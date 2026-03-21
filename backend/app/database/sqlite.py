"""
SQLite数据库连接模块。

本模块提供SQLite类，处理与SQLite数据库的所有交互。
SQLite用于存储结构化数据，包括用户信息和文件元数据。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-19
"""

import threading
import uuid
import sqlite3
from datetime import datetime
from typing import Any, List, Optional, Tuple

from app.models.user import User
from app.models.file_metadata import FileMetadata

import logging

logger = logging.getLogger(__name__)


def as_sql_text_param(value: Any) -> str:
    """
    将绑定到 SQLite 占位符的值规范为 str。
    JWT / Pydantic 可能传入 uuid.UUID、bytes 或非规范 str，部分环境下会触发
    sqlite3.InterfaceError: bad parameter or other API misuse。
    """
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, uuid.UUID):
        return str(value)
    return str(value).strip()


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class SQLite:
    """
    SQLite数据库操作类。
    
    该类管理与SQLite数据库的连接，并提供对用户和文件元数据表的
    CRUD操作。SQLite存储结构化数据，ChromaDB存储语义向量，
    形成双存储架构。
    
    属性:
        db_name: SQLite数据库文件名
        conn: sqlite3连接对象
        cursor: sqlite3游标对象
    """

    def __init__(self, db_path: str = "allahpan.db"):
        """
        初始化SQLite连接并创建表（如果不存在）。
        
        该构造函数建立数据库连接，设置行工厂，并调用_create_tables
        方法创建必要的数据表。
        
        参数:
            db_path: 数据库文件完整路径（默认: 'allahpan.db'）
        """
        import os
        db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        logger.info(f"初始化SQLite数据库连接，数据库文件: {db_path}")
        self.db_name = db_path
        self._lock = threading.RLock()
        with self._lock:
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            self.conn.execute("PRAGMA busy_timeout = 30000")
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.execute("PRAGMA foreign_keys = ON")
            self._create_tables()
        logger.info(f"SQLite数据库连接初始化完成")

    def _execute_fetchone(self, sql: str, params: tuple) -> Optional[sqlite3.Row]:
        """执行查询并返回一行，使用独立游标；连接级锁避免多线程并发导致 InterfaceError。"""
        with self._lock:
            cur = self.conn.cursor()
            try:
                cur.execute(sql, params)
                return cur.fetchone()
            finally:
                cur.close()

    def _execute_fetchall(self, sql: str, params: tuple = ()) -> list:
        """执行查询并返回多行，使用独立游标。"""
        with self._lock:
            cur = self.conn.cursor()
            try:
                cur.execute(sql, params)
                return cur.fetchall()
            finally:
                cur.close()

    def _execute_write(self, sql: str, params: tuple) -> int:
        """执行写操作并提交，使用独立游标，返回 rowcount。"""
        with self._lock:
            cur = self.conn.cursor()
            try:
                cur.execute(sql, params)
                self.conn.commit()
                return cur.rowcount
            finally:
                cur.close()

    def _create_tables(self) -> None:
        """
        创建数据库表（如果不存在）。
        
        该方法创建两个表：
        - users: 存储用户账户信息
        - file_metadata: 存储文件元数据，与用户关联
        """
        logger.info("开始创建数据库表")
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                email TEXT NOT NULL,
                create_time TEXT NOT NULL
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_metadata (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                size INTEGER NOT NULL,
                filetype TEXT NOT NULL,
                userid TEXT NOT NULL,
                is_ai_parsed BOOLEAN NOT NULL DEFAULT 0,
                upload_time TEXT NOT NULL,
                FOREIGN KEY (userid) REFERENCES users(id)
            )
        """)
        self.conn.commit()
        logger.info("数据库表创建完成")

    def close(self) -> None:
        """关闭数据库连接。"""
        logger.info("关闭SQLite数据库连接")
        with self._lock:
            if self.conn:
                self.conn.close()
                logger.info("SQLite数据库连接已关闭")

    def add_user(self, user: User) -> str:
        """
        添加新用户到数据库。
        
        参数:
            user: 要添加的User实例
        
        返回:
            str: 新插入用户的ID（UUID字符串）
        """
        logger.info(f"开始添加新用户，用户名: {user.username}")
        user_id = str(uuid.uuid4())
        self._execute_write(
            """INSERT INTO users (id, username, password, email, create_time)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, user.username, user.password, user.email, user.create_time)
        )
        logger.info(f"用户添加成功，用户ID: {user_id}")
        return user_id

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        根据ID检索用户。
        
        参数:
            user_id: 要检索的用户ID
        
        返回:
            Optional[User]: 找到的User实例，未找到返回None
        """
        logger.debug(f"根据ID检索用户: {user_id}")
        uid = as_sql_text_param(user_id)
        if not uid:
            return None
        try:
            row = self._execute_fetchone("SELECT * FROM users WHERE id = ?", (uid,))
        except sqlite3.Error as e:
            logger.error("get_user_by_id SQLite 错误 user_id=%r: %s", uid, e)
            return None
        user = None
        if row:
            try:
                row_dict = {k.lower(): v for k, v in dict(row).items()}
                user = User.from_dict(row_dict)
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"从数据库行构建 User 失败，user_id={user_id}: {e}")
        if user:
            logger.debug(f"找到用户: {user.username}")
        else:
            logger.debug(f"未找到用户: {user_id}")
        return user

    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        根据用户名检索用户。
        
        参数:
            username: 要检索的用户名
        
        返回:
            Optional[User]: 找到的User实例，未找到返回None
        """
        logger.debug(f"根据用户名检索用户: {username}")
        row = self._execute_fetchone("SELECT * FROM users WHERE username = ?", (username,))
        user = None
        if row:
            try:
                row_dict = {k.lower(): v for k, v in dict(row).items()}
                user = User.from_dict(row_dict)
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"从数据库行构建 User 失败，username={username}: {e}")
        if user:
            logger.debug(f"找到用户: {user.username}")
        else:
            logger.debug(f"未找到用户: {username}")
        return user

    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        根据邮箱检索用户。
        
        参数:
            email: 要检索的邮箱地址
        
        返回:
            Optional[User]: 找到的User实例，未找到返回None
        """
        logger.debug(f"根据邮箱检索用户: {email}")
        row = self._execute_fetchone("SELECT * FROM users WHERE email = ?", (email,))
        user = User.from_dict(dict(row)) if row else None
        if user:
            logger.debug(f"找到用户: {user.username}")
        else:
            logger.debug(f"未找到用户: {email}")
        return user

    def update_user(self, user: User) -> bool:
        """
        更新现有用户信息。
        
        参数:
            user: 包含更新数据的User实例（必须设置id）
        
        返回:
            bool: 更新成功返回True，否则返回False
        """
        logger.info(f"开始更新用户信息，用户ID: {user.id}")
        success = self._execute_write(
            """UPDATE users SET username = ?, password = ?, email = ?,
               create_time = ? WHERE id = ?""",
            (user.username, user.password, user.email,
             user.create_time, user.id)
        ) > 0
        if success:
            logger.info(f"用户信息更新成功，用户ID: {user.id}")
        else:
            logger.warning(f"用户信息更新失败，未找到用户: {user.id}")
        return success

    def delete_user(self, user_id: str) -> bool:
        """
        根据ID删除用户。
        
        参数:
            user_id: 要删除的用户ID
        
        返回:
            bool: 删除成功返回True，否则返回False
        """
        logger.info(f"开始删除用户，用户ID: {user_id}")
        success = self._execute_write("DELETE FROM users WHERE id = ?", (user_id,)) > 0
        if success:
            logger.info(f"用户删除成功，用户ID: {user_id}")
        else:
            logger.warning(f"用户删除失败，未找到用户: {user_id}")
        return success

    def get_all_users(self) -> List[User]:
        """
        获取所有用户。
        
        返回:
            List[User]: 用户实例列表
        """
        logger.debug("获取所有用户")
        rows = self._execute_fetchall("SELECT * FROM users")
        users = [User.from_dict(dict(row)) for row in rows]
        logger.debug(f"共获取 {len(users)} 个用户")
        return users

    def add_file_metadata(self, file_metadata: FileMetadata) -> str:
        """
        添加新文件元数据到数据库。
        
        参数:
            file_metadata: 要添加的FileMetadata实例
        
        返回:
            str: 新插入文件元数据的ID（UUID字符串）
        """
        logger.info(f"开始添加文件元数据，文件名: {file_metadata.filename}")
        file_id = file_metadata.file_id
        self._execute_write(
            """INSERT INTO file_metadata
               (id, filename, filepath, size, filetype, userid, is_ai_parsed, upload_time)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (file_id, file_metadata.filename, file_metadata.filepath,
             file_metadata.size, file_metadata.filetype,
             file_metadata.userid, file_metadata.is_ai_parsed, file_metadata.upload_time)
        )
        logger.info(f"文件元数据添加成功，文件ID: {file_id}")
        return file_id

    def get_file_metadata_by_id(self, file_id: str) -> Optional[FileMetadata]:
        """
        根据文件ID检索文件元数据。
        
        参数:
            file_id: 要检索的文件ID
        
        返回:
            Optional[FileMetadata]: 找到的FileMetadata实例，未找到返回None
        """
        logger.debug(f"根据ID检索文件元数据: {file_id}")
        row = self._execute_fetchone("SELECT * FROM file_metadata WHERE id = ?", (file_id,))
        file_meta = FileMetadata.from_dict(dict(row)) if row else None
        if file_meta:
            logger.debug(f"找到文件元数据: {file_meta.filename}")
        else:
            logger.debug(f"未找到文件元数据: {file_id}")
        return file_meta

    def get_file_metadata_by_filename(
        self,
        filename: str
    ) -> Optional[FileMetadata]:
        """
        根据文件名检索文件元数据。
        
        参数:
            filename: 要检索的文件名
        
        返回:
            Optional[FileMetadata]: 找到的FileMetadata实例，未找到返回None
        """
        logger.debug(f"根据文件名检索元数据: {filename}")
        row = self._execute_fetchone("SELECT * FROM file_metadata WHERE filename = ?", (filename,))
        file_meta = FileMetadata.from_dict(dict(row)) if row else None
        if file_meta:
            logger.debug(f"找到文件元数据: {file_meta.file_id}")
        else:
            logger.debug(f"未找到文件元数据: {filename}")
        return file_meta

    def get_file_metadata_by_filepath(self, filepath: str) -> Optional[FileMetadata]:
        """
        根据文件路径检索文件元数据。
        
        参数:
            filepath: 文件的完整路径
        
        返回:
            Optional[FileMetadata]: 找到的FileMetadata实例，未找到返回None
        """
        logger.debug(f"根据文件路径检索元数据: {filepath}")
        row = self._execute_fetchone("SELECT * FROM file_metadata WHERE filepath = ?", (filepath,))
        file_meta = FileMetadata.from_dict(dict(row)) if row else None
        if file_meta:
            logger.debug(f"找到文件元数据: {file_meta.file_id}")
        else:
            logger.debug(f"未找到文件元数据: {filepath}")
        return file_meta

    def get_files_by_userid(self, user_id: str) -> List[FileMetadata]:
        """
        获取指定用户的所有文件。
        
        参数:
            user_id: 用户ID
        
        返回:
            List[FileMetadata]: 该用户的文件元数据列表
        """
        logger.debug(f"获取用户文件列表，用户ID: {user_id}")
        rows = self._execute_fetchall("SELECT * FROM file_metadata WHERE userid = ?", (user_id,))
        files = [FileMetadata.from_dict(dict(row)) for row in rows]
        logger.debug(f"用户 {user_id} 共有 {len(files)} 个文件")
        return files

    def get_all_file_metadata(self) -> List[FileMetadata]:
        """
        获取所有文件元数据。
        
        返回:
            List[FileMetadata]: 所有文件元数据列表
        """
        logger.debug("获取所有文件元数据")
        rows = self._execute_fetchall("SELECT * FROM file_metadata")
        files = [FileMetadata.from_dict(dict(row)) for row in rows]
        logger.debug(f"共获取 {len(files)} 个文件元数据")
        return files

    def get_accessible_files(self) -> List[FileMetadata]:
        """
        获取所有可访问的文件（完整共享模型）。
        
        返回:
            List[FileMetadata]: 所有文件元数据列表
        """
        logger.debug("获取所有可访问的文件")
        rows = self._execute_fetchall("SELECT * FROM file_metadata")
        files = [FileMetadata.from_dict(dict(row)) for row in rows]
        logger.debug(f"共获取 {len(files)} 个可访问文件")
        return files

    def update_file_metadata(self, file_metadata: FileMetadata) -> bool:
        """
        更新现有文件元数据。
        
        参数:
            file_metadata: 包含更新数据的FileMetadata实例
        
        返回:
            bool: 更新成功返回True，否则返回False
        """
        logger.info(f"开始更新文件元数据，文件ID: {file_metadata.file_id}")
        success = self._execute_write(
            """UPDATE file_metadata
               SET filename = ?, filepath = ?, size = ?,
                   filetype = ?, userid = ?, is_ai_parsed = ?, upload_time = ?
               WHERE id = ?""",
            (file_metadata.filename, file_metadata.filepath,
             file_metadata.size, file_metadata.filetype,
             file_metadata.userid, file_metadata.is_ai_parsed,
             file_metadata.upload_time, file_metadata.file_id)
        ) > 0
        if success:
            logger.info(f"文件元数据更新成功，文件ID: {file_metadata.file_id}")
        else:
            logger.warning(f"文件元数据更新失败，未找到文件: {file_metadata.file_id}")
        return success

    def delete_file_metadata(self, file_id: str) -> bool:
        """
        根据文件ID删除文件元数据。
        
        参数:
            file_id: 要删除的文件元数据ID
        
        返回:
            bool: 删除成功返回True，否则返回False
        """
        logger.info(f"开始删除文件元数据，文件ID: {file_id}")
        success = self._execute_write("DELETE FROM file_metadata WHERE id = ?", (file_id,)) > 0
        if success:
            logger.info(f"文件元数据删除成功，文件ID: {file_id}")
        else:
            logger.warning(f"文件元数据删除失败，未找到文件: {file_id}")
        return success

    def delete_files_by_userid(self, user_id: str) -> int:
        """
        删除指定用户的所有文件。
        
        参数:
            user_id: 用户ID
        
        返回:
            int: 删除的文件数量
        """
        logger.info(f"开始删除用户所有文件，用户ID: {user_id}")
        deleted_count = self._execute_write("DELETE FROM file_metadata WHERE userid = ?", (user_id,))
        logger.info(f"删除用户文件完成，用户ID: {user_id}，删除数量: {deleted_count}")
        return deleted_count

    def get_unparsed_files(self) -> List[FileMetadata]:
        """
        获取所有未进行AI解析的文件。
        
        返回:
            List[FileMetadata]: is_ai_parsed为False的文件元数据列表
        """
        logger.debug("获取所有未进行AI解析的文件")
        rows = self._execute_fetchall("SELECT * FROM file_metadata WHERE is_ai_parsed = 0")
        files = [FileMetadata.from_dict(dict(row)) for row in rows]
        logger.debug(f"共获取 {len(files)} 个未解析文件")
        return files

    def update_file_ai_status(self, file_id: str, is_parsed: bool) -> bool:
        """
        更新文件的AI解析状态。
        
        参数:
            file_id: 文件ID
            is_parsed: 新的AI解析状态
        
        返回:
            bool: 更新成功返回True，否则返回False
        """
        logger.info(f"更新文件AI解析状态，文件ID: {file_id}，状态: {is_parsed}")
        success = self._execute_write(
            "UPDATE file_metadata SET is_ai_parsed = ? WHERE id = ?",
            (is_parsed, file_id)
        ) > 0
        if success:
            logger.info(f"文件AI解析状态更新成功，文件ID: {file_id}")
        else:
            logger.warning(f"文件AI解析状态更新失败，未找到文件: {file_id}")
        return success

    def search_files_by_filename(self, keyword: str) -> List[FileMetadata]:
        """
        根据文件名关键字搜索文件（模糊匹配）。
        
        使用SQL LIKE查询实现模糊搜索，匹配文件名中包含关键字的文件。
        支持中英文文件名搜索。
        
        参数:
            keyword: 搜索关键字
        
        返回:
            List[FileMetadata]: 匹配的文件元数据列表
        """
        logger.info(f"根据文件名搜索文件，关键字: {keyword}")
        pattern = f"%{keyword}%"
        rows = self._execute_fetchall("SELECT * FROM file_metadata WHERE filename LIKE ?", (pattern,))
        files = [FileMetadata.from_dict(dict(row)) for row in rows]
        logger.info(f"文件名搜索完成，匹配到 {len(files)} 个文件")
        return files
