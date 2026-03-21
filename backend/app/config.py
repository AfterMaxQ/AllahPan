"""
配置管理模块。

本模块提供AllahPan项目的所有配置参数，支持环境变量覆盖。
统一管理数据库路径、存储路径、Ollama配置、JWT配置等。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-19
"""

import os
import sys
from pathlib import Path
from typing import Optional


# ==================== Frozen 模式检测 ====================

# PyInstaller 打包后会设置 sys.frozen 属性
_FROZEN = getattr(sys, "frozen", False)
# 在 frozen 模式下，_MEIPASS 指向 bundle 内只读的临时目录
_MEIPASS = getattr(sys, "_MEIPASS", "")


# ==================== 路径配置 ====================

# 数据目录根路径
# Frozen 模式: 写入用户目录，避免写入 MEIPASS 只读临时目录
_APP_DIR = Path(__file__).resolve().parent
_BACKEND_ROOT = _APP_DIR.parent
_PROJECT_ROOT = _BACKEND_ROOT.parent

if _FROZEN:
    # 打包后使用用户目录下的 .allahpan 文件夹
    _USER_DATA_ROOT = Path.home() / ".allahpan"
    _USER_DATA_ROOT.mkdir(parents=True, exist_ok=True)
    DATA_DIR = _USER_DATA_ROOT / "data"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
else:
    # 开发模式: 使用项目根目录下的 data 文件夹
    PROJECT_ROOT = _PROJECT_ROOT
    DATA_DIR = PROJECT_ROOT / "data"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

# Web 前端静态目录（后端托管后，访问 / 即进网盘；可用 ALLAHPAN_WEB_DIR 覆盖）
# 打包后 frontend_web 与 backend 并列于 _MEIPASS 根下，不能用 backend 的父级的 frontend_web（不存在）
if os.environ.get("ALLAHPAN_WEB_DIR"):
    _web_dir = Path(os.environ.get("ALLAHPAN_WEB_DIR")).resolve()
elif _FROZEN and _MEIPASS:
    _web_dir = Path(_MEIPASS) / "frontend_web"
else:
    _web_dir = _PROJECT_ROOT / "frontend_web"
WEB_FRONTEND_DIR = _web_dir if _web_dir.exists() else None

# SQLite数据库文件路径
DB_NAME = os.environ.get("ALLAHPAN_DB_NAME", "allahpan.db")
DB_PATH = DATA_DIR / DB_NAME

# 文件存储目录（统一放在 ~/Documents/AllahPan/files，跨平台一致）
_DEFAULT_STORAGE = Path.home() / "Documents" / "AllahPan" / "files"
STORAGE_DIR = Path(os.environ.get("ALLAHPAN_STORAGE_DIR", str(_DEFAULT_STORAGE)))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# ChromaDB向量数据库路径
CHROMA_PERSIST_PATH = os.environ.get(
    "ALLAHPAN_CHROMA_PATH", str(DATA_DIR / "chroma_vectors")
)

# 向量相似度阈值（用于语义搜索过滤），可通过环境变量 ALLAHPAN_SIMILARITY_THRESHOLD 覆盖
SIMILARITY_THRESHOLD = float(os.environ.get("ALLAHPAN_SIMILARITY_THRESHOLD", "1.43"))


# ==================== Ollama配置 ====================

OLLAMA_BASE_URL = os.environ.get("ALLAHPAN_OLLAMA_URL", "http://localhost:11434")
OLLAMA_EMBEDDING_MODEL = os.environ.get(
    "ALLAHPAN_EMBEDDING_MODEL", "nomic-embed-text-v2-moe"
)
OLLAMA_VISION_MODEL = os.environ.get(
    "ALLAHPAN_VISION_MODEL", "qwen3-vl:4b"
)
# 图片/向量化请求可能较慢，默认 300 秒避免 ReadTimeout
OLLAMA_TIMEOUT = int(os.environ.get("ALLAHPAN_OLLAMA_TIMEOUT", "300"))

# 图片解析队列并发 worker 数，默认 1 减轻 Ollama 负载、减少 ReadTimeout
IMAGE_PARSER_WORKER_COUNT = int(os.environ.get("ALLAHPAN_IMAGE_PARSER_WORKERS", "1"))


# ==================== JWT配置 ====================

_DEFAULT_JWT_SECRET = "allahpan-dev-secret-change-in-production"
JWT_SECRET_KEY = os.environ.get(
    "ALLAHPAN_JWT_SECRET",
    os.environ.get("JWT_SECRET_KEY", _DEFAULT_JWT_SECRET)
)
JWT_ALGORITHM = "HS256"


def ensure_jwt_secret_for_production() -> None:
    """
    生产环境下禁止使用默认 JWT 密钥，启动时调用。
    若 ALLAHPAN_ENV=production 且密钥为默认值则抛出 RuntimeError。
    """
    env = os.environ.get("ALLAHPAN_ENV", "").lower()
    if env == "production" and (not JWT_SECRET_KEY or JWT_SECRET_KEY == _DEFAULT_JWT_SECRET):
        raise RuntimeError(
            "生产环境(ALLAHPAN_ENV=production)必须设置 ALLAHPAN_JWT_SECRET 或 JWT_SECRET_KEY，"
            "不能使用默认密钥。"
        )


# ==================== 文件上传配置 ====================

MAX_UPLOAD_SIZE = int(os.environ.get("ALLAHPAN_MAX_UPLOAD_MB", "100")) * 1024 * 1024


# ==================== CORS配置 ====================

# 允许的前端来源；远程通过 Tunnel 访问时需包含公网域名（如 https://allahpan.cn）
CORS_ORIGINS_STR = os.environ.get(
    "ALLAHPAN_CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173,"
    "https://allahpan.cn,http://allahpan.cn"
)
CORS_ALLOWED_ORIGINS = [o.strip() for o in CORS_ORIGINS_STR.split(",") if o.strip()]

# 允许任意 http(s) Origin（含局域网 IP、主机名），便于手机/其他电脑访问托管在同一后端的 Web SPA。
# 同源页面（http://本机IP:端口/）不依赖此项；拆域部署或 file:// 调试时可依赖正则。
# 未设置 ALLAHPAN_CORS_ORIGIN_REGEX 时使用宽松默认；设为空字符串则关闭正则，仅使用上方列表。
_cors_regex_raw = os.environ.get("ALLAHPAN_CORS_ORIGIN_REGEX")
if _cors_regex_raw is None:
    CORS_ORIGIN_REGEX: Optional[str] = r"https?://[^\s/?#]+(:\d+)?$"
elif _cors_regex_raw.strip() == "":
    CORS_ORIGIN_REGEX = None
else:
    CORS_ORIGIN_REGEX = _cors_regex_raw.strip()


# ==================== 服务配置 ====================

API_HOST = os.environ.get("ALLAHPAN_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("ALLAHPAN_PORT", "8000"))
DEBUG_MODE = os.environ.get("ALLAHPAN_DEBUG", "false").lower() == "true"

# 运维指标：不计入请求统计的路径前缀（逗号分隔），减轻 /health 等对曲线干扰
METRICS_EXCLUDE_PREFIXES = tuple(
    p.strip()
    for p in os.environ.get(
        "ALLAHPAN_METRICS_EXCLUDE_PREFIXES", "/health,/favicon.ico"
    ).split(",")
    if p.strip()
)


def get_storage_dir() -> Path:
    """获取文件存储目录的绝对路径。"""
    return STORAGE_DIR.resolve()


def get_db_path() -> Path:
    """获取数据库文件的绝对路径。"""
    return DB_PATH.resolve()


def get_chroma_path() -> Path:
    """获取ChromaDB持久化路径的绝对路径。"""
    return Path(CHROMA_PERSIST_PATH).resolve()


def get_base_path() -> Path:
    """获取应用基准路径。
    
    在 frozen 模式（PyInstaller 打包）下返回 bundle 所在目录，
    在开发模式下返回项目根目录。
    """
    if _FROZEN:
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent
