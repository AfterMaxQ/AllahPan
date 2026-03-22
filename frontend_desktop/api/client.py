"""
统一 API 客户端模块。

本模块封装所有 HTTP 请求逻辑，提供统一的错误处理和认证机制。
使用 httpx 同步客户端，在 QThread 中安全调用。

作者: AllahPan团队
"""

import json
import httpx
from typing import Optional, Any, Dict
from dataclasses import dataclass

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


@dataclass
class APIError(Exception):
    """API 错误异常类。"""
    status_code: int
    detail: Any  # 可能是 str 或 list（如 FastAPI 校验错误）
    error: Optional[str] = None
    
    def __str__(self) -> str:
        d = self.detail
        if d is None:
            return self.error or f"API错误 (状态码: {self.status_code})"
        if isinstance(d, str):
            return d
        if isinstance(d, list):
            parts = [str(x.get("msg", x)) if isinstance(x, dict) else str(x) for x in d]
            return "; ".join(parts) if parts else f"API错误 (状态码: {self.status_code})"
        return str(d)


class APIClient:
    """
    统一 API 客户端类。
    
    使用 httpx 同步客户端，提供：
    - 自动添加认证头
    - 统一的错误处理
    - 响应数据验证
    - 超时控制
    
    注意（httpx URL 合并规则）:
    - base_url 必须为「目录」形式并以 / 结尾，例如 http://host:8000/api/v1/
    - 请求 path 必须为相对片段且不以 / 开头，例如 system/metrics/traffic
    否则会出现请求落到 http://host/system/... 或 http://host/api/tunnel/...，
    后端无此路由时易被 SPA 静态托管返回 HTML，表现为「服务器返回了 HTML 而非 JSON」。
    """
    
    DEFAULT_TIMEOUT = 30.0
    UPLOAD_TIMEOUT = 300.0
    
    @staticmethod
    def _normalize_base_url(url: str) -> str:
        u = (url or "").strip()
        if not u:
            return u
        return u.rstrip("/") + "/"
    
    @staticmethod
    def _relative_api_path(path: str) -> str:
        if not path:
            return path
        return path.lstrip("/")
    
    def __init__(self, base_url: Optional[str] = None):
        """
        初始化 API 客户端。
        
        参数:
            base_url: API 基础 URL，默认使用 config.API_BASE_URL
        """
        self.base_url = self._normalize_base_url(base_url or config.API_BASE_URL)
        self._client: Optional[httpx.Client] = None
    
    def _get_client(self) -> httpx.Client:
        """获取或创建 HTTP 客户端。"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.DEFAULT_TIMEOUT),
                follow_redirects=True,
            )
        return self._client
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """获取认证请求头。"""
        headers = {}
        token = config.get_auth_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers
    
    def _handle_response(self, response: httpx.Response) -> Any:
        """
        处理 HTTP 响应。
        
        参数:
            response: httpx 响应对象
            
        返回:
            解析后的响应数据
            
        异常:
            APIError: 当响应状态码不是 2xx 时
        """
        if response.status_code == 401:
            config.clear_auth()
            raise APIError(401, "认证失败，请重新登录")
        
        if response.status_code == 404:
            raise APIError(404, "请求的资源不存在")
        
        if response.status_code >= 400:
            try:
                error_data = response.json()
                raw = error_data.get("detail", error_data.get("message", "请求失败"))
                if isinstance(raw, list):
                    parts = []
                    for item in raw:
                        if isinstance(item, dict) and "msg" in item:
                            parts.append(str(item["msg"]))
                        else:
                            parts.append(str(item))
                    detail = "; ".join(parts) if parts else "请求失败"
                else:
                    detail = raw if isinstance(raw, str) else str(raw)
            except Exception:
                detail = f"请求失败 (状态码: {response.status_code})"
            raise APIError(response.status_code, detail)
        
        if response.status_code == 204:
            return None

        raw_text = response.text
        if not (raw_text or "").strip():
            return {}

        try:
            parsed = response.json()
        except Exception:
            t = raw_text.strip()
            if t.startswith("<!") or t.lower().startswith("<html"):
                raise APIError(
                    response.status_code,
                    "服务器返回了 HTML 而非 API JSON，请确认 API 基础地址为后端的 /api/v1（例如 http://主机:端口/api/v1）。",
                )
            raise APIError(
                response.status_code,
                f"响应无法解析为 JSON: {t[:200]}",
            )

        if isinstance(parsed, str):
            if "<html" in parsed.lower()[:800]:
                raise APIError(
                    response.status_code,
                    "响应内容为 HTML 文本，请检查是否连错地址或网关替换了响应体。",
                )
            raise APIError(
                response.status_code,
                f"接口返回了 JSON 字符串而非对象，可能是网关或旧版后端: {parsed[:200]}",
            )

        return parsed
    
    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """
        发送 GET 请求。
        
        参数:
            path: API 路径
            params: 查询参数
            timeout: 超时时间（秒）
            
        返回:
            响应数据
        """
        client = self._get_client()
        headers = self._get_auth_headers()
        
        rel = self._relative_api_path(path)
        response = client.get(
            rel,
            params=params,
            headers=headers,
            timeout=timeout or self.DEFAULT_TIMEOUT,
        )
        return self._handle_response(response)
    
    def post(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """
        发送 POST 请求。
        
        参数:
            path: API 路径
            json: JSON 请求体
            data: 表单数据
            timeout: 超时时间（秒）
            
        返回:
            响应数据
        """
        client = self._get_client()
        headers = self._get_auth_headers()
        
        rel = self._relative_api_path(path)
        response = client.post(
            rel,
            json=json,
            data=data,
            headers=headers,
            timeout=timeout or self.DEFAULT_TIMEOUT,
        )
        return self._handle_response(response)
    
    def patch(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """
        发送 PATCH 请求。

        参数:
            path: API 路径
            json: JSON 请求体
            timeout: 超时时间（秒）

        返回:
            响应数据
        """
        client = self._get_client()
        headers = self._get_auth_headers()
        rel = self._relative_api_path(path)
        response = client.request(
            "PATCH",
            rel,
            json=json,
            headers=headers,
            timeout=timeout or self.DEFAULT_TIMEOUT,
        )
        return self._handle_response(response)

    def delete(
        self,
        path: str,
        timeout: Optional[float] = None,
    ) -> Any:
        """
        发送 DELETE 请求。

        参数:
            path: API 路径
            timeout: 超时时间（秒）

        返回:
            响应数据
        """
        client = self._get_client()
        headers = self._get_auth_headers()

        rel = self._relative_api_path(path)
        response = client.delete(
            rel,
            headers=headers,
            timeout=timeout or self.DEFAULT_TIMEOUT,
        )
        return self._handle_response(response)
    
    def upload_file(
        self,
        file_path: str,
        file_name: str,
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        上传文件。
        
        参数:
            file_path: 文件本地路径
            file_name: 上传后的文件名
            progress_callback: 进度回调函数，参数为 (已上传字节数, 总字节数)
            
        返回:
            上传成功后的文件元数据
        """
        import os
        
        file_size = os.path.getsize(file_path)
        
        client = self._get_client()
        headers = self._get_auth_headers()
        
        class FileWithProgress:
            """包装文件对象，在读取时触发进度回调。"""
            def __init__(self, path: str, callback, total_size: int, chunk_size: int = 64 * 1024):
                self._file = open(path, "rb")
                self._callback = callback
                self._total_size = total_size
                self._chunk_size = chunk_size
                self._uploaded = 0
                self._done = False
            
            def read(self, size: int = -1) -> bytes:
                if self._done:
                    return b""
                data = self._file.read(size)
                if not data:
                    self._done = True
                    if self._callback:
                        self._callback(self._total_size, self._total_size)
                    self._file.close()
                    return b""
                self._uploaded += len(data)
                if self._callback:
                    self._callback(self._uploaded, self._total_size)
                return data
            
            def __enter__(self):
                return self
            
            def __exit__(self, *args):
                if not self._file.closed:
                    self._file.close()
        
        wrapped_file = FileWithProgress(file_path, progress_callback, file_size)
        raw = (file_name or "").strip().replace("\\", "/")
        if "/" in raw:
            rel_parent, base_nm = raw.rsplit("/", 1)
            rel_parent = rel_parent.strip().strip("/") or None
            base_nm = base_nm.strip() or "unnamed"
        else:
            rel_parent = None
            base_nm = raw or "unnamed"
        files = {"file": (base_nm, wrapped_file)}
        data = {"relative_parent": rel_parent} if rel_parent else None

        response = client.post(
            self._relative_api_path("/files/upload"),
            files=files,  # type: ignore[arg-type]
            data=data,
            headers=headers,
            timeout=httpx.Timeout(self.UPLOAD_TIMEOUT),
        )
        return self._handle_response(response)
    
    def download_file(
        self,
        file_id: str,
        save_path: str,
        progress_callback: Optional[callable] = None,
    ) -> str:
        """
        下载文件。
        
        参数:
            file_id: 文件 ID
            save_path: 保存路径
            progress_callback: 进度回调函数
            
        返回:
            保存的文件路径
        """
        import os
        
        client = self._get_client()
        headers = self._get_auth_headers()
        
        with client.stream(
            "GET",
            self._relative_api_path(f"/files/{file_id}/download"),
            headers=headers,
            timeout=httpx.Timeout(self.UPLOAD_TIMEOUT),
        ) as response:
            if response.status_code >= 400:
                body = response.read()
                try:
                    error_data = json.loads(body) if body else {}
                    detail = error_data.get("detail", "下载失败")
                except Exception:
                    detail = f"下载失败 (状态码: {response.status_code})"
                raise APIError(response.status_code, detail)
            content_length = int(response.headers.get("content-length", 0))
            downloaded = 0
            with open(save_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and content_length > 0:
                            progress_callback(downloaded, content_length)
            
            return save_path
    
    def close(self) -> None:
        """关闭 HTTP 客户端。"""
        if self._client and not self._client.is_closed:
            self._client.close()
            self._client = None
    
    def __enter__(self) -> "APIClient":
        """上下文管理器入口。"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器退出。"""
        self.close()


# 主线程使用的全局实例（兼容现有单线程调用）
_api_client: Optional[APIClient] = None
# 每线程独立实例，避免多线程共享同一 httpx.Client
import threading
_tls = threading.local()


def get_api_client() -> APIClient:
    """
    获取当前线程可用的 API 客户端。
    主线程使用全局单例；QThread 等子线程使用线程局部实例，保证线程安全。
    """
    if threading.current_thread() is threading.main_thread():
        global _api_client
        if _api_client is None:
            _api_client = APIClient()
        return _api_client
    if not getattr(_tls, "client", None):
        _tls.client = APIClient()
    return _tls.client


def close_api_client() -> None:
    """关闭主线程的全局 API 客户端。"""
    global _api_client
    if _api_client:
        _api_client.close()
        _api_client = None
