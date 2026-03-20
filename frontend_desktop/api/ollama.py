"""
Ollama 与系统摘要 API 客户端模块。

提供 Ollama 状态、启停及系统摘要的 API 封装，与后端 /api/v1/system 路由对应。
"""

from typing import Any, Dict, Optional

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.client import get_api_client, APIError


# 相对 base_url 的路径，与 backend prefix /api/v1 拼接后为 /api/v1/system/ollama 等
PATH_OLLAMA_STATUS = "system/ollama"
PATH_OLLAMA_START = "system/ollama/start"
PATH_OLLAMA_STOP = "system/ollama/stop"
PATH_SYSTEM_SUMMARY = "system/summary"


def get_ollama_status() -> Dict[str, Any]:
    """
    获取 Ollama 引擎状态。
    返回字段含 service_available、is_running、loaded_models 等（与后端 OllamaStatusInfo 一致）。
    """
    client = get_api_client()
    return client.get(PATH_OLLAMA_STATUS)


def start_ollama() -> Dict[str, Any]:
    """请求后端启动 Ollama 引擎。"""
    client = get_api_client()
    return client.post(PATH_OLLAMA_START)


def stop_ollama() -> Dict[str, Any]:
    """请求后端停止 Ollama 引擎。"""
    client = get_api_client()
    return client.post(PATH_OLLAMA_STOP)


def get_system_summary() -> Dict[str, Any]:
    """获取系统状态摘要（存储、Watcher、Ollama、Tunnel 等）。"""
    client = get_api_client()
    return client.get(PATH_SYSTEM_SUMMARY)


class OllamaAPI:
    """Ollama API 封装类，与后端 /system/ollama 系列接口对应。"""

    def __init__(self):
        self.client = get_api_client()

    @property
    def is_running(self) -> bool:
        try:
            status = self.get_status()
            return status.get("is_running", False)
        except Exception:
            return False

    @property
    def is_available(self) -> bool:
        try:
            status = self.get_status()
            return status.get("service_available", False)
        except Exception:
            return False

    def get_status(self) -> Dict[str, Any]:
        return self.client.get(PATH_OLLAMA_STATUS)

    def start(self) -> Dict[str, Any]:
        return self.client.post(PATH_OLLAMA_START)

    def stop(self) -> Dict[str, Any]:
        return self.client.post(PATH_OLLAMA_STOP)

    def get_loaded_models(self) -> list:
        try:
            status = self.get_status()
            return status.get("loaded_models", [])
        except Exception:
            return []
