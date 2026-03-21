"""
AI语义服务API模块。

本模块提供AI相关的RESTful API接口，包括文件搜索、文件解析和Ollama状态查询。

搜索功能说明：
- 图片文件：使用Ollama进行语义搜索（向量匹配）
- 文本文件：使用文件名匹配搜索（模糊查询）

AI解析功能：
- 仅支持图片文件（jpeg, png, gif, webp）
- 调用Ollama的Qwen3-VL-4B模型解析图片内容
- 生成语义向量存储到向量数据库

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-19
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.v1.dependencies import get_current_user, get_ollama, get_file_repo, AuthUser
from app.database.repositories.file_repository import FileRepository
from ollama.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

router = APIRouter()

SUPPORTED_IMAGE_TYPES = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/gif": [".gif"],
    "image/webp": [".webp"],
}


class SearchRequest(BaseModel):
    """
    文件搜索请求模型。

    属性:
        query: 搜索查询关键字（文件名匹配）
        limit: 返回结果数量限制，默认为20
        search_mode: 搜索模式，filename=仅文件名，vector=仅语义/图片，mixed=混合（默认）
    """
    query: str
    limit: int = 20
    search_mode: str = "mixed"  # "filename" | "vector" | "mixed"


class SearchResult(BaseModel):
    """
    搜索结果模型。

    属性:
        file_id: 文件唯一标识符
        filename: 文件名
        filetype: 文件类型
        is_ai_parsed: 是否已AI解析（用于语义搜索）
        size: 文件大小（字节）
        upload_time: 上传时间（可选，供前端展示）
    """
    file_id: str
    filename: str
    filetype: str
    is_ai_parsed: bool
    size: int
    upload_time: Optional[str] = None


class SearchResponse(BaseModel):
    """
    搜索响应模型。

    属性:
        results: 搜索结果列表
        total: 总结果数量
        mode: 搜索模式（filename/vector）
    """
    results: List[SearchResult]
    total: int
    mode: str


class OllamaStatus(BaseModel):
    """
    Ollama服务状态模型。
    与 /system/ollama 的 OllamaStatusInfo 语义对齐，提供 available 与 service_available 双字段。
    """
    available: bool
    service_available: bool = False  # 与 available 一致，供前端统一使用
    model: str = "qwen3-vl:4b"
    embedding_model: str = "nomic-embed-text-v2-moe"
    error: Optional[str] = None

    class Config:
        # 构造时用 available 填充 service_available
        pass

    def __init__(self, **data: Any) -> None:
        if "service_available" not in data and "available" in data:
            data["service_available"] = data["available"]
        super().__init__(**data)


class ParseResponse(BaseModel):
    """
    文件解析响应模型。

    属性:
        file_id: 文件唯一标识符
        success: 解析是否成功
        message: 解析结果消息
        extracted_text: 提取的文本内容（截断版本）
    """
    file_id: str
    success: bool
    message: str
    extracted_text: Optional[str] = None


def is_supported_image_type(filetype: str) -> bool:
    """检查文件类型是否为支持的图片格式。"""
    return filetype.lower() in SUPPORTED_IMAGE_TYPES


def is_image_file(filename: str, filetype: str) -> bool:
    """检查文件是否为图片类型。"""
    if is_supported_image_type(filetype):
        return True
    ext = Path(filename).suffix.lower()
    for extensions in SUPPORTED_IMAGE_TYPES.values():
        if ext in extensions:
            return True
    return False


def _file_id_from_vector_hit(item: dict) -> Optional[str]:
    """从 Chroma 查询条目中解析业务 file_id（兼容 metadata 与文档 id）。"""
    meta = item.get("metadata")
    if not isinstance(meta, dict):
        meta = {}
    raw = meta.get("file_id")
    if raw is not None:
        s = str(raw).strip()
        if s:
            return s
    doc_id = item.get("id") or ""
    if isinstance(doc_id, str) and doc_id.startswith("file_"):
        return doc_id[5:]
    if doc_id:
        return str(doc_id)
    return None


def _merge_vector_search_hits(
    file_repo: FileRepository,
    vector_results: List[dict],
    current_user: AuthUser,
) -> List[tuple[float, str, dict]]:
    """
    将向量命中与 SQLite 对齐：去掉孤立向量、按当前用户过滤、按磁盘路径去重（保留距离最小的一条）。

    返回 (distance, file_id, result_row) 列表，按 distance 升序，供写入 results_dict。
    """
    path_key_best: dict[str, tuple[float, str, dict]] = {}

    raw_ids: List[str] = []
    for item in vector_results:
        fid = _file_id_from_vector_hit(item)
        if fid:
            raw_ids.append(fid)
    meta_map = file_repo.get_file_metadata_by_ids(raw_ids)

    for item in vector_results:
        file_id = _file_id_from_vector_hit(item)
        if not file_id:
            continue
        distance = item.get("distance")
        if distance is None:
            distance = float("inf")

        file_meta = meta_map.get(file_id)
        if file_meta is None:
            logger.info(
                "向量命中但 SQLite 无对应记录，视为孤立索引并尝试清理，file_id=%s",
                file_id,
            )
            file_repo.remove_vector_index(file_id)
            continue
        if file_meta.userid != current_user.id:
            continue

        try:
            resolved = str(Path(file_meta.filepath).resolve())
        except OSError:
            resolved = file_meta.filepath
        dedupe_key = f"{file_meta.userid}\x00{resolved}"

        row = {
            "file_id": file_meta.file_id,
            "filename": file_meta.filename,
            "filetype": file_meta.filetype,
            "is_ai_parsed": file_meta.is_ai_parsed,
            "size": file_meta.size,
            "upload_time": getattr(file_meta, "upload_time", None),
        }
        prev = path_key_best.get(dedupe_key)
        if prev is None or distance < prev[0]:
            path_key_best[dedupe_key] = (distance, file_meta.file_id, row)

    merged = list(path_key_best.values())
    merged.sort(key=lambda t: t[0])
    return merged


@router.post("/search", response_model=SearchResponse)
async def search_files(
    request: SearchRequest,
    file_repo: "FileRepository" = Depends(get_file_repo),
    current_user: AuthUser = Depends(get_current_user),
    ollama: OllamaClient = Depends(get_ollama),
):
    """
    搜索文件接口。

    混合搜索策略：
    - 首先进行文件名模糊匹配（所有文件类型）
    - 对于已AI解析的图片文件，同时进行向量语义搜索

    参数:
        request: 搜索请求，包含查询关键字和结果数量限制
        current_user: 当前认证用户（通过依赖注入获取）
        ollama: Ollama客户端（通过依赖注入获取）

    返回:
        SearchResponse: 包含搜索结果和总数的响应对象

    异常:
        HTTPException: 当搜索失败时抛出500错误
    """
    q_preview = request.query[:50] + ("…" if len(request.query) > 50 else "")
    logger.debug("文件搜索请求，查询: %s", q_preview)
    try:
        if not request.query.strip():
            logger.warning("搜索失败，查询为空")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="搜索查询不能为空",
            )

        results_dict = {}
        mode_param = (request.search_mode or "mixed").strip().lower()
        if mode_param not in ("filename", "vector", "mixed"):
            mode_param = "mixed"
        search_mode = "filename"

        # 按文件名搜索（文件名/字符搜索）
        if mode_param in ("filename", "mixed"):
            filename_results = file_repo.search_files_by_filename(request.query)
            for file_meta in filename_results:
                results_dict[file_meta.file_id] = {
                    "file_id": file_meta.file_id,
                    "filename": file_meta.filename,
                    "filetype": file_meta.filetype,
                    "is_ai_parsed": file_meta.is_ai_parsed,
                    "size": file_meta.size,
                    "upload_time": getattr(file_meta, "upload_time", None),
                }
            if filename_results:
                search_mode = "filename" if mode_param == "filename" else "mixed"

        # 仅当需要向量时且文件名未达上限时做语义/图片搜索
        if mode_param == "vector" or (mode_param == "mixed" and len(results_dict) < request.limit):
            if await ollama.is_available():
                try:
                    query_vector = await ollama.embed_text(request.query)
                    logger.debug("查询向量生成完成，维度: %s", len(query_vector))
                    vector_results = file_repo.search_similar_files(
                        query_vector=query_vector,
                        n_results=request.limit,
                    )
                    logger.debug("向量搜索返回 %s 个结果", len(vector_results))

                    merged_hits = _merge_vector_search_hits(
                        file_repo, vector_results, current_user
                    )
                    logger.debug(
                        "向量结果经 SQLite 校验与路径去重后 %s 条（原始 %s 条）",
                        len(merged_hits),
                        len(vector_results),
                    )
                    for distance, file_id, row in merged_hits:
                        logger.debug(
                            "向量结果(已对齐): file_id=%s, distance=%s, filename=%s",
                            file_id,
                            f"{distance:.4f}" if distance != float("inf") else "n/a",
                            row.get("filename"),
                        )
                        if file_id not in results_dict:
                            results_dict[file_id] = row
                        if mode_param == "vector":
                            search_mode = "vector"
                        else:
                            search_mode = "mixed"
                except Exception as e:
                    logger.warning(f"向量搜索失败: {e}")
                    if mode_param == "vector":
                        results_dict.clear()
            elif mode_param == "vector":
                results_dict.clear()

        if len(results_dict) == 0 and mode_param != "mixed":
            logger.info("当前模式无匹配，返回空结果")
            return SearchResponse(results=[], total=0, mode=mode_param)

        results = list(results_dict.values())[:request.limit]

        logger.debug("搜索完成，找到 %s 个匹配结果，模式: %s", len(results), search_mode)
        return SearchResponse(
            results=[
                SearchResult(**r) for r in results
            ],
            total=len(results),
            mode=search_mode,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索失败: {str(e)}",
        )


@router.post("/parse/{file_id}", response_model=ParseResponse)
async def parse_file(
    file_id: str,
    file_repo: "FileRepository" = Depends(get_file_repo),
    current_user: AuthUser = Depends(get_current_user),
    ollama: OllamaClient = Depends(get_ollama),
):
    """
    对指定文件进行AI解析。
    
    该接口调用Ollama的多模态模型（Qwen3-VL-4B）对图片文件进行解析，
    提取文本内容并生成语义向量，用于后续的语义搜索。
    
    参数:
        file_id: 需要解析的文件唯一标识符
        file_repo: 文件仓库（通过依赖注入获取）
        current_user: 当前认证用户（通过依赖注入获取）
        ollama: Ollama客户端（通过依赖注入获取）
    
    返回:
        ParseResponse: 包含解析结果的响应对象
    
    异常:
        HTTPException: 当文件不存在或解析失败时抛出相应错误
    """
    logger.info(f"文件解析请求，文件ID: {file_id}")
    try:
        if not await ollama.is_available():
            logger.error("Ollama服务不可用")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Ollama服务不可用，请确保Ollama正在运行",
            )
        
        file_metadata = file_repo.get_file_metadata_by_id(file_id)
        
        if file_metadata is None:
            logger.warning(f"文件不存在，文件ID: {file_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在",
            )
        
        if not is_supported_image_type(file_metadata.filetype):
            logger.warning(f"不支持的文件类型，文件ID: {file_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件类型: {file_metadata.filetype}，仅支持图片格式",
            )
        
        file_path = Path(file_metadata.filepath)
        if not file_path.exists():
            logger.error(f"文件已丢失，文件ID: {file_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件已丢失",
            )
        
        logger.info(f"开始解析文件: {file_id}, 路径: {file_path}")
        
        extracted_text = await ollama.parse_image_content(str(file_path))
        
        if not extracted_text or not extracted_text.strip():
            extracted_text = f"[图片内容] {file_metadata.filename}"
        
        embedding = await ollama.embed_text(extracted_text)
        
        vector_metadata = {
            "filename": file_metadata.filename,
            "filetype": file_metadata.filetype,
            "file_size": file_metadata.size,
            "parsed_text": extracted_text[:1000],
            "parsed_at": file_metadata.upload_time,
        }
        
        file_repo.add_or_update_vector(
            file_id=file_id,
            vector=embedding,
            metadata=vector_metadata,
        )
        
        file_repo.mark_as_ai_parsed(file_id)
        
        logger.info(f"文件解析完成: {file_id}, 提取文本长度: {len(extracted_text)}")
        
        return ParseResponse(
            file_id=file_id,
            success=True,
            message="文件解析成功，已生成语义向量",
            extracted_text=extracted_text[:500] if len(extracted_text) > 500 else extracted_text,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件解析失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件解析失败: {str(e)}",
        )


@router.get("/status", response_model=OllamaStatus)
async def get_ollama_status(
    ollama: OllamaClient = Depends(get_ollama),
):
    """
    查询Ollama服务的当前状态。
    
    该接口检查Ollama推理引擎是否可用，并返回当前配置的模型信息。
    用于前端判断AI功能是否可用。
    
    参数:
        ollama: Ollama客户端（通过依赖注入获取）
    
    返回:
        OllamaStatus: 包含服务可用性和模型配置的状态对象
    """
    logger.debug("查询Ollama服务状态")
    try:
        is_avail = await ollama.is_available()
        
        if not is_avail:
            logger.warning("Ollama服务不可用")
            return OllamaStatus(
                available=False,
                service_available=False,
                model=ollama.vision_model,
                embedding_model=ollama.embedding_model,
                error="无法连接到Ollama服务",
            )
        
        logger.info("Ollama服务可用")
        return OllamaStatus(
            available=True,
            service_available=True,
            model=ollama.vision_model,
            embedding_model=ollama.embedding_model,
            error=None,
        )
        
    except Exception as e:
        logger.error(f"获取Ollama状态失败: {e}")
        return OllamaStatus(
            available=False,
            service_available=False,
            model=getattr(ollama, "vision_model", "qwen3-vl:4b"),
            embedding_model=ollama.embedding_model,
            error=str(e),
        )
