"""
Tunnel API 客户端模块。

提供 Cloudflare Tunnel 的前端 API 接口封装。

作者: AllahPan团队
创建日期: 2026-03-20
"""

from typing import Optional, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from api.client import get_api_client, APIError


# ==================== API 路径（相对 base_url，与后端 /api/v1 拼接）====================
PATH_TUNNEL_STATUS = "tunnel/status"
PATH_TUNNEL_CONNECTION = "tunnel/connection"
PATH_TUNNEL_START = "tunnel/start"
PATH_TUNNEL_STOP = "tunnel/stop"
PATH_TUNNEL_RESTART = "tunnel/restart"
PATH_TUNNEL_CONFIG = "tunnel/config"


def get_tunnel_status() -> Dict[str, Any]:
    """
    获取 Tunnel 状态。
    
    返回当前 Tunnel 的运行状态、连接信息和配置状态。
    
    返回:
        dict: Tunnel 状态信息
        
    异常:
        APIError: API 请求失败
    """
    client = get_api_client()
    return client.get(PATH_TUNNEL_STATUS)


def get_connection_info() -> Dict[str, Any]:
    """
    获取 Tunnel 连接信息。
    
    返回当前的连接 URL、域名和运行时间。
    
    返回:
        dict: 连接信息
        
    异常:
        APIError: API 请求失败
    """
    client = get_api_client()
    return client.get(PATH_TUNNEL_CONNECTION)


def start_tunnel() -> Dict[str, Any]:
    """
    启动 Tunnel。
    
    使用已配置的 Token 启动 Cloudflare Tunnel。
    
    返回:
        dict: 启动结果
        
    异常:
        APIError: API 请求失败
    """
    client = get_api_client()
    return client.post(PATH_TUNNEL_START)


def stop_tunnel() -> Dict[str, Any]:
    """
    停止 Tunnel。
    
    优雅地停止 Cloudflare Tunnel 连接。
    
    返回:
        dict: 停止结果
        
    异常:
        APIError: API 请求失败
    """
    client = get_api_client()
    return client.post(PATH_TUNNEL_STOP)


def restart_tunnel() -> Dict[str, Any]:
    """
    重启 Tunnel。
    
    停止并重新启动 Cloudflare Tunnel。
    
    返回:
        dict: 重启结果
        
    异常:
        APIError: API 请求失败
    """
    client = get_api_client()
    return client.post(PATH_TUNNEL_RESTART)


def configure_tunnel(token: str, domain: Optional[str] = None) -> Dict[str, Any]:
    """
    配置 Tunnel。
    
    保存 Tunnel Token 和域名配置。
    
    参数:
        token: Cloudflare Tunnel Token
        domain: 绑定的域名
        
    返回:
        dict: 配置结果
        
    异常:
        APIError: API 请求失败
    """
    client = get_api_client()
    data = {"token": token}
    if domain:
        data["domain"] = domain
    return client.post(PATH_TUNNEL_CONFIG, json=data)


def clear_tunnel_config() -> Dict[str, Any]:
    """
    清除 Tunnel 配置。
    
    删除保存的 Token 和域名配置。
    
    返回:
        dict: 清除结果
        
    异常:
        APIError: API 请求失败
    """
    client = get_api_client()
    headers = {}
    token = config.get_auth_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = client._client.delete(PATH_TUNNEL_CONFIG, headers=headers)
    return client._handle_response(response)


class TunnelAPI:
    """
    Tunnel API 封装类。
    
    提供更面向对象的 Tunnel 操作接口。
    """
    
    def __init__(self):
        self.client = get_api_client()
    
    @property
    def is_configured(self) -> bool:
        """检查是否已配置 Token。"""
        try:
            status = self.get_status()
            return status.get("token_configured", False)
        except Exception:
            return False
    
    @property
    def is_running(self) -> bool:
        """检查 Tunnel 是否正在运行。"""
        try:
            status = self.get_status()
            return status.get("is_running", False)
        except Exception:
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态。"""
        return self.client.get(PATH_TUNNEL_STATUS)

    def get_connection_info(self) -> Dict[str, Any]:
        """获取连接信息。"""
        return self.client.get(PATH_TUNNEL_CONNECTION)

    def start(self) -> Dict[str, Any]:
        """启动。"""
        return self.client.post(PATH_TUNNEL_START)

    def stop(self) -> Dict[str, Any]:
        """停止。"""
        return self.client.post(PATH_TUNNEL_STOP)

    def restart(self) -> Dict[str, Any]:
        """重启。"""
        return self.client.post(PATH_TUNNEL_RESTART)

    def configure(self, token: str, domain: Optional[str] = None) -> Dict[str, Any]:
        """配置。"""
        data = {"token": token}
        if domain:
            data["domain"] = domain
        return self.client.post(PATH_TUNNEL_CONFIG, json=data)
