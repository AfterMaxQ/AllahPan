"""
Ollama API客户端模块。

本模块提供Ollama推理引擎的Python封装，封装文本向量化、图片解析和服务状态检查等功能。
Ollama是本地AI推理框架，支持Qwen3-VL-4B等多模态模型。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-19
"""

import base64
import logging
import time
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class OllamaClient:
    """
    Ollama推理引擎客户端类。
    
    该类封装与本地Ollama服务的所有交互，包括：
    - 文本向量化（使用nomic-embed-text-v2-moe模型）
    - 图片内容解析（使用qwen3-vl:4b模型）
    - 服务健康状态检查
    
    属性:
        base_url: Ollama服务地址
        embedding_model: 向量化模型名称
        vision_model: 多模态视觉模型名称
        timeout: 请求超时时间（秒）
        _client: httpx异步客户端
    """
    
    # 与 app.config.OLLAMA_EMBEDDING_MODEL / OLLAMA_VISION_MODEL 默认值一致，注入时以 config 为准
    DEFAULT_EMBEDDING_MODEL = "nomic-embed-text-v2-moe"
    DEFAULT_VISION_MODEL = "qwen3-vl:4b"
    DEFAULT_TIMEOUT = 300  # 图片解析+向量化较慢，避免 ReadTimeout
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        vision_model: str = DEFAULT_VISION_MODEL,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """
        初始化Ollama客户端。
        
        参数:
            base_url: Ollama服务的HTTP地址（默认: http://localhost:11434）
            embedding_model: 文本向量化模型名称（默认: nomic-embed-text-v2-moe）
            vision_model: 多模态视觉模型名称（默认: qwen3-vl:4b）
            timeout: HTTP请求超时时间（秒，默认: 60）
        """
        self.base_url = base_url.rstrip("/")
        self.embedding_model = embedding_model
        self.vision_model = vision_model
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        # 短时间缓存可用性探测，减轻搜索/健康检查对 /api/tags 的突发压力
        self._availability_cache: Optional[Tuple[float, bool]] = None
        self._availability_ttl_sec = 5.0
    
    async def _get_client(self) -> httpx.AsyncClient:
        """
        获取或创建HTTP客户端实例。
        
        使用懒加载模式创建httpx异步客户端，确保连接复用。
        
        返回:
            httpx.AsyncClient: 配置好的异步HTTP客户端
        """
        if self._client is None or self._client.is_closed:
            # 新版 httpx 要求：要么只传 default，要么显式设置 connect/read/write/pool 四参数
            read_sec = float(self.timeout)
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=read_sec,
                    write=read_sec,
                    pool=5.0,
                ),
                follow_redirects=True,
            )
        return self._client
    
    async def close(self) -> None:
        """
        关闭HTTP客户端连接。
        
        在使用完客户端后应调用此方法释放资源。
        """
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    async def is_available(self) -> bool:
        """
        检查Ollama服务是否可用。
        
        通过调用/api/tags端点验证服务连接状态。
        
        返回:
            bool: 服务可用返回True，否则返回False
        """
        now = time.monotonic()
        if self._availability_cache is not None:
            ts, ok = self._availability_cache
            if now - ts < self._availability_ttl_sec:
                return ok
        logger.debug("检查Ollama服务可用性")
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            ok = response.status_code == 200
            logger.debug("Ollama服务状态: %s", "可用" if ok else "不可用")
            self._availability_cache = (time.monotonic(), ok)
            return ok
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
            logger.warning(f"Ollama服务连接失败: {e}")
            return False
        except Exception as e:
            logger.error(f"检查Ollama状态时发生错误: {e}")
            return False
    
    async def get_models(self) -> List[Dict[str, Any]]:
        """
        获取Ollama已加载的模型列表。
        
        返回:
            List[Dict[str, Any]]: 模型列表，每个模型包含name、size、modified_at等字段
        """
        logger.info("获取Ollama模型列表")
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            models = data.get("models", [])
            logger.info(f"获取到 {len(models)} 个Ollama模型")
            return models
        except Exception as e:
            logger.error(f"获取模型列表失败: {e}")
            return []
    
    async def embed_text(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> List[float]:
        """
        将文本转换为语义向量。
        
        使用指定的嵌入模型将输入文本转换为固定维度的语义向量，
        用于后续的向量检索和相似性匹配。
        
        参数:
            text: 待向量化的文本内容
            model: 嵌入模型名称（默认使用初始化时配置的模型）
        
        返回:
            List[float]: 文本的语义向量表示
            
        异常:
            httpx.HTTPStatusError: 当API返回错误状态码时
            httpx.TimeoutException: 当请求超时时
            ValueError: 当文本为空时
        """
        logger.debug("开始向量化文本，长度: %s，模型: %s", len(text), model or self.embedding_model)
        if not text or not text.strip():
            logger.error("文本内容为空")
            raise ValueError("文本内容不能为空")
        
        model = model or self.embedding_model
        client = await self._get_client()
        
        payload = {
            "model": model,
            "input": text.strip(),
        }
        
        # 使用 OpenAI 兼容的 /v1/embeddings 端点（兼容性更好）
        response = await client.post("/v1/embeddings", json=payload)
        response.raise_for_status()
        
        data = response.json()
        # OpenAI 兼容格式：data[0].embedding
        data_list = data.get("data")
        
        if data_list is None or not isinstance(data_list, list) or len(data_list) == 0:
            logger.error("API 响应中未包含 data 字段或 data 为空")
            raise ValueError("API 响应中未包含 data 字段或 data 为空")
        
        embedding = data_list[0].get("embedding")
        
        if embedding is None:
            logger.error("API 响应中未包含 embedding 字段")
            raise ValueError("API 响应中未包含 embedding 字段")
        
        if not isinstance(embedding, list):
            logger.error(f"embedding 字段类型错误，期望 list 但得到{type(embedding)}")
            raise ValueError(f"embedding 字段类型错误，期望 list 但得到{type(embedding)}")
        
        logger.debug("文本向量化完成，向量维度: %s", len(embedding))
        return embedding
    
    async def generate_response(
        self,
        prompt: str,
        images: Optional[List[str]] = None,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """
        生成AI响应，支持多模态输入。
        
        调用Ollama的生成接口，可选附带图片进行多模态理解。
        适用于图片内容解析、OCR、问答等场景。
        
        参数:
            prompt: 输入提示词/问题
            images: 图片文件路径列表（支持jpeg, png, gif, webp）
            model: 使用的模型（默认使用初始化时配置的视觉模型）
            system: 系统提示词，用于指定模型行为
            temperature: 生成温度（0-1之间，越低越确定）
            max_tokens: 最大生成的token数量
        
        返回:
            str: 模型生成的文本响应
            
        异常:
            httpx.HTTPStatusError: 当API返回错误状态码时
            httpx.TimeoutException: 当请求超时时
            FileNotFoundError: 当指定的图片文件不存在时
        """
        logger.info(f"开始生成AI响应，prompt长度: {len(prompt)}，图片数量: {len(images) if images else 0}")
        model = model or self.vision_model
        client = await self._get_client()
        
        # keep_alive 单位秒，避免每次请求后卸载模型导致延迟
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": 300,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        
        if system:
            payload["system"] = system
        
        if images:
            encoded_images = []
            max_image_bytes = 80 * 1024 * 1024  # 80MB，防止大图导致 OOM
            for img_path in images:
                path = Path(img_path)
                if not path.exists():
                    logger.error(f"图片文件不存在: {img_path}")
                    raise FileNotFoundError(f"图片文件不存在: {img_path}")
                size = path.stat().st_size
                if size > max_image_bytes:
                    logger.error(f"图片过大，跳过: {img_path} ({size} bytes)")
                    raise ValueError(f"图片大小超过限制 ({size} > {max_image_bytes} bytes)")
                with open(path, "rb") as f:
                    img_base64 = base64.b64encode(f.read()).decode("utf-8")
                encoded_images.append(img_base64)
            
            payload["images"] = encoded_images
            logger.info(f"已编码 {len(encoded_images)} 张图片")
        
        response = await client.post("/api/generate", json=payload)
        response.raise_for_status()
        
        data = response.json()
        result = data.get("response", "").strip()
        logger.info(f"AI响应生成完成，响应长度: {len(result)}")
        return result
    
    async def parse_image_content(
        self,
        image_path: str,
        model: Optional[str] = None,
    ) -> str:
        """
        解析图片内容，提取文本信息。
        
        使用多模态模型分析图片，提取其中的文字内容和视觉描述。
        适用于扫描文档、名片、截图等场景的文字提取。
        
        参数:
            image_path: 图片文件的绝对或相对路径
            model: 使用的视觉模型（默认使用初始化时配置的模型）
        
        返回:
            str: 图片中提取的文本内容和视觉描述
        """
        logger.info(f"开始解析图片内容，路径: {image_path}")
        model = model or self.vision_model
        
        system_prompt = "你是图片分析助手。只输出正文，不要标题或 Markdown。"

        prompt = (
            "用约100字以内中文概括画面要点（人物/场景/物体/氛围）。"
            "若有清晰可读文字，简要转录关键信息。"
        )

        result = await self.generate_response(
            prompt=prompt,
            images=[image_path],
            model=model,
            system=system_prompt,
            temperature=0.3,
            max_tokens=320,
        )
        logger.info(f"图片内容解析完成，提取文本长度: {len(result)}")
        return result
    
    async def health_check(self) -> Dict[str, Any]:
        """
        执行完整的健康检查。
        
        检查Ollama服务的可用性、已加载模型和系统状态。
        
        返回:
            Dict[str, Any]: 包含健康状态信息的字典：
                - available: 服务是否可用
                - embedding_model: 配置的嵌入模型
                - vision_model: 配置的视觉模型
                - loaded_models: 已加载的模型列表
                - error: 如果不可用，错误信息
        """
        logger.info("开始执行Ollama健康检查")
        result = {
            "available": False,
            "embedding_model": self.embedding_model,
            "vision_model": self.vision_model,
            "loaded_models": [],
            "error": None,
        }
        
        if not await self.is_available():
            result["error"] = "无法连接到Ollama服务，请确保Ollama正在运行"
            logger.warning("Ollama健康检查失败: 服务不可用")
            return result
        
        result["available"] = True
        result["loaded_models"] = await self.get_models()
        logger.info(f"Ollama健康检查完成，服务可用，已加载 {len(result['loaded_models'])} 个模型")
        
        return result


_ollama_client: Optional[OllamaClient] = None


def get_ollama_client(
    base_url: str = "http://localhost:11434",
    embedding_model: str = OllamaClient.DEFAULT_EMBEDDING_MODEL,
    vision_model: str = OllamaClient.DEFAULT_VISION_MODEL,
) -> OllamaClient:
    """
    获取OllamaClient单例实例。
    
    使用单例模式确保整个应用生命周期内只创建一个客户端实例，
    避免重复创建连接池。
    
    参数:
        base_url: Ollama服务地址
        embedding_model: 向量化模型名称
        vision_model: 视觉模型名称
    
    返回:
        OllamaClient: 单例客户端实例
    """
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient(
            base_url=base_url,
            embedding_model=embedding_model,
            vision_model=vision_model,
        )
    return _ollama_client
