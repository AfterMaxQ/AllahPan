"""
AI 语义搜索 API 模块。

提供文件搜索、AI 解析和 Ollama 状态查询功能。

作者: AllahPan团队
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent))
from api.client import APIClient, get_api_client, APIError


class AIAPI:
    """AI 语义搜索 API 操作类。"""
    
    def __init__(self, client: Optional[APIClient] = None):
        """
        初始化 AI API。
        
        参数:
            client: API 客户端实例，默认使用全局实例
        """
        self._client = client or get_api_client()
    
    def search(
        self,
        query: str,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        搜索文件。
        
        混合搜索策略：
        - 首先进行文件名模糊匹配
        - 对于已 AI 解析的图片文件，同时进行向量语义搜索
        
        参数:
            query: 搜索查询关键字
            limit: 返回结果数量限制，默认 20
            
        返回:
            包含 results 列表、total 总数和 mode 搜索模式的字典
            
        异常:
            APIError: 搜索失败时
        """
        return self._client.post(
            "/ai/search",
            json={
                "query": query,
                "limit": limit,
            },
        )
    
    def parse_file(self, file_id: str) -> Dict[str, Any]:
        """
        对指定文件进行 AI 解析。
        
        仅支持图片文件，调用 Ollama 的多模态模型解析图片内容，
        提取文本并生成语义向量。
        
        参数:
            file_id: 文件 ID
            
        返回:
            包含解析结果的字典
            
        异常:
            APIError: 解析失败时
        """
        return self._client.post(f"/ai/parse/{file_id}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取 Ollama 服务状态。
        
        返回:
            包含 available、model、embedding_model、error 等字段的字典
            
        异常:
            APIError: 获取状态失败时
        """
        return self._client.get("/ai/status")
    
    @property
    def is_available(self) -> bool:
        """检查 Ollama 服务是否可用（与后端 service_available/available 一致）。"""
        try:
            status = self.get_status()
            return status.get("service_available", status.get("available", False))
        except Exception:
            return False
    
    def get_search_mode_display(self, mode: str) -> str:
        """
        获取搜索模式的中文显示名称。
        
        参数:
            mode: 搜索模式（filename/mixed）
            
        返回:
            中文显示名称
        """
        mode_map = {
            "filename": "文件名搜索",
            "mixed": "混合搜索",
            "vector": "向量搜索",
        }
        return mode_map.get(mode, mode)
