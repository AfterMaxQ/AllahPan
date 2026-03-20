"""
系统 API 模块。

提供存储信息、监听器状态和图片解析队列状态查询功能。

作者: AllahPan团队
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))
from api.client import APIClient, get_api_client, APIError


class SystemAPI:
    """系统 API 操作类。"""
    
    def __init__(self, client: Optional[APIClient] = None):
        """
        初始化系统 API。
        
        参数:
            client: API 客户端实例，默认使用全局实例
        """
        self._client = client or get_api_client()
    
    def get_storage_info(self) -> Dict[str, Any]:
        """
        获取存储空间信息。
        
        返回:
            包含 total_space、used_space、free_space、file_count 的字典
            
        异常:
            APIError: 获取失败时
        """
        return self._client.get("/system/info")
    
    def get_storage_directory(self) -> Dict[str, Any]:
        """
        获取存储目录路径（用于在文件管理器中打开）。
        
        返回:
            包含 path、exists、size 的字典
        """
        return self._client.get("/system/storage")
    
    def get_watcher_status(self) -> Dict[str, Any]:
        """
        获取目录监听器状态。
        
        返回:
            包含 running、watch_path、observer_alive 的字典
            
        异常:
            APIError: 获取失败时
        """
        return self._client.get("/system/watcher")
    
    def get_image_parser_status(self) -> Dict[str, Any]:
        """
        获取图片解析队列状态。
        
        返回:
            包含 queue_size、processing_count、worker_count、
            total_processed、total_failed、is_running 的字典
            
        异常:
            APIError: 获取失败时
        """
        return self._client.get("/system/image-parser-queue")
    
    def get_status_summary(self) -> Dict[str, Any]:
        """
        获取系统状态摘要。
        
        综合存储信息和 Ollama 状态。
        
        返回:
            系统状态摘要字典
        """
        from api.ai import AIAPI
        
        try:
            storage = self.get_storage_info()
        except Exception:
            storage = {
                "total_space": 0,
                "used_space": 0,
                "free_space": 0,
                "file_count": 0,
            }
        
        try:
            ai_api = AIAPI(self._client)
            ollama = ai_api.get_status()
        except Exception:
            ollama = {"available": False, "error": "无法获取"}
        
        try:
            watcher = self.get_watcher_status()
        except Exception:
            watcher = {"running": False}
        
        return {
            "storage": storage,
            "ollama": ollama,
            "watcher": watcher,
        }
    
    def format_storage_display(self, storage_info: Dict[str, Any]) -> str:
        """
        格式化存储信息为显示字符串。
        
        参数:
            storage_info: 存储信息字典
            
        返回:
            格式化的显示字符串，如 "256GB / 512GB"
        """
        from config import format_file_size
        
        used = format_file_size(storage_info.get("used_space", 0))
        total = format_file_size(storage_info.get("total_space", 0))
        
        if total == "0 B":
            return "存储信息不可用"
        
        return f"{used} / {total}"
    
    def get_storage_usage_percent(self, storage_info: Dict[str, Any]) -> float:
        """
        获取存储空间使用百分比。
        
        参数:
            storage_info: 存储信息字典
            
        返回:
            使用百分比（0-100）
        """
        total = storage_info.get("total_space", 0)
        used = storage_info.get("used_space", 0)
        
        if total <= 0:
            return 0
        
        return round((used / total) * 100, 1)
