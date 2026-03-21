"""
系统服务API模块。

本模块提供系统级别的API接口，包括存储空间信息查询、
存储目录状态检查、目录监听状态、Ollama引擎状态、
Tunnel状态等系统监控功能。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-20
"""

import shutil
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.v1.dependencies import get_current_user, AuthUser
from app.config import (
    CHROMA_PERSIST_PATH,
    DATA_DIR,
    DB_PATH,
    STORAGE_DIR,
    get_storage_dir,
)
from app.watcher.watcher import DirectoryWatcher
from app.services.image_parser import get_image_parser_queue

import logging

logger = logging.getLogger(__name__)


router = APIRouter()

# GET /summary 聚合磁盘、Ollama、Tunnel 等，开销大；短 TTL 缓存减轻多标签/多设备同时轮询时的压力
_summary_cache_lock = threading.Lock()
_summary_cache_mono: float = 0.0
_cached_summary: Optional[Any] = None
SUMMARY_CACHE_TTL_SEC = 10.0

_watcher_instance: Optional[DirectoryWatcher] = None
_ollama_manager_instance = None
_tunnel_manager_instance = None


def set_watcher_instance(watcher: DirectoryWatcher) -> None:
    """
    设置全局的DirectoryWatcher实例。
    
    该函数由main.py调用，用于将watcher实例注入到system模块中，
    以便API可以查询监听器状态。
    
    参数:
        watcher: DirectoryWatcher实例
    """
    global _watcher_instance
    _watcher_instance = watcher
    logger.info("DirectoryWatcher实例已注入到system模块")


def set_ollama_manager_instance(manager) -> None:
    """设置 Ollama 管理器实例。"""
    global _ollama_manager_instance
    _ollama_manager_instance = manager
    logger.info("OllamaManager实例已注入到system模块")


def set_tunnel_manager_instance(manager) -> None:
    """设置 Tunnel 管理器实例。"""
    global _tunnel_manager_instance
    _tunnel_manager_instance = manager
    logger.info("TunnelManager实例已注入到system模块")


class StorageInfo(BaseModel):
    """
    存储信息模型。
    
    属性:
        total_space: 总存储空间（字节）
        used_space: 已使用存储空间（字节）
        free_space: 剩余存储空间（字节）
        file_count: 文件数量
    """
    total_space: int
    used_space: int
    free_space: int
    file_count: int


class DirectoryInfo(BaseModel):
    """
    目录信息模型。
    
    属性:
        path: 目录绝对路径
        exists: 目录是否存在
        size: 目录总大小（字节）
    """
    path: str
    exists: bool
    size: int


@router.get("/info", response_model=StorageInfo)
def get_storage_info(
    current_user: AuthUser = Depends(get_current_user),
):
    """
    获取存储空间信息接口。
    
    该接口查询存储目录的总空间、已用空间、剩余空间和文件数量，
    用于系统监控和用户展示。
    
    参数:
        current_user: 当前认证用户（通过依赖注入获取）
    
    返回:
        StorageInfo: 包含存储空间信息的对象
    """
    logger.debug(f"查询存储空间信息，用户: {current_user.username}")
    if not STORAGE_DIR.exists():
        logger.info("存储目录不存在，返回零值存储信息")
        return StorageInfo(
            total_space=0,
            used_space=0,
            free_space=0,
            file_count=0,
        )

    def _dir_size(p: Path) -> int:
        """统计目录下所有文件的实际占用字节数。"""
        total = 0
        try:
            for entry in p.rglob("*"):
                if entry.is_file():
                    try:
                        total += entry.stat().st_size
                    except OSError:
                        pass
        except OSError:
            pass
        return total

    disk_total, _, disk_free = shutil.disk_usage(STORAGE_DIR)
    used_space = _dir_size(STORAGE_DIR) if STORAGE_DIR.is_dir() else 0
    file_count = len(list(STORAGE_DIR.iterdir())) if STORAGE_DIR.is_dir() else 0

    logger.info(
        f"存储空间信息: 磁盘总={disk_total}字节, 目录已用={used_space}字节, 磁盘剩余={disk_free}字节, 文件数={file_count}"
    )
    return StorageInfo(
        total_space=disk_total,
        used_space=used_space,
        free_space=disk_free,
        file_count=file_count,
    )


@router.get("/storage", response_model=DirectoryInfo)
def get_storage_directory(
    current_user: AuthUser = Depends(get_current_user),
):
    """
    获取存储目录信息接口。
    
    该接口返回存储目录的路径、存在状态和目录大小，
    用于确认存储配置是否正确。
    
    参数:
        current_user: 当前认证用户（通过依赖注入获取）
    
    返回:
        DirectoryInfo: 包含目录信息的对象
    """
    logger.debug(f"查询存储目录信息，用户: {current_user.username}")
    directory_size = _get_directory_size(STORAGE_DIR) if STORAGE_DIR.exists() else 0
    logger.info(f"存储目录信息: 路径={STORAGE_DIR.absolute()}, 存在={STORAGE_DIR.exists()}, 大小={directory_size}字节")
    return DirectoryInfo(
        path=str(STORAGE_DIR.absolute()),
        exists=STORAGE_DIR.exists(),
        size=directory_size,
    )


def _get_directory_size(path: Path) -> int:
    """
    递归计算目录的总大小。
    
    该函数遍历目录中的所有文件，累加文件大小，
    返回目录的总占用空间。
    
    参数:
        path: 目录路径对象
    
    返回:
        int: 目录总大小（字节）
    """
    logger.debug(f"计算目录大小: {path}")
    total = 0
    if path.is_file():
        logger.debug(f"文件大小: {path} = {path.stat().st_size}字节")
        return path.stat().st_size
    for item in path.rglob("*"):
        if item.is_file():
            size = item.stat().st_size
            total += size
    logger.debug(f"目录大小计算完成: {path} = {total}字节")
    return total


class WatcherStatus(BaseModel):
    """
    监听器状态模型。
    
    属性:
        running: 监听器是否正在运行
        watch_path: 监控的目录路径
        observer_alive: Observer 线程是否存活
    """
    running: bool
    watch_path: str
    observer_alive: bool


class ImageParserQueueStatus(BaseModel):
    """
    图片解析队列状态模型。
    
    属性:
        queue_size: 队列中待处理文件数量
        processing_count: 正在处理的文件数量
        worker_count: worker 数量
        total_processed: 总处理数量
        total_failed: 总失败数量
        is_running: 队列是否正在运行
    """
    queue_size: int
    processing_count: int
    worker_count: int
    total_processed: int
    total_failed: int
    is_running: bool


class OllamaStatusInfo(BaseModel):
    """
    Ollama 引擎状态模型。
    
    属性:
        status: 引擎状态
        is_running: 是否正在运行
        host: 监听地址
        port: 监听端口
        uptime: 运行时间（秒）
        restart_count: 重启次数
        process_pid: 进程 PID
        error: 错误信息
        port_in_use: 端口是否被占用
        service_available: 服务是否可用
        loaded_models: 已加载的模型列表
    """
    status: str
    is_running: bool
    host: str
    port: int
    uptime: Optional[float] = None
    restart_count: int = 0
    process_pid: Optional[int] = None
    error: Optional[str] = None
    port_in_use: bool = False
    service_available: bool = False
    loaded_models: list = []


class TunnelStatusInfo(BaseModel):
    """
    Tunnel 状态模型。
    
    属性:
        status: Tunnel 状态
        is_running: 是否正在运行
        uptime: 运行时间（秒）
        reconnect_count: 重连次数
        domain: 绑定的域名
        connection_url: 连接 URL
        tunnel_id: Tunnel ID
        token_configured: Token 是否已配置
        auto_reconnect: 是否启用自动重连
        process_pid: 进程 PID
        error: 错误信息
    """
    status: str
    is_running: bool
    uptime: Optional[float] = None
    reconnect_count: int = 0
    domain: Optional[str] = None
    connection_url: Optional[str] = None
    tunnel_id: Optional[str] = None
    token_configured: bool = False
    auto_reconnect: bool = True
    process_pid: Optional[int] = None
    error: Optional[str] = None


class SystemStatusSummary(BaseModel):
    """
    系统状态摘要模型。
    
    属性:
        storage: 存储信息
        ollama: Ollama 引擎状态
        tunnel: Tunnel 状态
        watcher: 监听器状态
        image_parser: 图片解析队列状态
    """
    storage: StorageInfo
    ollama: OllamaStatusInfo
    tunnel: TunnelStatusInfo
    watcher: WatcherStatus
    image_parser: ImageParserQueueStatus


@router.get("/watcher", response_model=WatcherStatus)
def get_watcher_status(
    current_user: AuthUser = Depends(get_current_user),
):
    """
    获取目录监听器状态接口。
    
    该接口返回目录监听器（watcher）的当前运行状态，
    包括是否运行中、监控路径等信息。
    
    参数:
        current_user: 当前认证用户（通过依赖注入获取）
    
    返回:
        WatcherStatus: 包含监听器状态的对象
    """
    logger.debug(f"查询目录监听器状态，用户: {current_user.username}")
    
    if _watcher_instance is None:
        logger.warning("DirectoryWatcher实例未初始化")
        return WatcherStatus(
            running=False,
            watch_path=str(STORAGE_DIR.absolute()),
            observer_alive=False,
        )
    
    status = _watcher_instance.get_status()
    logger.info(f"目录监听器状态: 运行中={status['running']}, 路径={status['watch_path']}")
    
    return WatcherStatus(
        running=status["running"],
        watch_path=status["watch_path"],
        observer_alive=status["observer_alive"],
    )


@router.get("/image-parser-queue", response_model=ImageParserQueueStatus)
def get_image_parser_queue_status(
    current_user: AuthUser = Depends(get_current_user),
):
    """
    获取图片解析队列状态接口。
    
    该接口返回图片解析队列的当前运行状态，
    包括队列长度、处理中数量、总处理数等信息。
    
    参数:
        current_user: 当前认证用户（通过依赖注入获取）
    
    返回:
        ImageParserQueueStatus: 包含队列状态的对象
    """
    logger.debug(f"查询图片解析队列状态，用户：{current_user.username}")
    
    image_parser = get_image_parser_queue()
    
    if image_parser is None:
        logger.warning("ImageParserQueue 实例未初始化")
        return ImageParserQueueStatus(
            queue_size=0,
            processing_count=0,
            worker_count=0,
            total_processed=0,
            total_failed=0,
            is_running=False,
        )
    
    status = image_parser.get_status()
    logger.info(
        f"图片解析队列状态：队列大小={status['queue_size']}, "
        f"处理中={status['processing_count']}, 总处理={status['total_processed']}"
    )
    
    return ImageParserQueueStatus(**status)


@router.get("/ollama", response_model=OllamaStatusInfo)
def get_ollama_status(
    current_user: AuthUser = Depends(get_current_user),
):
    """
    获取 Ollama 引擎状态接口。
    
    该接口返回 Ollama 引擎的当前运行状态，
    包括进程状态、已加载模型等信息。
    
    参数:
        current_user: 当前认证用户（通过依赖注入获取）
    
    返回:
        OllamaStatusInfo: 包含 Ollama 状态的对象
    """
    logger.debug(f"查询 Ollama 引擎状态，用户: {current_user.username}")
    
    if _ollama_manager_instance is None:
        logger.warning("OllamaManager实例未初始化")
        return OllamaStatusInfo(
            status="unknown",
            is_running=False,
            host="localhost",
            port=11434,
        )
    
    status_info = _ollama_manager_instance.get_status_info(include_models=True)
    
    logger.info(f"Ollama 引擎状态: {status_info['status']}")
    return OllamaStatusInfo(**status_info)


@router.post("/ollama/start")
def start_ollama(
    current_user: AuthUser = Depends(get_current_user),
):
    """
    启动 Ollama 引擎接口。
    
    该接口尝试启动本地 Ollama 引擎。
    
    参数:
        current_user: 当前认证用户（通过依赖注入获取）
    
    返回:
        dict: 启动结果
    """
    logger.info(f"用户请求启动 Ollama: {current_user.username}")
    
    if _ollama_manager_instance is None:
        return {"success": False, "message": "Ollama管理器未初始化"}
    
    if _ollama_manager_instance.is_running:
        return {"success": True, "message": "Ollama已在运行"}
    
    success = _ollama_manager_instance.start(timeout=120)
    return {
        "success": success,
        "message": "Ollama启动成功" if success else "Ollama启动失败"
    }


@router.post("/ollama/stop")
def stop_ollama(
    current_user: AuthUser = Depends(get_current_user),
):
    """
    停止 Ollama 引擎接口。
    
    该接口停止本地 Ollama 引擎。
    
    参数:
        current_user: 当前认证用户（通过依赖注入获取）
    
    返回:
        dict: 停止结果
    """
    logger.info(f"用户请求停止 Ollama: {current_user.username}")
    
    if _ollama_manager_instance is None:
        return {"success": False, "message": "Ollama管理器未初始化"}
    
    success = _ollama_manager_instance.stop()
    return {
        "success": success,
        "message": "Ollama已停止" if success else "停止失败"
    }


@router.get("/tunnel", response_model=TunnelStatusInfo)
def get_tunnel_status(
    current_user: AuthUser = Depends(get_current_user),
):
    """
    获取 Tunnel 状态接口。
    
    该接口返回 Cloudflare Tunnel 的当前运行状态。
    
    参数:
        current_user: 当前认证用户（通过依赖注入获取）
    
    返回:
        TunnelStatusInfo: 包含 Tunnel 状态的对象
    """
    logger.debug(f"查询 Tunnel 状态，用户: {current_user.username}")
    
    if _tunnel_manager_instance is None:
        logger.warning("TunnelManager实例未初始化")
        return TunnelStatusInfo(
            status="unknown",
            is_running=False,
        )
    
    status_info = _tunnel_manager_instance.get_status_info()
    logger.info(f"Tunnel 状态: {status_info['status']}")
    return TunnelStatusInfo(**status_info)


@router.get("/summary", response_model=SystemStatusSummary)
def get_system_status_summary(
    current_user: AuthUser = Depends(get_current_user),
):
    """
    获取系统状态摘要接口。
    
    该接口返回所有系统组件的状态摘要，
    包括存储、Ollama、Tunnel、监听器、图片解析队列。
    
    参数:
        current_user: 当前认证用户（通过依赖注入获取）
    
    返回:
        SystemStatusSummary: 包含所有系统状态的摘要对象
    """
    global _summary_cache_mono, _cached_summary
    logger.debug(f"查询系统状态摘要，用户: {current_user.username}")
    now = time.monotonic()
    with _summary_cache_lock:
        if _cached_summary is not None and (now - _summary_cache_mono) < SUMMARY_CACHE_TTL_SEC:
            logger.debug("系统状态摘要缓存命中")
            return _cached_summary

    # 获取存储信息（避免异常导致 500，影响前端定时刷新）
    try:
        if STORAGE_DIR.exists():
            total, used, free = shutil.disk_usage(STORAGE_DIR)
            if STORAGE_DIR.is_dir():
                try:
                    file_count = sum(1 for _ in STORAGE_DIR.iterdir())
                except OSError:
                    file_count = 0
            else:
                file_count = 0
        else:
            total = used = free = file_count = 0
        storage = StorageInfo(
            total_space=total,
            used_space=used,
            free_space=free,
            file_count=file_count,
        )
    except Exception as e:
        logger.warning("获取存储信息失败: %s", e, exc_info=True)
        storage = StorageInfo(total_space=0, used_space=0, free_space=0, file_count=0)
    
    # 获取 Ollama 状态（一次性获取，避免重复 HTTP 调用）
    try:
        if _ollama_manager_instance:
            ollama_info = _ollama_manager_instance.get_status_info(include_models=True)
        else:
            ollama_info = {
                "status": "unknown",
                "is_running": False,
                "host": "localhost",
                "port": 11434,
                "loaded_models": [],
            }
        ollama = OllamaStatusInfo(**ollama_info)
    except Exception as e:
        logger.warning("获取 Ollama 状态失败: %s", e, exc_info=True)
        ollama = OllamaStatusInfo(
            status="error", is_running=False, host="localhost", port=11434, loaded_models=[],
        )
    
    # 获取 Tunnel 状态
    try:
        if _tunnel_manager_instance:
            tunnel_info = _tunnel_manager_instance.get_status_info()
        else:
            tunnel_info = {"status": "unknown", "is_running": False}
        tunnel = TunnelStatusInfo(**tunnel_info)
    except Exception as e:
        logger.warning("获取 Tunnel 状态失败: %s", e, exc_info=True)
        tunnel = TunnelStatusInfo(status="error", is_running=False)
    
    # 获取监听器状态
    try:
        if _watcher_instance:
            watcher_info = _watcher_instance.get_status()
        else:
            watcher_info = {
                "running": False,
                "watch_path": str(STORAGE_DIR.absolute()),
                "observer_alive": False,
            }
        watcher = WatcherStatus(**watcher_info)
    except Exception as e:
        logger.warning("获取监听器状态失败: %s", e, exc_info=True)
        watcher = WatcherStatus(
            running=False, watch_path=str(STORAGE_DIR.absolute()), observer_alive=False,
        )
    
    # 获取图片解析队列状态
    try:
        image_parser = get_image_parser_queue()
        if image_parser:
            parser_status = image_parser.get_status()
        else:
            parser_status = {
                "queue_size": 0,
                "processing_count": 0,
                "worker_count": 0,
                "total_processed": 0,
                "total_failed": 0,
                "is_running": False,
            }
        image_parser_status = ImageParserQueueStatus(**parser_status)
    except Exception as e:
        logger.warning("获取图片解析队列状态失败: %s", e, exc_info=True)
        image_parser_status = ImageParserQueueStatus(
            queue_size=0, processing_count=0, worker_count=0,
            total_processed=0, total_failed=0, is_running=False,
        )
    
    result = SystemStatusSummary(
        storage=storage,
        ollama=ollama,
        tunnel=tunnel,
        watcher=watcher,
        image_parser=image_parser_status,
    )
    with _summary_cache_lock:
        _summary_cache_mono = time.monotonic()
        _cached_summary = result
    logger.info("系统状态摘要获取成功")
    return result


def _path_size_bytes(path: Path) -> int:
    """目录或文件占用字节数（递归目录）。"""
    if not path.exists():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    try:
        for child in path.rglob("*"):
            if child.is_file():
                try:
                    total += child.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


@router.get("/metrics/traffic")
def get_metrics_traffic(
    current_user: AuthUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """运维：最近最多 120 分钟的请求量（按 API 分类聚合）。"""
    from app.observability.traffic_stats import get_traffic_snapshot

    return get_traffic_snapshot()


@router.get("/metrics/data-volumes")
def get_metrics_data_volumes(
    current_user: AuthUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """运维：数据库、向量库、数据目录等占用体积。"""
    db_p = DB_PATH.resolve()
    chroma_p = Path(CHROMA_PERSIST_PATH).resolve()
    data_p = DATA_DIR.resolve()
    storage_p = STORAGE_DIR.resolve()
    return {
        "database_bytes": _path_size_bytes(db_p) if db_p.exists() else 0,
        "chroma_bytes": _path_size_bytes(chroma_p) if chroma_p.exists() else 0,
        "data_dir_bytes": _path_size_bytes(data_p) if data_p.is_dir() else 0,
        "storage_dir_bytes": _path_size_bytes(storage_p) if storage_p.exists() else 0,
        "paths": {
            "database": str(db_p),
            "chroma": str(chroma_p),
            "data_dir": str(data_p),
            "storage_dir": str(storage_p),
        },
    }


@router.get("/logs/tail")
def get_logs_tail(
    lines: int = 300,
    current_user: AuthUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """运维：读取 ~/.allahpan/logs 下最近修改的 .log 文件末尾若干行。"""
    n = max(1, min(int(lines), 2000))
    log_dir = Path.home() / ".allahpan" / "logs"
    if not log_dir.is_dir():
        return {"path": None, "lines": [], "raw": "", "message": "日志目录不存在"}
    log_files = sorted(log_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not log_files:
        return {"path": None, "lines": [], "raw": "", "message": "暂无 .log 文件"}
    latest = log_files[0]
    try:
        text = latest.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {"path": str(latest), "lines": [], "raw": "", "message": f"读取失败: {e}"}
    all_lines: List[str] = text.splitlines()
    tail = all_lines[-n:] if len(all_lines) > n else all_lines
    return {
        "path": str(latest.resolve()),
        "lines": tail,
        "raw": "\n".join(tail),
        "message": None,
    }
