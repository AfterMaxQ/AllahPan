"""
认证 API 模块。

提供用户登录、注册和认证相关功能。

作者: AllahPan团队
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))
from api.client import APIClient, get_api_client, APIError
import config


class AuthAPI:
    """认证 API 操作类。"""
    
    def __init__(self, client: Optional[APIClient] = None):
        """
        初始化认证 API。
        
        参数:
            client: API 客户端实例，默认使用全局实例
        """
        self._client = client or get_api_client()
    
    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        用户登录。
        
        参数:
            username: 用户名
            password: 密码
            
        返回:
            包含 access_token 和用户信息的字典
            
        异常:
            APIError: 登录失败时
        """
        response = self._client.post(
            "/auth/login",
            json={
                "username": username,
                "password": password,
            },
        )
        
        token = response.get("access_token")
        user = response.get("user")
        
        if token and user:
            config.set_auth_token(token)
            config.set_auth_user(user)
        
        return response
    
    def register(self, username: str, password: str, email: str) -> Dict[str, Any]:
        """
        用户注册。
        
        参数:
            username: 用户名
            password: 密码
            email: 邮箱
            
        返回:
            创建的用户信息
            
        异常:
            APIError: 注册失败时
        """
        return self._client.post(
            "/auth/register",
            json={
                "username": username,
                "password": password,
                "email": email,
            },
        )
    
    def get_current_user(self) -> Dict[str, Any]:
        """
        获取当前登录用户信息。
        
        返回:
            用户信息字典
            
        异常:
            APIError: 获取失败时
        """
        return self._client.get("/auth/me")
    
    def logout(self) -> None:
        """退出登录，清除认证信息。"""
        config.clear_auth()
    
    @property
    def is_authenticated(self) -> bool:
        """检查是否已认证。"""
        return config.get_auth_token() is not None
    
    @property
    def current_user(self) -> Optional[Dict[str, Any]]:
        """获取当前用户信息。"""
        return config.get_auth_user()
