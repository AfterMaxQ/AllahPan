"""
服务层模块。

本模块包含各种业务逻辑服务，如图片解析队列、Ollama引擎管理、Tunnel管理等。
"""

from app.services.image_parser import ImageParserQueue
from app.services.ollama_manager import OllamaManager, OllamaStatus, get_ollama_manager, shutdown_ollama_manager
from app.services.tunnel_manager import TunnelManager, TunnelStatus, get_tunnel_manager, shutdown_tunnel_manager

__all__ = [
    "ImageParserQueue",
    "OllamaManager",
    "OllamaStatus",
    "get_ollama_manager",
    "shutdown_ollama_manager",
    "TunnelManager",
    "TunnelStatus",
    "get_tunnel_manager",
    "shutdown_tunnel_manager",
]
