"""
AllahPan PySide6 桌面端配置模块。

本模块提供应用程序的所有配置常量，包括：
- API 地址配置
- 主题配色方案（macOS 风格 + 百度网盘模式）
- 视图配置
- 应用元数据

作者: AllahPan团队
创建日期: 2026-03-19
"""

import os
import sys
from pathlib import Path
from typing import Optional

__all__ = [
    "APP_NAME", "APP_VERSION", "APP_DESCRIPTION",
    "API_HOST", "API_PORT", "API_BASE_URL",
    "API_AUTH_LOGIN", "API_AUTH_REGISTER", "API_AUTH_ME",
    "API_FILES_LIST", "API_FILES_UPLOAD", "API_FILES_DETAIL",
    "API_AI_SEARCH", "API_AI_STATUS", "API_AI_PARSE",
    "API_SYSTEM_INFO", "API_SYSTEM_WATCHER",
    "WINDOW_MIN_WIDTH", "WINDOW_MIN_HEIGHT",
    "WINDOW_DEFAULT_WIDTH", "WINDOW_DEFAULT_HEIGHT",
    "GRID_ICON_SIZE", "GRID_ITEM_SIZE", "GRID_SPACING", "GRID_COLUMNS_MIN",
    "LIST_ROW_HEIGHT", "LIST_HEADER_HEIGHT",
    "SIDEBAR_WIDTH", "SIDEBAR_MIN_WIDTH", "SIDEBAR_MAX_WIDTH",
    "UPLOAD_QUEUE_MAX_CONCURRENT", "UPLOAD_PROGRESS_HEIGHT",
    "FILE_TYPE_CATEGORIES", "FILE_ICON_MAP",
    "get_file_category", "get_file_icon", "format_file_size",
    "ThemeColors",
    "set_auth_token", "get_auth_token", "set_auth_user", "get_auth_user", "clear_auth",
    "ThemeMode", "get_current_colors", "set_theme_mode", "init_theme",
    "_current_theme_mode",
    "_load_auth",
    "STORAGE_DIR",
    "resolve_app_icon_path",
    "SERVER_SETTINGS_PATH",
]

# ==================== 应用元数据 ====================
# 版本信息应与项目根目录 version.py 保持一致
APP_NAME = "AllahPan"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "家庭私有网盘"


def resolve_app_icon_path() -> Optional[Path]:
    """
    主窗口 / 任务栏使用的应用图标路径。
    优先使用 frontend_desktop/assets/app_icon.png（随 PyInstaller 一并打入 frontend_desktop）；
    开发时若未复制资源，可回退到仓库根目录 图标.png。
    """
    base = Path(__file__).resolve().parent
    for candidate in (base / "assets" / "app_icon.png", base.parent / "图标.png"):
        if candidate.is_file():
            return candidate
    return None


# 与 launcher.py 中 _apply_persistent_server_settings 使用的路径一致
SERVER_SETTINGS_PATH = Path.home() / ".allahpan" / "server_settings.json"

# ==================== API 配置 ====================
API_HOST = os.environ.get("ALLAHPAN_HOST", "localhost")
API_PORT = os.environ.get("ALLAHPAN_PORT", "8000")
API_BASE_URL = f"http://{API_HOST}:{API_PORT}/api/v1"

# ==================== 存储路径配置 ====================
# 与后端 backend/app/config.py 保持一致，统一使用 ~/Documents/AllahPan/files
_STORAGE_DEFAULT = Path.home() / "Documents" / "AllahPan" / "files"
STORAGE_DIR = Path(os.environ.get("ALLAHPAN_STORAGE_DIR", str(_STORAGE_DEFAULT)))

# API 端点
API_AUTH_LOGIN = f"{API_BASE_URL}/auth/login"
API_AUTH_REGISTER = f"{API_BASE_URL}/auth/register"
API_AUTH_ME = f"{API_BASE_URL}/auth/me"
API_FILES_LIST = f"{API_BASE_URL}/files/list"
API_FILES_UPLOAD = f"{API_BASE_URL}/files/upload"
API_FILES_DETAIL = f"{API_BASE_URL}/files"
API_AI_SEARCH = f"{API_BASE_URL}/ai/search"
API_AI_STATUS = f"{API_BASE_URL}/ai/status"
API_AI_PARSE = f"{API_BASE_URL}/ai/parse"
API_SYSTEM_INFO = f"{API_BASE_URL}/system/info"
API_SYSTEM_STORAGE = f"{API_BASE_URL}/system/storage"
API_SYSTEM_WATCHER = f"{API_BASE_URL}/system/watcher"
API_SYSTEM_SUMMARY = f"{API_BASE_URL}/system/summary"
API_SYSTEM_OLLAMA = f"{API_BASE_URL}/system/ollama"
API_TUNNEL_STATUS = f"{API_BASE_URL}/tunnel/status"
API_TUNNEL_START = f"{API_BASE_URL}/tunnel/start"
API_TUNNEL_STOP = f"{API_BASE_URL}/tunnel/stop"
API_TUNNEL_CONFIG = f"{API_BASE_URL}/tunnel/config"

# ==================== 窗口配置 ====================
WINDOW_MIN_WIDTH = 1200
WINDOW_MIN_HEIGHT = 800
WINDOW_DEFAULT_WIDTH = 1400
WINDOW_DEFAULT_HEIGHT = 900

# ==================== 视图配置 ====================
# 网格视图
GRID_ICON_SIZE = 80
GRID_ITEM_SIZE = 120
GRID_SPACING = 16
GRID_COLUMNS_MIN = 4

# 列表视图
LIST_ROW_HEIGHT = 44
LIST_HEADER_HEIGHT = 36

# 侧边栏
SIDEBAR_WIDTH = 256
SIDEBAR_MIN_WIDTH = 180
SIDEBAR_MAX_WIDTH = 280

# 上传队列
UPLOAD_QUEUE_MAX_CONCURRENT = 3
UPLOAD_PROGRESS_HEIGHT = 40

# ==================== 文件类型配置 ====================
FILE_TYPE_CATEGORIES = {
    "all": {"name": "全部文件", "icon": "folder", "types": None},
    "image": {"name": "图片", "icon": "image", "types": ["image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp", "image/svg+xml"]},
    "document": {"name": "文档", "icon": "document", "types": ["application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "text/plain", "text/html", "text/markdown"]},
    "video": {"name": "视频", "icon": "video", "types": ["video/mp4", "video/mpeg", "video/quicktime", "video/x-msvideo", "video/webm"]},
    "audio": {"name": "音频", "icon": "audio", "types": ["audio/mpeg", "audio/wav", "audio/ogg", "audio/flac", "audio/aac"]},
    "other": {"name": "其他", "icon": "other", "types": None},
}

# 文件图标映射
FILE_ICON_MAP = {
    "folder": "📁",
    "image": "🖼️",
    "document": "📄",
    "video": "🎬",
    "audio": "🎵",
    "compressed": "📦",
    "pdf": "📕",
    "word": "📘",
    "excel": "📊",
    "other": "📄",
}


def get_file_category(filetype: str) -> str:
    """根据文件 MIME 类型获取分类标识。"""
    if not filetype:
        return "other"
    
    for category, config in FILE_TYPE_CATEGORIES.items():
        if category == "all" or category == "other":
            continue
        if config["types"] and any(filetype.startswith(t.split("/")[0]) or filetype == t for t in config["types"]):
            return category
    
    return "other"


def get_file_icon(filetype: str) -> str:
    """根据文件 MIME 类型获取对应的 emoji 图标。"""
    if not filetype:
        return FILE_ICON_MAP["other"]
    if filetype in ("directory", "inode/directory") or (isinstance(filetype, str) and filetype.startswith("inode/directory")):
        return FILE_ICON_MAP["folder"]
    if filetype.startswith("image/"):
        return FILE_ICON_MAP["image"]
    elif filetype.startswith("video/"):
        return FILE_ICON_MAP["video"]
    elif filetype.startswith("audio/"):
        return FILE_ICON_MAP["audio"]
    elif "pdf" in filetype:
        return FILE_ICON_MAP["pdf"]
    elif "word" in filetype or "document" in filetype:
        return FILE_ICON_MAP["word"]
    elif "excel" in filetype or "spreadsheet" in filetype:
        return FILE_ICON_MAP["excel"]
    elif "zip" in filetype or "compressed" in filetype or "rar" in filetype or "tar" in filetype or "gzip" in filetype:
        return FILE_ICON_MAP["compressed"]
    
    return FILE_ICON_MAP["other"]


# MIME 类型到友好显示名称
FILE_TYPE_DISPLAY_NAMES = {
    "image/jpeg": "JPEG 图片",
    "image/png": "PNG 图片",
    "image/gif": "GIF 图片",
    "image/webp": "WebP 图片",
    "image/bmp": "BMP 图片",
    "image/svg+xml": "SVG 图片",
    "application/pdf": "PDF 文档",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word 文档",
    "application/msword": "Word 文档",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel 表格",
    "application/vnd.ms-excel": "Excel 表格",
    "text/plain": "文本文件",
    "text/markdown": "Markdown",
    "text/html": "HTML 文件",
    "video/mp4": "MP4 视频",
    "video/quicktime": "MOV 视频",
    "video/webm": "WebM 视频",
    "audio/mpeg": "MP3 音频",
    "audio/wav": "WAV 音频",
    "audio/ogg": "OGG 音频",
    "audio/flac": "FLAC 音频",
}


def get_file_type_display_name(filetype: str) -> str:
    """根据 MIME 类型返回友好显示名称。"""
    if not filetype:
        return "未知"
    if filetype in ("directory", "inode/directory") or (isinstance(filetype, str) and filetype.startswith("inode/directory")):
        return "文件夹"
    filetype = filetype.split(";")[0].strip()
    if filetype in FILE_TYPE_DISPLAY_NAMES:
        return FILE_TYPE_DISPLAY_NAMES[filetype]
    if filetype.startswith("image/"):
        return "图片"
    if filetype.startswith("video/"):
        return "视频"
    if filetype.startswith("audio/"):
        return "音频"
    if "pdf" in filetype:
        return "PDF 文档"
    if "word" in filetype or "document" in filetype:
        return "Word 文档"
    if "excel" in filetype or "spreadsheet" in filetype:
        return "Excel 表格"
    return filetype or "未知"


def format_file_size(size_bytes: int) -> str:
    """将字节数格式化为人类可读的大小字符串。"""
    if size_bytes <= 0:
        return "0 B"
    
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.2f} {units[unit_index]}"


# ==================== 主题配色方案 ====================
class ThemeColors:
    """主题颜色配置类。"""
    
    # 浅色主题（macOS 风格）
    LIGHT = {
        # 主色
        "primary": "#007AFF",
        "primary_hover": "#0056CC",
        "primary_light": "#E8F4FD",
        
        # 背景色
        "background": "#FFFFFF",
        "background_secondary": "#F5F5F7",
        "background_tertiary": "#EFEFF1",
        
        # 表面色（卡片、面板）
        "surface": "#FFFFFF",
        "surface_hover": "#F5F5F7",
        "surface_selected": "#E8F4FD",
        
        # 文字色
        "text_primary": "#1D1D1F",
        "text_secondary": "#86868B",
        "text_tertiary": "#6E6E73",
        
        # 边框色
        "border": "#D2D2D7",
        "border_light": "#E5E5EA",
        
        # 状态色
        "success": "#34C759",
        "warning": "#FF9500",
        "danger": "#FF3B30",
        "info": "#5AC8FA",
        
        # 侧边栏
        "sidebar_bg": "#F5F5F7",
        "sidebar_item_hover": "#E8E8ED",
        "sidebar_item_selected": "#E8F4FD",
        "sidebar_item_selected_border": "#007AFF",
        
        # 滚动条
        "scrollbar": "#C7C7CC",
        "scrollbar_hover": "#8E8E93",
        
        # 拖拽高亮
        "drop_highlight": "#007AFF",
        "drop_highlight_bg": "rgba(0, 122, 255, 0.1)",
        
        # 选中
        "selection": "#007AFF",
        "selection_bg": "rgba(0, 122, 255, 0.15)",
    }
    
    # 深色主题
    DARK = {
        # 主色
        "primary": "#0A84FF",
        "primary_hover": "#409CFF",
        "primary_light": "#1A3A5C",
        
        # 背景色
        "background": "#1C1C1E",
        "background_secondary": "#2C2C2E",
        "background_tertiary": "#3A3A3C",
        
        # 表面色（卡片、面板）
        "surface": "#2C2C2E",
        "surface_hover": "#3A3A3C",
        "surface_selected": "#1A3A5C",
        
        # 文字色
        "text_primary": "#FFFFFF",
        "text_secondary": "#98989D",
        "text_tertiary": "#8E8E93",
        
        # 边框色
        "border": "#3A3A3C",
        "border_light": "#48484A",
        
        # 状态色
        "success": "#30D158",
        "warning": "#FF9F0A",
        "danger": "#FF453A",
        "info": "#64D2FF",
        
        # 侧边栏
        "sidebar_bg": "#1C1C1E",
        "sidebar_item_hover": "#2C2C2E",
        "sidebar_item_selected": "#1A3A5C",
        "sidebar_item_selected_border": "#0A84FF",
        
        # 滚动条
        "scrollbar": "#545458",
        "scrollbar_hover": "#636366",
        
        # 拖拽高亮
        "drop_highlight": "#0A84FF",
        "drop_highlight_bg": "rgba(10, 132, 255, 0.2)",
        
        # 选中
        "selection": "#0A84FF",
        "selection_bg": "rgba(10, 132, 255, 0.25)",
    }


# ==================== 认证令牌管理（加密存储） ====================
import json as _json
import base64
import getpass
import hashlib

_AUTH_FILE = (Path.home() / ".allahpan" / "auth.json")
_AUTH_ENC_VERSION = 1  # 存储格式版本，便于日后迁移

_auth_token: Optional[str] = None
_auth_user: Optional[dict] = None


def _get_auth_fernet():
    """使用机器相关密钥创建 Fernet 实例，避免 token 明文落盘。"""
    try:
        from cryptography.fernet import Fernet
        raw = (str(Path.home()) + getpass.getuser() + "allahpan-auth-v1").encode()
        key = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
        return Fernet(key)
    except Exception:
        return None


def _encrypt_token(token: str) -> Optional[str]:
    """加密 token 为 base64 字符串，失败返回 None。"""
    f = _get_auth_fernet()
    if not f or not token:
        return None
    try:
        return f.encrypt(token.encode("utf-8")).decode("ascii")
    except Exception:
        return None


def _decrypt_token(encrypted: str) -> Optional[str]:
    """解密 token，失败返回 None。"""
    f = _get_auth_fernet()
    if not f or not encrypted:
        return None
    try:
        return f.decrypt(encrypted.encode("ascii")).decode("utf-8")
    except Exception:
        return None


def _load_auth() -> None:
    """从磁盘加载认证信息（支持明文兼容与加密格式）。"""
    global _auth_token, _auth_user
    if not _AUTH_FILE.exists():
        return
    try:
        with open(_AUTH_FILE, "r", encoding="utf-8") as f:
            data = _json.load(f)
        enc_version = data.get("_v", 0)
        raw_token = data.get("token")
        if enc_version == _AUTH_ENC_VERSION and isinstance(raw_token, str) and raw_token:
            _auth_token = _decrypt_token(raw_token)
        else:
            _auth_token = raw_token
        _auth_user = data.get("user")
        if not _auth_token:
            _auth_token = None
        if not _auth_user:
            _auth_user = None
    except Exception:
        _auth_token = None
        _auth_user = None


def _save_auth() -> None:
    """将认证信息加密后保存到磁盘。"""
    if _auth_token is None and _auth_user is None:
        if _AUTH_FILE.exists():
            try:
                _AUTH_FILE.unlink()
            except Exception:
                pass
        return
    _AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        enc_token = _encrypt_token(_auth_token) if _auth_token else None
        if enc_token:
            payload = {"_v": _AUTH_ENC_VERSION, "token": enc_token, "user": _auth_user}
        else:
            payload = {"_v": 0, "token": _auth_token, "user": _auth_user}
        with open(_AUTH_FILE, "w", encoding="utf-8") as f:
            _json.dump(payload, f)
    except Exception:
        pass


def set_auth_token(token: str) -> None:
    """设置认证令牌。"""
    global _auth_token
    _auth_token = token
    _save_auth()


def get_auth_token() -> Optional[str]:
    """获取认证令牌。"""
    return _auth_token


def set_auth_user(user: dict) -> None:
    """设置当前用户信息。"""
    global _auth_user
    _auth_user = user
    _save_auth()


def get_auth_user() -> Optional[dict]:
    """获取当前用户信息。"""
    return _auth_user


def clear_auth() -> None:
    """清除认证信息。"""
    global _auth_token, _auth_user
    _auth_token = None
    _auth_user = None
    if _AUTH_FILE.exists():
        try:
            _AUTH_FILE.unlink()
        except Exception:
            pass


# ==================== 主题模式管理 ====================
class ThemeMode:
    """主题模式枚举。"""
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


_current_theme_mode = ThemeMode.SYSTEM
_current_colors: dict = {}


def get_current_colors() -> dict:
    """获取当前主题颜色配置。"""
    global _current_colors
    return _current_colors


def set_theme_mode(mode: str) -> None:
    """设置主题模式。"""
    global _current_theme_mode, _current_colors
    
    if mode == ThemeMode.DARK:
        _current_colors = ThemeColors.DARK
    else:
        _current_colors = ThemeColors.LIGHT
    
    _current_theme_mode = mode


def init_theme() -> None:
    """初始化主题配置。"""
    set_theme_mode(ThemeMode.LIGHT)


# 初始化默认主题
init_theme()

# 从磁盘恢复认证状态
_load_auth()
