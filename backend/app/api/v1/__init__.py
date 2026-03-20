"""
API v1 模块。

本模块包含所有 API v1 版本的路由：
- auth: 认证接口
- files: 文件管理接口
- ai: AI 接口
- system: 系统接口
- tunnel: Tunnel 接口
"""

from app.api.v1 import auth, files, ai, system, tunnel

__all__ = ["auth", "files", "ai", "system", "tunnel"]
