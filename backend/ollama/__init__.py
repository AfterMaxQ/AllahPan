"""
Ollama集成模块。

本模块提供Ollama推理引擎的Python封装和相关工具。
Ollama是本地AI推理框架，支持Qwen3-VL-4B等多模态模型。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-19
"""

from ollama.ollama_client import OllamaClient, get_ollama_client

__all__ = ["OllamaClient", "get_ollama_client"]
