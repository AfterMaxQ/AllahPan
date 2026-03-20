"""
文件删除事件处理器模块。

本模块实现watchdog文件系统的事件处理器，用于捕获文件删除和移动事件，
并自动清理相关的数据库记录。当用户在Finder中删除文件时，系统自动
同步清理SQLite元数据和ChromaDB向量索引。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-19
"""

from __future__ import annotations

import os
from typing import Optional, TYPE_CHECKING

import mimetypes
from watchdog.events import (
    FileSystemEventHandler,
    FileCreatedEvent,
    FileDeletedEvent,
    FileMovedEvent,
    FileModifiedEvent,
)

from app.database.repositories.file_repository import FileRepository
from app.models.file_metadata import FileMetadata

if TYPE_CHECKING:
    from app.database.sqlite import SQLite
    from app.database.chroma import ChromaDB

import logging

logger = logging.getLogger(__name__)


class FileDeletionEventHandler(FileSystemEventHandler):
    """
    文件删除事件处理器类。
    
    继承watchdog的FileSystemEventHandler，用于监听文件系统变化事件。
    当检测到文件被删除或移动出监控目录时，自动清理相关的数据库记录。
    
    处理的事件类型：
    - FileDeletedEvent: 文件被删除
    - FileMovedEvent: 文件被移动（从监控目录移出视为删除）
    - FileModifiedEvent: 文件被修改（可选：更新元数据）
    
    属性:
        watch_path: 监控的根目录路径
        sqlite: SQLite数据库实例
        chroma: ChromaDB向量数据库实例
        file_repo: 文件仓库实例
    """

    def __init__(
        self,
        watch_path: str = "./data/files",
        sqlite_db: Optional["SQLite"] = None,
        chroma_db: Optional["ChromaDB"] = None
    ):
        """
        初始化文件删除事件处理器。
        
        参数:
            watch_path: 要监控的目录路径（默认使用config.STORAGE_DIR）
            sqlite_db: 可选的SQLite实例，未提供时使用共享实例
            chroma_db: 可选的ChromaDB实例，未提供时使用共享实例
        """
        super().__init__()
        self.watch_path = os.path.abspath(watch_path)
        if sqlite_db is not None:
            self.sqlite = sqlite_db
        else:
            from app.api.v1.dependencies import get_db
            self.sqlite = get_db()
        if chroma_db is not None:
            self.chroma = chroma_db
        else:
            from app.api.v1.dependencies import get_chroma_db
            self.chroma = get_chroma_db()
        self.file_repo = FileRepository(sqlite_db=self.sqlite, chroma_db=self.chroma)
        logger.info(f"FileDeletionEventHandler初始化完成，监控路径: {self.watch_path}")

    def _get_file_by_path(self, file_path: str) -> Optional[dict]:
        """
        根据文件路径查找数据库中的文件记录。
        
        参数:
            file_path: 文件的绝对路径
        
        返回:
            Optional[dict]: 找到的文件元数据字典，未找到返回None
        """
        abs_path = os.path.abspath(file_path)
        logger.debug(f"根据路径查找文件记录: {abs_path}")
        
        file_meta = self.file_repo.get_file_metadata_by_filepath(abs_path)
        if file_meta:
            logger.debug(f"找到匹配的文件记录: {file_meta.filename}，ID: {file_meta.file_id}")
            return {
                "file_id": file_meta.file_id,
                "filename": file_meta.filename,
                "filepath": file_meta.filepath,
                "filetype": file_meta.filetype,
                "size": file_meta.size,
                "is_ai_parsed": file_meta.is_ai_parsed
            }
        
        logger.debug(f"未找到文件记录: {abs_path}")
        return None

    def _get_default_user_id(self) -> Optional[str]:
        """获取用于文件系统新建文件的默认用户 ID（取第一个用户）。"""
        try:
            self.sqlite.cursor.execute("SELECT id FROM users LIMIT 1")
            row = self.sqlite.cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            logger.warning(f"获取默认用户失败: {e}")
            return None

    def _add_file_record(self, file_path: str) -> bool:
        """将磁盘上的新文件加入数据库（Finder 新建/拖入后同步）。"""
        abs_path = os.path.abspath(file_path)
        if not os.path.isfile(abs_path):
            return False
        if self.file_repo.get_file_metadata_by_filepath(abs_path):
            return True
        user_id = self._get_default_user_id()
        if not user_id:
            logger.warning("无可用用户，跳过新建文件入库")
            return False
        try:
            size = os.path.getsize(abs_path)
            filename = os.path.basename(abs_path)
            mt, _ = mimetypes.guess_type(filename)
            filetype = mt or "application/octet-stream"
            meta = FileMetadata(
                filename=filename,
                filepath=abs_path,
                size=size,
                filetype=filetype,
                userid=user_id,
                is_ai_parsed=False,
            )
            self.file_repo.create_file_metadata(meta)
            logger.info(f"Watcher 新建文件入库: {filename}, file_id={meta.file_id}")
            return True
        except Exception as e:
            logger.error(f"新建文件入库失败 {abs_path}: {e}")
            return False

    def _cleanup_file_record(self, file_info: dict) -> bool:
        """
        清理文件的数据库记录。
        
        先删 SQLite 元数据再删 ChromaDB 向量，避免向量已删而元数据未删的不一致。
        
        参数:
            file_info: 包含文件ID等信息的字典
        
        返回:
            bool: 清理成功返回True，否则返回False
        """
        file_id = file_info["file_id"]
        filename = file_info["filename"]
        
        logger.info(f"开始清理文件数据库记录，文件ID: {file_id}，文件名: {filename}")
        
        try:
            sqlite_deleted = self.sqlite.delete_file_metadata(file_id)
            if not sqlite_deleted:
                logger.warning(f"SQLite中未找到元数据记录，文件ID: {file_id}")
                return False
            logger.info(f"SQLite元数据删除成功，文件ID: {file_id}")
            try:
                self.chroma.delete_vector(file_id)
                logger.info(f"ChromaDB向量删除成功，文件ID: {file_id}")
            except Exception as ce:
                logger.warning(f"ChromaDB向量删除失败（元数据已删），文件ID: {file_id}，错误: {ce}")
            return True
        except Exception as e:
            logger.error(f"清理文件记录时发生错误，文件ID: {file_id}，错误: {e}")
            return False

    def on_deleted(self, event: FileDeletedEvent) -> None:
        """
        处理文件删除事件。
        
        当文件被删除时，根据文件路径查找数据库记录并清理。
        
        参数:
            event: watchdog的FileDeletedEvent事件对象
        """
        if event.is_directory:
            logger.debug(f"忽略目录删除事件: {event.src_path}")
            return
        
        file_path = str(event.src_path)
        logger.info(f"检测到文件删除事件: {file_path}")
        
        file_info = self._get_file_by_path(file_path)
        if file_info is None:
            logger.warning(f"文件不在数据库中，无需清理: {file_path}")
            return
        
        success = self._cleanup_file_record(file_info)
        if success:
            logger.info(f"文件删除同步完成，文件名: {file_info['filename']}")
        else:
            logger.error(f"文件删除同步失败，文件名: {file_info['filename']}")

    def on_created(self, event: FileCreatedEvent) -> None:
        """
        处理文件新建事件。
        当用户在 Finder 中新建或拖入文件时，自动加入数据库，便于列表与预览。
        """
        if event.is_directory:
            logger.debug(f"忽略目录创建事件: {event.src_path}")
            return
        file_path = str(event.src_path)
        if not str(os.path.abspath(file_path)).startswith(str(self.watch_path)):
            return
        logger.info(f"检测到文件新建事件: {file_path}")
        self._add_file_record(file_path)

    def on_moved(self, event: FileMovedEvent) -> None:
        """
        处理文件移动事件。
        
        当文件被移动出监控目录时，视为删除，执行清理逻辑。
        如果文件仍在监控目录内移动，则忽略。
        
        参数:
            event: watchdog的FileMovedEvent事件对象
        """
        if event.is_directory:
            logger.debug(f"忽略目录移动事件: {event.src_path} -> {event.dest_path}")
            return
        
        src_path = str(event.src_path)
        dest_path = str(event.dest_path)
        
        logger.info(f"检测到文件移动事件: {src_path} -> {dest_path}")
        
        src_abs = os.path.abspath(src_path)
        dest_abs = os.path.abspath(dest_path)
        
        if not str(src_abs).startswith(str(self.watch_path)):
            logger.debug(f"源文件不在监控目录内，忽略移动事件: {src_path}")
            return
        
        if str(dest_abs).startswith(str(self.watch_path)):
            logger.debug(f"文件在监控目录内移动: {src_path} -> {dest_path}")
            file_meta = self.file_repo.get_file_metadata_by_filepath(src_path)
            if file_meta:
                try:
                    file_meta.filepath = dest_abs
                    file_meta.filename = os.path.basename(dest_path)
                    self.file_repo.update_file_metadata(file_meta)
                    logger.info(f"文件移动已同步到 DB: {file_meta.filename}")
                except Exception as e:
                    logger.error(f"更新移动后路径失败: {e}")
            else:
                self._add_file_record(dest_path)
            return

        logger.info(f"文件移出监控目录，视为删除: {src_path} -> {dest_path}")
        file_info = self._get_file_by_path(src_path)
        if file_info is None:
            logger.warning(f"文件不在数据库中，无需清理: {src_path}")
            return
        success = self._cleanup_file_record(file_info)
        if success:
            logger.info(f"文件移出同步完成，原文件: {file_info['filename']}")
        else:
            logger.error(f"文件移出同步失败，原文件: {file_info['filename']}")

    def on_modified(self, event: FileModifiedEvent) -> None:
        """
        处理文件修改事件。
        
        可选功能：更新文件大小等元数据。当前的实现记录日志，
        实际更新元数据需要根据业务需求决定是否实现。
        
        参数:
            event: watchdog的FileModifiedEvent事件对象
        """
        if event.is_directory:
            return
        
        file_path = event.src_path
        
        if not os.path.exists(file_path):
            return
        
        try:
            file_size = os.path.getsize(file_path)
            logger.debug(f"文件修改检测: {file_path}，新大小: {file_size} bytes")
        except Exception as e:
            logger.warning(f"获取文件大小失败: {file_path}，错误: {e}")
