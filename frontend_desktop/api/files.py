"""
文件管理 API 模块。

提供文件上传、下载、列表、预览、删除等功能。

作者: AllahPan团队
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent))
from api.client import APIClient, get_api_client, APIError


class FilesAPI:
    """文件管理 API 操作类。"""
    
    def __init__(self, client: Optional[APIClient] = None):
        """
        初始化文件 API。
        
        参数:
            client: API 客户端实例，默认使用全局实例
        """
        self._client = client or get_api_client()
    
    def list_files(self, path: Optional[str] = None) -> Dict[str, Any]:
        """
        获取文件列表（以磁盘为事实来源，当前 path 下的目录与文件）。
        
        参数:
            path: 相对根目录的当前路径，空或 None 表示根目录
        
        返回:
            包含 directories、files、total 的字典
            
        异常:
            APIError: 获取失败时
        """
        params = {}
        if path is not None and path != "":
            params["path"] = path
        # 后端处理图片解析时可能较慢，给文件列表请求更长超时
        return self._client.get("/files/list", params=params, timeout=90.0)
    
    def get_file(self, file_id: str) -> Dict[str, Any]:
        """
        获取单个文件元数据。
        
        参数:
            file_id: 文件 ID
            
        返回:
            文件元数据字典
            
        异常:
            APIError: 文件不存在或获取失败时
        """
        return self._client.get(f"/files/{file_id}")
    
    def upload_file(
        self,
        file_path: str,
        progress_callback: Optional[callable] = None,
        upload_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        上传文件。
        
        参数:
            file_path: 文件本地路径
            progress_callback: 进度回调函数，参数为 (已上传字节数, 总字节数)
            upload_name: 传给后端的文件名，可含路径如 "证件/2024/合同.pdf"，不传则用 basename
        
        返回:
            上传成功后的文件元数据
            
        异常:
            APIError: 上传失败时
        """
        import os
        file_name = upload_name if upload_name is not None else os.path.basename(file_path)
        
        def wrapped_progress(uploaded: int, total: int) -> None:
            if progress_callback:
                progress_callback(uploaded, total)
        
        return self._client.upload_file(
            file_path=file_path,
            file_name=file_name,
            progress_callback=wrapped_progress,
        )
    
    def upload_file_sync(
        self,
        file_path: str,
        file_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        同步上传文件（无进度回调）。
        
        参数:
            file_path: 文件本地路径
            file_name: 可选的自定义文件名
            
        返回:
            上传成功后的文件元数据
            
        异常:
            APIError: 上传失败时
        """
        import os
        
        name = file_name or os.path.basename(file_path)
        
        client = self._client
        headers = client._get_auth_headers()
        
        with open(file_path, "rb") as f:
            files = {"file": (name, f)}
            response = client.post(
                "/files/upload",
                files=files,
                headers=headers,
            )
        
        return response
    
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
            
        异常:
            APIError: 下载失败时
        """
        return self._client.download_file(
            file_id=file_id,
            save_path=save_path,
            progress_callback=progress_callback,
        )
    
    def preview_file(self, file_id: str) -> bytes:
        """
        预览文件内容。
        
        参数:
            file_id: 文件 ID
            
        返回:
            文件内容的二进制数据
            
        异常:
            APIError: 预览失败时
        """
        client = self._client
        headers = client._get_auth_headers()
        
        # 须与 APIClient 一致：相对路径，避免 httpx 丢弃 /api/v1
        response = client._client.get(
            f"files/{file_id}/preview",
            headers=headers,
            timeout=90.0,
        )
        
        if response.status_code >= 400:
            raise APIError(response.status_code, "预览失败")
        
        return response.content
    
    def rename_file(self, file_id: str, filename: str) -> Dict[str, Any]:
        """
        重命名文件。

        参数:
            file_id: 文件 ID
            filename: 新文件名（不含路径）

        返回:
            更新后的文件元数据

        异常:
            APIError: 重命名失败时
        """
        return self._client.patch(
            f"/files/{file_id}/rename",
            json={"filename": filename},
        )

    def delete_file(self, file_id: str) -> None:
        """
        删除文件。

        注意：AllahPan 系统设计为无系统级删除功能，
        此接口仅用于清理已丢失的物理文件索引。

        参数:
            file_id: 文件 ID

        异常:
            APIError: 删除失败时
        """
        self._client.delete(f"/files/{file_id}")
    
    def get_file_url(self, file_id: str) -> str:
        """
        获取文件访问 URL。
        
        参数:
            file_id: 文件 ID
            
        返回:
            文件的直接访问 URL
        """
        base_url = self._client.base_url.rstrip("/")
        token = self._client._get_auth_headers().get("Authorization", "")
        return f"{base_url}/files/{file_id}/download"
