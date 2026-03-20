"""
目录监听器模块。

本模块提供DirectoryWatcher类，使用watchdog库实现文件系统监听功能。
监控指定目录下的文件变化事件，支持文件删除和移动检测，自动触发数据库清理。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-19
"""

from __future__ import annotations

import os
import time
import threading
from typing import Optional, TYPE_CHECKING

from watchdog.observers import Observer

from app.watcher.handler import FileDeletionEventHandler
from app.config import get_storage_dir

if TYPE_CHECKING:
    from app.database.sqlite import SQLite
    from app.database.chroma import ChromaDB

import logging

logger = logging.getLogger(__name__)


class DirectoryWatcher:
    """
    目录监听器类。

    使用watchdog库的Observer实现目录监听功能，监控用户存储目录下的
    文件删除和移动事件。当检测到文件变化时，自动调用事件处理器
    清理相关的数据库记录。

    主要功能：
    - 启动/停止目录监听
    - 自动创建监控目录
    - 线程安全的生命周期管理
    - 自动同步文件删除到数据库

    属性:
        watch_path: 监控的目录路径
        observer: watchdog的Observer实例
        event_handler: 文件事件处理器
        _running: 运行状态标志
        _lock: 线程锁
    """

    def __init__(
        self,
        watch_path: Optional[str] = None,
        sqlite_db: Optional["SQLite"] = None,
        chroma_db: Optional["ChromaDB"] = None
    ):
        """
        初始化目录监听器。

        参数:
            watch_path: 要监控的目录路径（默认使用config.STORAGE_DIR）
            sqlite_db: 可选的SQLite实例，未提供时使用共享实例
            chroma_db: 可选的ChromaDB实例，未提供时使用共享实例
        """
        resolved_path = watch_path if watch_path is not None else str(get_storage_dir())
        self.watch_path: str = os.path.abspath(resolved_path)
        self.observer: Observer | None = None
        self.event_handler: FileDeletionEventHandler | None = None
        self._running = False
        self._lock = threading.Lock()

        logger.info(f"DirectoryWatcher初始化，监控路径: {self.watch_path}")

        if not os.path.exists(self.watch_path):
            logger.warning(f"监控目录不存在，自动创建: {self.watch_path}")
            os.makedirs(self.watch_path, exist_ok=True)
            logger.info(f"监控目录创建成功: {self.watch_path}")

        self.event_handler = FileDeletionEventHandler(
            watch_path=self.watch_path,
            sqlite_db=sqlite_db,
            chroma_db=chroma_db
        )

    def start(self) -> bool:
        """
        启动目录监听。

        在新线程中启动watchdog的Observer，开始监听文件系统事件。
        如果监听器已经在运行，则不会重复启动。

        返回:
            bool: 启动成功返回True，否则返回False
        """
        with self._lock:
            if self._running:
                logger.warning("DirectoryWatcher已经在运行中，无需重复启动")
                return True

            try:
                if self.event_handler is None:
                    logger.error("事件处理器未初始化，无法启动监听器")
                    return False
                    
                observer = Observer()
                observer.schedule(
                    self.event_handler,
                    self.watch_path,
                    recursive=True
                )
                observer.start()
                self.observer = observer
                self._running = True
                logger.info(f"DirectoryWatcher启动成功，监控路径: {self.watch_path}")
                logger.info("目录监听服务已启动，正在监控文件变化...")
                return True

            except Exception as e:
                logger.error(f"DirectoryWatcher启动失败，错误: {e}")
                self._running = False
                return False

    def stop(self) -> bool:
        """
        停止目录监听。

        优雅地停止watchdog的Observer，等待观察线程安全退出。
        清理所有相关资源。

        返回:
            bool: 停止成功返回True，否则返回False
        """
        with self._lock:
            if not self._running:
                logger.warning("DirectoryWatcher未在运行，无需停止")
                return True

            if self.observer is None:
                logger.warning("Observer实例不存在，无需停止")
                self._running = False
                return True

            try:
                logger.info("正在停止DirectoryWatcher...")
                self.observer.stop()
                self.observer.join(timeout=5)
                
                if self.observer.is_alive():
                    logger.warning("Observer线程未能及时停止，强制终止")
                    self.observer = None
                else:
                    logger.info("Observer线程已正常停止")
                
                self._running = False
                logger.info("DirectoryWatcher已停止")
                return True

            except Exception as e:
                logger.error(f"停止DirectoryWatcher时发生错误: {e}")
                self._running = False
                return False

    def is_running(self) -> bool:
        """
        检查监听器是否正在运行。

        返回:
            bool: 正在运行返回True，否则返回False
        """
        with self._lock:
            return self._running and self.observer is not None and self.observer.is_alive()

    def get_status(self) -> dict:
        """
        获取监听器的详细状态信息。

        返回:
            dict: 包含运行状态、监控路径等信息的字典
        """
        with self._lock:
            status = {
                "running": self._running,
                "watch_path": self.watch_path,
                "observer_alive": self.observer.is_alive() if self.observer else False,
                "storage_dir": str(get_storage_dir())
            }
            logger.debug(f"DirectoryWatcher状态: {status}")
            return status

    def restart(self) -> bool:
        """
        重启目录监听器。

        先停止当前运行的监听器，然后重新启动。
        用于配置变更后重新加载等场景。

        返回:
            bool: 重启成功返回True，否则返回False
        """
        logger.info("正在重启DirectoryWatcher...")
        self.stop()
        time.sleep(0.5)
        return self.start()

    def __enter__(self):
        """
        上下文管理器入口。

        支持使用with语句自动管理监听器生命周期。
        
        返回:
            DirectoryWatcher: 自身实例
        """
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        上下文管理器退出。

        确保监听器在退出with块时正确停止。
        
        参数:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常追踪
        """
        logger.info("上下文管理器退出，自动停止DirectoryWatcher")
        self.stop()
