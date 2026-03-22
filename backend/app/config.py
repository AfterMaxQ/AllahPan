"""
配置管理模块。

本模块提供AllahPan项目的所有配置参数，支持环境变量覆盖。
统一管理数据库路径、存储路径、Ollama配置、JWT配置等。

用户数据根目录由 app.user_dirs.get_allahpan_user_root() 解析，可通过环境变量
ALLAHPAN_USER_DATA_ROOT 覆盖；打包或从 macOS .app 内运行时，数据库与向量库
写入该目录下的 data/，与应用程序包分离，便于升级重装。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-19
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

from app.user_dirs import get_allahpan_user_root, should_store_data_outside_bundle
from app.runtime_env import ensure_sqlite_temp_environment


# ==================== Frozen 模式检测 ====================

# PyInstaller 打包后会设置 sys.frozen 属性
_FROZEN = getattr(sys, "frozen", False)
# 在 frozen 模式下，_MEIPASS 指向 bundle 内只读的临时目录
_MEIPASS = getattr(sys, "_MEIPASS", "")


# ==================== 路径配置 ====================

# 数据目录根路径
# 打包或从 macOS .app 内运行时写入用户数据目录，避免写入 bundle / MEIPASS
_APP_DIR = Path(__file__).resolve().parent
_BACKEND_ROOT = _APP_DIR.parent
_PROJECT_ROOT = _BACKEND_ROOT.parent

if should_store_data_outside_bundle():
    _USER_DATA_ROOT = get_allahpan_user_root()
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

# 文件存储目录：环境变量 > server_settings.json 中的 storage_dir > 默认 ~/Documents/AllahPan/files
_DEFAULT_STORAGE = Path.home() / "Documents" / "AllahPan" / "files"
_PERSISTENT_SETTINGS = get_allahpan_user_root() / "server_settings.json"


def _storage_dir_from_settings_file() -> Optional[Path]:
    if not _PERSISTENT_SETTINGS.is_file():
        return None
    try:
        data = json.loads(_PERSISTENT_SETTINGS.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    raw = str(data.get("storage_dir") or "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


_env_sd = os.environ.get("ALLAHPAN_STORAGE_DIR", "").strip()
if _env_sd:
    STORAGE_DIR = Path(os.path.expanduser(_env_sd))
else:
    _from_file = _storage_dir_from_settings_file()
    STORAGE_DIR = _from_file if _from_file is not None else _DEFAULT_STORAGE

ensure_sqlite_temp_environment()

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

# 向量索引定期对齐线程：清理 Chroma 孤立文档、回填「已解析但缺向量」的图片（设 0 关闭）
INDEX_MAINTENANCE_INTERVAL_SEC = int(os.environ.get("ALLAHPAN_INDEX_MAINTENANCE_INTERVAL_SEC", "300"))
INDEX_MAINTENANCE_ENABLED = os.environ.get("ALLAHPAN_INDEX_MAINTENANCE", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)
# Chroma 分页扫描每页条数；孤立向量按批 delete
INDEX_MAINTENANCE_CHROMA_PAGE_SIZE = int(os.environ.get("ALLAHPAN_INDEX_MAINTENANCE_CHROMA_PAGE", "256"))
INDEX_MAINTENANCE_ORPHAN_DELETE_BATCH = int(os.environ.get("ALLAHPAN_INDEX_MAINTENANCE_ORPHAN_BATCH", "128"))
# 每轮最多入队多少张「缺向量」修复任务，避免拖垮 Ollama
INDEX_MAINTENANCE_REPAIR_MAX_PER_RUN = int(os.environ.get("ALLAHPAN_INDEX_MAINTENANCE_REPAIR_MAX", "5"))


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
