"""
AllahPan家庭私有网盘主应用模块。

本模块是FastAPI应用的入口点，负责初始化应用配置、注册中间件、
注册API路由以及管理应用生命周期。应用使用SQLite和ChromaDB双存储
架构，支持用户认证、文件管理、AI语义搜索、Ollama引擎管理和远程访问功能。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-20
"""

from contextlib import asynccontextmanager

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.v1 import auth, files, ai, system, tunnel
from app.config import (
    CORS_ALLOWED_ORIGINS,
    WEB_FRONTEND_DIR,
    get_storage_dir,
    OLLAMA_BASE_URL,
    ensure_jwt_secret_for_production,
)
from app.watcher.watcher import DirectoryWatcher
from app.services.image_parser import ImageParserQueue, set_image_parser_queue, get_image_parser_queue

import logging

logger = logging.getLogger(__name__)


_dirWatcher: DirectoryWatcher | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理器。
    
    该函数作为 FastAPI 的生命周期上下文管理器，在应用启动时初始化
    SQLite 数据库、ChromaDB 向量数据库、目录监听服务、图片解析队列、
    Ollama 引擎管理器（可选）、Tunnel 管理器（可选），
    在应用关闭时自动清理资源。
    
    参数:
        app: FastAPI 应用实例
    
    异常:
        Exception: 数据库初始化失败时抛出异常
    """
    global _dirWatcher

    ensure_jwt_secret_for_production()
    
    from app.api.v1.dependencies import get_db, get_chroma_db, get_file_repo, get_ollama
    
    logger.info("应用启动，开始初始化数据库...")
    get_db()
    get_chroma_db()
    logger.info("数据库初始化完成")
    
    logger.info("应用启动中，正在初始化目录监听服务...")
    _dirWatcher = DirectoryWatcher(watch_path=str(get_storage_dir()))
    watcher_started = _dirWatcher.start()
    if watcher_started:
        logger.info("目录监听服务启动成功")
    else:
        logger.error("目录监听服务启动失败，但应用将继续运行")
    
    from app.api.v1 import system
    system.set_watcher_instance(_dirWatcher)
    
    # 初始化并启动图片解析队列
    logger.info("应用启动中，正在初始化图片解析队列...")
    try:
        from app.config import IMAGE_PARSER_WORKER_COUNT
        file_repo = get_file_repo()
        ollama = get_ollama()
        image_parser_queue = ImageParserQueue(
            file_repo=file_repo,
            ollama=ollama,
            worker_count=IMAGE_PARSER_WORKER_COUNT,
        )
        await image_parser_queue.start()
        set_image_parser_queue(image_parser_queue)
        logger.info("图片解析队列启动成功")
    except Exception as e:
        logger.error(f"图片解析队列启动失败：{e}")
    
    # 初始化 Ollama 引擎管理器（仅当 Ollama 服务不可用时尝试启动）
    logger.info("应用启动中，正在检查 Ollama 引擎状态...")
    try:
        from app.services.ollama_manager import get_ollama_manager, OllamaStatus
        ollama_manager = get_ollama_manager()
        
        # 如果 Ollama 服务不可用，尝试启动
        if not ollama_manager.check_service_available():
            logger.info("Ollama 服务不可用，尝试启动...")
            # 不阻塞启动，自动在后台处理
            import threading
            def start_ollama_async():
                ollama_manager.start(timeout=120)
            threading.Thread(target=start_ollama_async, daemon=True).start()
        else:
            logger.info("Ollama 服务已运行")
        
        system.set_ollama_manager_instance(ollama_manager)
    except Exception as e:
        logger.error(f"Ollama 引擎管理器初始化失败：{e}")
    
    # 初始化 Tunnel 管理器
    logger.info("应用启动中，正在初始化 Tunnel 管理器...")
    try:
        from app.services.tunnel_manager import get_tunnel_manager
        from app.api.v1 import tunnel
        tunnel_manager = get_tunnel_manager()
        tunnel.set_tunnel_manager_instance(tunnel_manager)
        system.set_tunnel_manager_instance(tunnel_manager)
        logger.info("Tunnel 管理器初始化成功")
    except Exception as e:
        logger.error(f"Tunnel 管理器初始化失败：{e}")
    
    yield
    
    logger.info("应用关闭中，正在停止目录监听服务...")
    if _dirWatcher:
        _dirWatcher.stop()
        logger.info("目录监听服务已停止")
    
    logger.info("应用关闭中，正在停止图片解析队列...")
    image_parser = get_image_parser_queue()
    if image_parser:
        await image_parser.stop()
        logger.info("图片解析队列已停止")
    
    logger.info("应用关闭中，正在停止 Ollama 引擎...")
    try:
        from app.services.ollama_manager import shutdown_ollama_manager
        shutdown_ollama_manager()
        logger.info("Ollama 引擎已停止")
    except Exception as e:
        logger.error(f"停止 Ollama 引擎失败：{e}")
    
    logger.info("应用关闭中，正在停止 Tunnel...")
    try:
        from app.services.tunnel_manager import shutdown_tunnel_manager
        shutdown_tunnel_manager()
        logger.info("Tunnel 已停止")
    except Exception as e:
        logger.error(f"停止 Tunnel 失败：{e}")

    logger.info("应用关闭中，正在关闭数据库连接...")
    try:
        get_file_repo().close()
        logger.info("数据库连接已关闭")
    except Exception as e:
        logger.error(f"关闭数据库连接失败：{e}")
    
    logger.info("应用已关闭")


app = FastAPI(
    title="AllahPan API",
    version="1.0.0",
    description="AllahPan家庭私有网盘API",
    lifespan=lifespan,
)

logger.info("FastAPI应用初始化完成")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("CORS中间件配置完成")

app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(files.router, prefix="/api/v1/files", tags=["文件"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["AI"])
app.include_router(system.router, prefix="/api/v1/system", tags=["系统"])
app.include_router(tunnel.router, prefix="/api/v1/tunnel", tags=["远程访问"])

if WEB_FRONTEND_DIR:
    logger.info("Web 前端已启用，根路径将托管: %s", WEB_FRONTEND_DIR)
logger.info("API路由注册完成")


@app.get("/health", tags=["健康检查"])
async def health_check():
    """
    健康检查接口。
    
    该接口用于监控服务健康状态，返回详细的健康信息。
    
    返回:
        dict: 包含健康状态的字典
    """
    logger.debug("健康检查请求")
    return {"status": "healthy"}


def _serve_web_file(path: str) -> Optional[FileResponse]:
    """在 WEB_FRONTEND_DIR 下查找文件并返回，不存在或为目录则返回 None。"""
    if not WEB_FRONTEND_DIR:
        return None
    path = path.strip("/") or "index.html"
    # 禁止路径穿越
    if ".." in path or path.startswith("/"):
        return None
    full = (WEB_FRONTEND_DIR / path).resolve()
    if not full.is_file() or not str(full).startswith(str(WEB_FRONTEND_DIR.resolve())):
        return None
    return FileResponse(full)


@app.get("/", tags=["Web"])
async def root():
    """
    根路径：若已配置 Web 前端目录则返回 index.html（实现「访问隧道域名/ 即进网盘」），否则返回健康检查 JSON。
    """
    if WEB_FRONTEND_DIR:
        index = WEB_FRONTEND_DIR / "index.html"
        if index.is_file():
            return FileResponse(index)
    return {"status": "ok", "message": "AllahPan服务运行中"}


@app.get("/{full_path:path}", tags=["Web"])
async def serve_web(full_path: str):
    """
    托管 Web 前端静态资源（js、css 等）。若文件不存在则返回 index.html 以支持 SPA 前端路由。
    仅当配置了 WEB_FRONTEND_DIR 时生效；否则 404。
    """
    res = _serve_web_file(full_path)
    if res is not None:
        return res
    # SPA：任意未匹配路径返回 index.html
    if WEB_FRONTEND_DIR:
        index = WEB_FRONTEND_DIR / "index.html"
        if index.is_file():
            return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not Found")
