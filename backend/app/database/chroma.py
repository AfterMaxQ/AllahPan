"""
ChromaDB向量数据库连接模块。

本模块提供ChromaDB类，处理与ChromaDB向量数据库的所有交互。
ChromaDB用于存储文件的语义嵌入向量，支持AI驱动的相似性搜索功能。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-19
"""

import chromadb
from chromadb.config import Settings
from typing import List, Optional, Dict, Any

import httpx

import logging

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class ChromaDB:
    """
    ChromaDB向量数据库操作类。
    
    该类管理ChromaDB向量数据库的连接和操作，用于存储和检索
    文件的语义嵌入向量。每个文件可以关联一个向量表示，实现
    基于语义的相似性搜索。
    
    属性:
        COLLECTION_NAME: 文件向量集合名称
        db_name: ChromaDB数据库路径
        client: ChromaDB客户端实例
        _collection: 文件向量集合
    """

    COLLECTION_NAME = "file_vectors"
    DEFAULT_SIMILARITY_THRESHOLD = 1.43

    def __init__(self, persist_path: str = "./data/chroma_vectors", ollama_base_url: str = "http://localhost:11434", similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD):
        """
        初始化ChromaDB连接，使用持久化存储。
        
        该构造函数创建ChromaDB客户端并获取或创建文件向量集合。
        数据会持久化到指定路径，确保应用重启后数据不丢失。
        
        参数:
            persist_path: 向量数据持久化目录路径（默认: './data/chroma_vectors'）
            ollama_base_url: Ollama服务地址（默认: 'http://localhost:11434'）
        """
        import os
        abs_path = os.path.abspath(persist_path)
        logger.info(f"初始化ChromaDB向量数据库连接，路径: {abs_path}")
        self.db_name = abs_path
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.client = chromadb.PersistentClient(
            path=abs_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        self._collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "File semantic vectors for AI search"}
        )
        self.similarity_threshold = similarity_threshold
        logger.info(f"ChromaDB向量数据库连接初始化完成，相似度阈值: {similarity_threshold}")

    def add_vector(
        self,
        file_id: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        为文件添加语义向量。
        
        该方法将文件的语义嵌入向量存储到向量数据库中，
        并关联文件元数据以便后续检索。
        
        参数:
            file_id: 文件唯一标识符（UUID字符串）
            vector: 语义嵌入向量
            metadata: 可选的额外元数据
        
        返回:
            str: 文档ID（格式: 'file_{file_id}'）
        """
        logger.info(f"开始添加向量，文件ID: {file_id}")
        doc_id = f"file_{file_id}"
        meta = metadata or {}
        meta["file_id"] = file_id

        self._collection.add(
            ids=[doc_id],
            embeddings=[vector],
            metadatas=[meta]
        )
        logger.info(f"向量添加成功，文件ID: {file_id}")
        return doc_id

    def get_vector(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        根据文件ID检索向量。
        
        该方法从向量数据库中获取指定文件的向量数据。
        
        参数:
            file_id: 文件唯一标识符
        
        返回:
            Optional[Dict[str, Any]]: 包含向量数据的字典，未找到返回None
        """
        logger.debug(f"根据文件ID检索向量: {file_id}")
        doc_id = f"file_{file_id}"
        result = self._collection.get(ids=[doc_id])
        if result["ids"]:
            vector_data = {
                "id": result["ids"][0],
                "embedding": result["embeddings"][0] if result["embeddings"] else None,
                "metadata": result["metadatas"][0] if result["metadatas"] else None
            }
            logger.debug(f"找到向量，文件ID: {file_id}")
            return vector_data
        logger.debug(f"未找到向量，文件ID: {file_id}")
        return None

    def update_vector(
        self,
        file_id: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        更新文件的向量。
        
        该方法更新已存在文件的语义向量和元数据。
        
        参数:
            file_id: 文件唯一标识符
            vector: 新的语义嵌入向量
            metadata: 可选的新元数据
        
        返回:
            bool: 更新成功返回True，否则返回False
        """
        logger.info(f"开始更新向量，文件ID: {file_id}")
        doc_id = f"file_{file_id}"
        meta = metadata or {}
        meta["file_id"] = file_id

        try:
            self._collection.update(
                ids=[doc_id],
                embeddings=[vector],
                metadatas=[meta]
            )
            logger.info(f"向量更新成功，文件ID: {file_id}")
            return True
        except Exception as e:
            logger.error(f"向量更新失败，文件ID: {file_id}，错误: {e}")
            return False

    def delete_vector(self, file_id: str) -> bool:
        """
        删除文件的向量。
        
        该方法从向量数据库中删除指定文件的向量索引。
        
        参数:
            file_id: 文件唯一标识符
        
        返回:
            bool: 删除成功返回True，否则返回False
        """
        logger.info(f"开始删除向量，文件ID: {file_id}")
        doc_id = f"file_{file_id}"
        try:
            self._collection.delete(ids=[doc_id])
            logger.info(f"向量删除成功，文件ID: {file_id}")
            return True
        except Exception as e:
            logger.error(f"向量删除失败，文件ID: {file_id}，错误: {e}")
            return False

    def search_by_vector(
        self,
        query_vector: List[float],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        使用查询向量搜索相似文件。
        
        该方法根据输入的向量在数据库中检索最相似的文件向量。
        
        参数:
            query_vector: 查询向量
            n_results: 返回结果数量上限（默认: 5）
            where: 可选的元数据过滤条件
        
        返回:
            List[Dict[str, Any]]: 包含匹配结果的列表，每个结果包含id、embedding、metadata和distance
        """
        logger.info(f"开始向量相似性搜索，查询向量维度: {len(query_vector)}，结果数: {n_results}，阈值: {self.similarity_threshold}")
        result = self._collection.query(
            query_embeddings=[query_vector],
            n_results=n_results,
            where=where
        )

        if not result["ids"]:
            logger.info("向量搜索未找到匹配结果")
            return []

        ids_list = result["ids"][0] if result["ids"] else []
        embeddings_list = result["embeddings"][0] if result["embeddings"] and result["embeddings"][0] else []
        metadatas_list = result["metadatas"][0] if result["metadatas"] and result["metadatas"][0] else []
        distances_list = result["distances"][0] if result["distances"] and result["distances"][0] else []

        search_results = []
        filtered_results = []
        for i in range(len(ids_list)):
            metadata = metadatas_list[i] if i < len(metadatas_list) else None
            if metadata is None:
                metadata = {}
            embedding = embeddings_list[i] if i < len(embeddings_list) else None
            distance = distances_list[i] if i < len(distances_list) else None

            search_results.append({
                "id": ids_list[i],
                "embedding": embedding,
                "metadata": metadata,
                "distance": distance
            })

            if distance is not None and distance <= self.similarity_threshold:
                filtered_results.append(search_results[-1])
                logger.debug(f"  结果[{i}] 通过阈值: id={ids_list[i]}, distance={distance:.4f}, filename={metadata.get('filename', 'unknown')}")
            else:
                logger.debug(f"  结果[{i}] 被过滤: id={ids_list[i]}, distance={distance}, filename={metadata.get('filename', 'unknown')}")

        logger.info(f"向量搜索完成，原始结果: {len(search_results)} 个，过滤后: {len(filtered_results)} 个（阈值: {self.similarity_threshold}）")
        logger.info(f"向量搜索详情: {[(r['id'], round(r['distance'], 4)) for r in search_results]}")
        return filtered_results

    def _get_text_embedding_sync(self, text: str, model: str = "nomic-embed-text-v2-moe") -> List[float]:
        """
        同步调用Ollama API将文本转换为向量。

        参数:
            text: 待向量化的文本
            model: 嵌入模型名称

        返回:
            List[float]: 文本的语义向量
        """
        try:
            # 新版 httpx 要求 Timeout 要么只传 default，要么显式设置 connect/read/write/pool
            timeout = httpx.Timeout(connect=10.0, read=60.0, write=60.0, pool=5.0)
            with httpx.Client(timeout=timeout) as client:
                # 使用 OpenAI 兼容的 /v1/embeddings 端点（兼容性更好）
                response = client.post(
                    f"{self.ollama_base_url}/v1/embeddings",
                    json={"model": model, "input": text.strip()}
                )
                response.raise_for_status()
                data = response.json()
                # OpenAI 兼容格式：data[0].embedding
                data_list = data.get("data")
                if data_list is None or not isinstance(data_list, list) or len(data_list) == 0:
                    logger.error("Ollama API 响应中未包含 data 字段或 data 为空")
                    raise ValueError("API 响应中未包含 data 字段或 data 为空")
                embedding = data_list[0].get("embedding")
                if embedding is None:
                    logger.error("Ollama API 响应中未包含 embedding 字段")
                    raise ValueError("API 响应中未包含 embedding 字段")
                return embedding
        except httpx.ConnectError:
            logger.warning(f"无法连接到Ollama服务: {self.ollama_base_url}")
            raise RuntimeError(f"无法连接到Ollama服务: {self.ollama_base_url}")
        except httpx.TimeoutException:
            logger.warning("Ollama API请求超时")
            raise RuntimeError("Ollama API请求超时")
        except Exception as e:
            logger.error(f"文本向量化失败: {e}")
            raise RuntimeError(f"文本向量化失败: {e}")

    def search_by_text(
        self,
        query_text: str,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        使用文本查询搜索相似文件。

        该方法将文本通过Ollama API同步转换为向量，然后在向量库中检索相似文件。
        避免了ChromaDB内置嵌入函数的兼容性问题。

        参数:
            query_text: 文本查询
            n_results: 返回结果数量上限（默认: 5）

        返回:
            List[Dict[str, Any]]: 包含匹配结果的列表
        """
        logger.info(f"开始文本相似性搜索，查询文本: {query_text[:50]}...，结果数: {n_results}")
        try:
            query_vector = self._get_text_embedding_sync(query_text)
        except RuntimeError as e:
            logger.error(f"文本转向量失败，无法执行搜索: {e}")
            return []

        return self.search_by_vector(query_vector, n_results)

    def iter_index_pages(
        self,
        page_size: int = 256,
        include_metadatas: bool = True,
    ):
        """
        分页遍历集合中的文档，默认不包含 embedding，降低内存与 IO。

        每页产出 (doc_ids: List[str], metadatas: List[Optional[dict]])。
        """
        offset = 0
        include = ["metadatas"] if include_metadatas else []
        try:
            while True:
                result = self._collection.get(
                    limit=page_size,
                    offset=offset,
                    include=include,
                )
                ids_batch = result.get("ids") or []
                if not ids_batch:
                    break
                metas = result.get("metadatas") if include_metadatas else [None] * len(ids_batch)
                if metas is None:
                    metas = [None] * len(ids_batch)
                yield ids_batch, metas
                offset += len(ids_batch)
                if len(ids_batch) < page_size:
                    break
        except TypeError:
            # 旧版 chromadb 可能不支持 offset 分页，一次性拉取（仍不含 embedding）
            logger.warning("Chroma get 不支持 offset 分页，回退为单次全量列举 id/metadata")
            result = self._collection.get(include=include)
            ids_batch = result.get("ids") or []
            metas = result.get("metadatas") if include_metadatas else [None] * len(ids_batch)
            if metas is None:
                metas = [None] * len(ids_batch)
            if ids_batch:
                yield ids_batch, metas

    def delete_vectors_batch(self, file_ids: List[str]) -> int:
        """按业务 file_id 批量删除文档（内部 id 为 file_{uuid}）。成功时返回本次请求的文档数（与 len(file_ids) 一致）。"""
        if not file_ids:
            return 0
        doc_ids = [f"file_{fid}" for fid in file_ids]
        try:
            self._collection.delete(ids=doc_ids)
            return len(doc_ids)
        except Exception as e:
            logger.warning(f"批量删除向量失败，数量 {len(doc_ids)}，错误: {e}")
            n = 0
            for fid in file_ids:
                if self.delete_vector(fid):
                    n += 1
            return n

    def get_all_vectors(self) -> List[Dict[str, Any]]:
        """
        获取数据库中的所有向量。
        
        该方法检索向量数据库中的所有向量数据。
        
        返回:
            List[Dict[str, Any]]: 包含所有向量的列表
        """
        logger.debug("获取所有向量")
        result = self._collection.get()
        if not result["ids"]:
            logger.debug("向量库为空")
            return []

        all_vectors = [
            {
                "id": result["ids"][i],
                "embedding": result["embeddings"][i] if result["embeddings"] else None,
                "metadata": result["metadatas"][i] if result["metadatas"] else None
            }
            for i in range(len(result["ids"]))
        ]
        logger.debug(f"共获取 {len(all_vectors)} 个向量")
        return all_vectors

    def count(self) -> int:
        """
        获取向量数据库中的向量总数。
        
        返回:
            int: 向量数量
        """
        count = self._collection.count()
        logger.debug(f"向量库中共有 {count} 个向量")
        return count

    def reset(self) -> None:
        """重置数据库，删除所有数据。"""
        logger.warning("开始重置ChromaDB向量数据库")
        self.client.reset()
        logger.warning("ChromaDB向量数据库已重置")

    def close(self) -> None:
        """关闭数据库连接。"""
        logger.info("关闭ChromaDB向量数据库连接")
        pass
