"""
文件仓库模块。

本模块提供FileRepository类，作为文件元数据和向量操作的抽象层。
它协调SQLite（元数据）和ChromaDB（向量）之间的操作，提供统一的
文件操作接口。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-19
"""

from typing import List, Optional

from app.models.file_metadata import FileMetadata
from app.database.sqlite import SQLite
from app.database.chroma import ChromaDB

import logging

logger = logging.getLogger(__name__)


class FileRepository:
    """
    文件数据操作仓库类。
    
    该类管理文件元数据（存储在SQLite中）和语义向量（存储在ChromaDB中），
    提供统一的文件操作接口，实现双存储架构的协调管理。
    
    属性:
        sqlite: 用于元数据操作的SQLite数据库实例
        chroma: 用于向量操作的ChromaDB实例
    """

    def __init__(
        self,
        sqlite_db: Optional[SQLite] = None,
        chroma_db: Optional[ChromaDB] = None
    ):
        """
        初始化FileRepository。
        
        参数:
            sqlite_db: 可选的SQLite实例，未提供时创建新实例
            chroma_db: 可选的ChromaDB实例，未提供时创建新实例
        """
        self.sqlite = sqlite_db or SQLite()
        self.chroma = chroma_db or ChromaDB()

    def create_file_metadata(self, file_metadata: FileMetadata) -> FileMetadata:
        """
        创建新的文件元数据。
        
        参数:
            file_metadata: 要创建的FileMetadata实例
        
        返回:
            FileMetadata: 创建的FileMetadata实例，包含分配的ID
        """
        logger.info(f"FileRepository创建文件元数据，文件名: {file_metadata.filename}")
        file_id = self.sqlite.add_file_metadata(file_metadata)
        file_metadata.file_id = file_id
        logger.info(f"文件元数据创建成功，文件ID: {file_id}")
        return file_metadata

    def get_file_metadata_by_id(self, file_id: str) -> Optional[FileMetadata]:
        """
        根据文件ID检索文件元数据。
        
        参数:
            file_id: 要检索的文件ID
        
        返回:
            Optional[FileMetadata]: 找到的FileMetadata实例，未找到返回None
        """
        logger.debug(f"FileRepository根据ID检索文件元数据: {file_id}")
        return self.sqlite.get_file_metadata_by_id(file_id)

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
        logger.debug(f"FileRepository根据文件名检索元数据: {filename}")
        return self.sqlite.get_file_metadata_by_filename(filename)

    def get_file_metadata_by_filepath(
        self,
        filepath: str
    ) -> Optional[FileMetadata]:
        """
        根据文件路径检索文件元数据。
        
        参数:
            filepath: 文件的完整路径
        
        返回:
            Optional[FileMetadata]: 找到的FileMetadata实例，未找到返回None
        """
        logger.debug(f"FileRepository根据文件路径检索元数据: {filepath}")
        return self.sqlite.get_file_metadata_by_filepath(filepath)

    def get_files_by_userid(self, user_id: str) -> List[FileMetadata]:
        """
        获取指定用户的所有文件。
        
        参数:
            user_id: 用户ID
        
        返回:
            List[FileMetadata]: 该用户的文件元数据列表
        """
        logger.debug(f"FileRepository获取用户文件列表，用户ID: {user_id}")
        return self.sqlite.get_files_by_userid(user_id)

    def get_all_file_metadata(self) -> List[FileMetadata]:
        """
        获取所有文件元数据。
        
        返回:
            List[FileMetadata]: 所有FileMetadata实例列表
        """
        logger.debug("FileRepository获取所有文件元数据")
        return self.sqlite.get_all_file_metadata()

    def get_accessible_files(self) -> List[FileMetadata]:
        """
        获取所有可访问的文件（完整共享模型）。
        
        返回:
            List[FileMetadata]: 所有FileMetadata实例列表
        """
        logger.debug("FileRepository获取所有可访问文件")
        return self.sqlite.get_all_file_metadata()

    def update_file_metadata(self, file_metadata: FileMetadata) -> bool:
        """
        更新现有文件元数据。
        
        参数:
            file_metadata: 包含更新数据的FileMetadata实例
        
        返回:
            bool: 更新成功返回True，否则返回False
        """
        logger.info(f"FileRepository更新文件元数据，文件ID: {file_metadata.file_id}")
        return self.sqlite.update_file_metadata(file_metadata)

    def delete_file_metadata(self, file_id: str) -> bool:
        """
        删除文件元数据及其关联的向量。
        
        先删 SQLite 元数据再删 ChromaDB 向量，避免“向量已删、元数据未删”的永久不一致。
        
        参数:
            file_id: 要删除的文件元数据ID
        
        返回:
            bool: 删除成功返回True，否则返回False
        """
        logger.info(f"FileRepository删除文件元数据，文件ID: {file_id}")
        if self.sqlite.get_file_metadata_by_id(file_id) is None:
            logger.warning(f"文件元数据不存在，无需删除: {file_id}")
            return False
        success = self.sqlite.delete_file_metadata(file_id)
        if success:
            try:
                self.chroma.delete_vector(file_id)
                logger.info(f"文件元数据与向量删除成功，文件ID: {file_id}")
            except Exception as e:
                logger.warning(f"ChromaDB 向量删除失败（元数据已删），文件ID: {file_id}，错误: {e}")
        else:
            logger.warning(f"文件元数据删除失败，文件ID: {file_id}")
        return success

    def delete_files_by_userid(self, user_id: str) -> int:
        """
        删除指定用户的所有文件。
        
        先删 SQLite 元数据再逐个删除 ChromaDB 向量，保证一致性。
        
        参数:
            user_id: 用户ID
        
        返回:
            int: 删除的文件数量
        """
        logger.info(f"FileRepository删除用户所有文件，用户ID: {user_id}")
        files = self.get_files_by_userid(user_id)
        deleted_count = self.sqlite.delete_files_by_userid(user_id)
        for file_meta in files:
            try:
                self.chroma.delete_vector(file_meta.file_id)
            except Exception as e:
                logger.warning(f"ChromaDB 向量删除失败，file_id: {file_meta.file_id}，错误: {e}")
        logger.info(f"FileRepository删除用户文件完成，用户ID: {user_id}，删除数量: {deleted_count}")
        return deleted_count

    def add_vector(
        self,
        file_id: str,
        vector: List[float],
        metadata: Optional[dict] = None
    ) -> str:
        """
        为文件添加语义向量。
        
        参数:
            file_id: 要关联向量的文件ID
            vector: 语义嵌入向量
            metadata: 可选的额外元数据
        
        返回:
            str: 文档ID（格式: 'file_{file_id}'）
        """
        logger.info(f"FileRepository添加向量，文件ID: {file_id}")
        return self.chroma.add_vector(file_id, vector, metadata)

    def add_or_update_vector(
        self,
        file_id: str,
        vector: List[float],
        metadata: Optional[dict] = None
    ) -> None:
        """
        添加或更新语义向量（存在则更新，避免重复添加报错导致永远不标记已解析）。
        """
        try:
            self.chroma.add_vector(file_id, vector, metadata)
        except Exception as e:
            logger.warning(f"添加向量失败，尝试更新已有向量，文件ID: {file_id}，原因: {e}")
            self.chroma.update_vector(file_id, vector, metadata)

    def get_vector(self, file_id: str) -> Optional[dict]:
        """
        根据文件ID检索向量。
        
        参数:
            file_id: 要检索的文件ID
        
        返回:
            Optional[dict]: 包含向量数据的字典，未找到返回None
        """
        logger.debug(f"FileRepository检索向量，文件ID: {file_id}")
        return self.chroma.get_vector(file_id)

    def search_similar_files(
        self,
        query_vector: List[float],
        n_results: int = 5
    ) -> List[dict]:
        """
        使用查询向量搜索相似文件。
        
        参数:
            query_vector: 查询向量
            n_results: 最大返回结果数（默认: 5）
        
        返回:
            List[dict]: 包含匹配结果的列表，每个结果包含id、embedding、metadata和distance
        """
        logger.info(f"FileRepository向量相似性搜索，查询向量维度: {len(query_vector)}")
        return self.chroma.search_by_vector(query_vector, n_results)

    def search_similar_files_by_text(
        self,
        query_text: str,
        n_results: int = 5
    ) -> List[dict]:
        """
        使用文本查询搜索相似文件。
        
        该方法将文本自动转换为向量，然后在向量库中检索相似文件。
        
        参数:
            query_text: 文本查询
            n_results: 最大返回结果数（默认: 5）
        
        返回:
            List[dict]: 包含匹配结果的列表，每个结果包含id、embedding、metadata和distance
        """
        logger.info(f"FileRepository文本相似性搜索，查询文本: {query_text[:50]}...")
        return self.chroma.search_by_text(query_text, n_results)

    def mark_as_ai_parsed(self, file_id: str) -> bool:
        """
        将文件标记为已AI解析。
        
        在成功通过Ollama处理后调用，更新文件的AI解析状态。
        
        参数:
            file_id: 要标记的文件ID
        
        返回:
            bool: 更新成功返回True，否则返回False
        """
        logger.info(f"FileRepository标记文件为已解析，文件ID: {file_id}")
        return self.sqlite.update_file_ai_status(file_id, True)

    def is_ai_parsed(self, file_id: str) -> bool:
        """
        检查文件是否已进行AI解析。
        
        参数:
            file_id: 要检查的文件ID
        
        返回:
            bool: 已解析返回True，否则返回False
        """
        logger.debug(f"FileRepository检查文件AI解析状态，文件ID: {file_id}")
        file_meta = self.sqlite.get_file_metadata_by_id(file_id)
        is_parsed = file_meta.is_ai_parsed if file_meta else False
        if is_parsed:
            logger.debug(f"文件已解析，文件ID: {file_id}")
        else:
            logger.debug(f"文件未解析，文件ID: {file_id}")
        return is_parsed

    def get_unparsed_files(self) -> List[FileMetadata]:
        """
        获取所有未进行AI解析的文件。
        
        返回:
            List[FileMetadata]: is_ai_parsed为False的文件元数据列表
        """
        logger.debug("FileRepository获取所有未解析文件")
        files = self.sqlite.get_unparsed_files()
        logger.debug(f"共获取 {len(files)} 个未解析文件")
        return files

    def search_files_by_filename(self, keyword: str) -> List[FileMetadata]:
        """
        根据文件名关键字搜索文件（模糊匹配）。

        使用SQL LIKE查询实现模糊搜索，匹配文件名中包含关键字的文件。
        这是文本文件的主要搜索方式。

        参数:
            keyword: 搜索关键字

        返回:
            List[FileMetadata]: 匹配的文件元数据列表
        """
        logger.info(f"FileRepository文件名模糊搜索，关键字: {keyword}")
        return self.sqlite.search_files_by_filename(keyword)

    def close(self) -> None:
        """关闭所有数据库连接。"""
        logger.info("关闭FileRepository数据库连接")
        self.sqlite.close()
        self.chroma.close()
