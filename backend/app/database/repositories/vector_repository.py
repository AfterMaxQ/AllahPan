"""
向量仓库模块。

本模块提供VectorRepository类，作为向量数据库操作的抽象层。
它处理语义嵌入的存储和检索，使用ChromaDB作为后端存储。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-19
"""

from typing import List, Optional, Dict, Any

from app.database.chroma import ChromaDB

import logging

logger = logging.getLogger(__name__)


class VectorRepository:
    """
    向量数据操作仓库类。
    
    该类提供向量数据库操作的干净接口，抽象掉直接的ChromaDB操作。
    用于存储和检索语义嵌入向量，支持相似性搜索功能。
    
    属性:
        chroma: 用于向量操作的ChromaDB实例
    """

    def __init__(self, chroma_db: Optional[ChromaDB] = None):
        """
        初始化VectorRepository。
        
        参数:
            chroma_db: 可选的ChromaDB实例，未提供时创建新实例
        """
        self.chroma = chroma_db or ChromaDB()

    def add_vector(
        self,
        file_id: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None
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
        logger.info(f"VectorRepository添加向量，文件ID: {file_id}")
        return self.chroma.add_vector(file_id, vector, metadata)

    def get_vector(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        根据文件ID检索向量。
        
        参数:
            file_id: 要检索的文件ID
        
        返回:
            Optional[Dict[str, Any]]: 包含向量数据的字典，未找到返回None
        """
        logger.debug(f"VectorRepository检索向量，文件ID: {file_id}")
        return self.chroma.get_vector(file_id)

    def update_vector(
        self,
        file_id: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        更新文件的向量。
        
        参数:
            file_id: 要更新向量的文件ID
            vector: 新的语义嵌入向量
            metadata: 可选的新元数据
        
        返回:
            bool: 更新成功返回True，否则返回False
        """
        logger.info(f"VectorRepository更新向量，文件ID: {file_id}")
        return self.chroma.update_vector(file_id, vector, metadata)

    def delete_vector(self, file_id: str) -> bool:
        """
        根据文件ID删除向量。
        
        参数:
            file_id: 要删除向量的文件ID
        
        返回:
            bool: 删除成功返回True，否则返回False
        """
        logger.info(f"VectorRepository删除向量，文件ID: {file_id}")
        return self.chroma.delete_vector(file_id)

    def search_by_vector(
        self,
        query_vector: List[float],
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        使用查询向量搜索相似文件。
        
        参数:
            query_vector: 查询向量
            n_results: 最大返回结果数（默认: 5）
        
        返回:
            List[Dict[str, Any]]: 包含匹配结果的列表，每个结果包含id、embedding、metadata和distance
        """
        logger.info(f"VectorRepository向量相似性搜索，查询向量维度: {len(query_vector)}")
        return self.chroma.search_by_vector(query_vector, n_results)

    def search_by_text(
        self,
        query_text: str,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        使用文本查询搜索相似文件。
        
        该方法将文本自动转换为向量，然后在向量库中检索相似文件。
        
        参数:
            query_text: 文本查询
            n_results: 最大返回结果数（默认: 5）
        
        返回:
            List[Dict[str, Any]]: 包含匹配结果的列表，每个结果包含id、embedding、metadata和distance
        """
        logger.info(f"VectorRepository文本相似性搜索，查询文本: {query_text[:50]}...")
        return self.chroma.search_by_text(query_text, n_results)

    def get_all_vectors(self) -> List[Dict[str, Any]]:
        """
        获取数据库中的所有向量。
        
        返回:
            List[Dict[str, Any]]: 包含所有向量的列表
        """
        logger.debug("VectorRepository获取所有向量")
        return self.chroma.get_all_vectors()

    def count(self) -> int:
        """
        获取向量数据库中的向量总数。
        
        返回:
            int: 向量数量
        """
        count = self.chroma.count()
        logger.debug(f"VectorRepository向量总数: {count}")
        return count

    def reset(self) -> None:
        """重置数据库，删除所有数据。"""
        logger.warning("VectorRepository重置向量数据库")
        self.chroma.reset()

    def close(self) -> None:
        """关闭数据库连接。"""
        logger.info("关闭VectorRepository数据库连接")
        self.chroma.close()
