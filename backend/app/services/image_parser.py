"""
图片解析队列服务模块。

本模块提供图片解析队列管理功能，使用 asyncio.Queue 实现异步批量解析。
当图片上传或搜索时，自动将未解析的图片加入队列，由后台 worker 处理。

作者：AllahPan 团队
创建日期：2026-03-19
最后修改：2026-03-19
"""

from __future__ import annotations

import asyncio
import traceback
from pathlib import Path
from typing import Optional, Set
from datetime import datetime

from app.database.repositories.file_repository import FileRepository
from ollama.ollama_client import OllamaClient

import logging

logger = logging.getLogger(__name__)

# ChromaDB 对 metadata 单值长度可能有限制，截断到安全长度
CHROMA_METADATA_TEXT_MAX_LEN = 500


class ImageParserQueue:
    """
    图片解析队列管理器。
    
    使用 asyncio.Queue 实现异步图片解析队列，支持：
    - 自动解析上传的图片
    - 批量队列处理
    - 防止重复解析
    - 优雅关闭
    
    属性：
        queue: asyncio 队列，存储待解析的文件 ID
        processing: 正在处理中的文件 ID 集合
        file_repo: 文件仓库实例
        ollama: Ollama 客户端实例
        worker_count: worker 数量
        _worker_tasks: worker 任务列表
        _shutdown_event: 关闭事件
    """

    def __init__(
        self,
        file_repo: FileRepository,
        ollama: OllamaClient,
        worker_count: int = 2
    ):
        """
        初始化图片解析队列。
        
        参数：
            file_repo: 文件仓库实例
            ollama: Ollama 客户端实例
            worker_count: 并发 worker 数量（默认：2）
        """
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.processing: Set[str] = set()
        self._processing_lock: asyncio.Lock = asyncio.Lock()
        self.file_repo = file_repo
        self.ollama = ollama
        self.worker_count = worker_count
        self._worker_tasks: list[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()
        self._total_processed = 0
        self._total_failed = 0
        logger.info(f"ImageParserQueue 初始化完成，worker 数量：{worker_count}")

    async def start(self) -> None:
        """
        启动队列处理 worker。

        创建指定数量的 worker 任务，扫描并加入未解析的图片，开始处理队列中的图片解析请求。
        """
        logger.info(f"启动 ImageParserQueue，worker 数量：{self.worker_count}")
        for i in range(self.worker_count):
            task = asyncio.create_task(self._worker(f"worker-{i}"))
            self._worker_tasks.append(task)

        await self._scan_and_enqueue_unparsed_images()
        logger.info("ImageParserQueue worker 已全部启动")

    async def _scan_and_enqueue_unparsed_images(self) -> None:
        """
        扫描并加入未解析的图片到队列。

        从数据库获取所有未解析的图片文件，将图片类型的文件加入解析队列。
        """
        logger.info("开始扫描未解析的图片...")
        try:
            unparsed_files = self.file_repo.get_unparsed_files()
            image_files = [
                f for f in unparsed_files
                if f.filetype.startswith("image/")
            ]
            logger.info(f"发现 {len(image_files)} 个未解析的图片文件")

            for file_meta in image_files:
                if file_meta.file_id not in self.processing:
                    await self.queue.put(file_meta.file_id)

            logger.info(f"已将 {self.queue.qsize()} 个未解析图片加入队列")
        except Exception as e:
            logger.error(f"扫描未解析图片失败：{e}")

    async def stop(self) -> None:
        """
        优雅停止队列处理。
        
        等待队列中的所有任务处理完成后再停止。
        """
        logger.info("正在停止 ImageParserQueue...")
        self._shutdown_event.set()
        
        # 等待队列清空
        if not self.queue.empty():
            logger.info(f"等待处理队列中剩余的 {self.queue.qsize()} 个任务...")
            await self.queue.join()
        
        # 取消所有 worker 任务
        for task in self._worker_tasks:
            task.cancel()
        
        # 等待所有任务完成
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()
        
        logger.info(f"ImageParserQueue 已停止，总处理：{self._total_processed}, 失败：{self._total_failed}")

    async def add_to_queue(self, file_id: str) -> bool:
        """
        将文件加入解析队列。
        
        参数：
            file_id: 文件 ID
        
        返回：
            bool: 成功加入返回 True，如果已在队列中或正在处理返回 False
        """
        # 检查文件是否存在且未解析
        file_meta = self.file_repo.get_file_metadata_by_id(file_id)
        if file_meta is None:
            logger.warning(f"文件不存在，无法加入队列：{file_id}")
            return False
        
        if file_meta.is_ai_parsed:
            logger.debug(f"文件已解析，无需加入队列：{file_id}")
            return False
        
        if not file_meta.filetype.startswith("image/"):
            logger.debug(f"文件不是图片类型，无需加入队列：{file_id}")
            return False
        
        # 持锁检查并加入 processing，避免多 worker 竞态
        async with self._processing_lock:
            if file_id in self.processing:
                logger.debug(f"文件已在队列中或正在处理，跳过：{file_id}")
                return False
            self.processing.add(file_id)
        await self.queue.put(file_id)
        logger.info(f"文件已加入解析队列：{file_id}, 队列长度：{self.queue.qsize()}")
        return True

    async def _worker(self, worker_name: str) -> None:
        """
        队列处理 worker。

        持续从队列中取出文件 ID 进行解析，直到收到关闭信号。
        失败后会自动重试最多3次，每次重试前等待递增的时间。

        参数：
            worker_name: worker 名称（用于日志）
        """
        logger.info(f"{worker_name} 启动")
        # 超时/网络类错误时延长退避，最多重试 5 次
        retry_delays = [5, 15, 30, 60, 90]

        while not self._shutdown_event.is_set():
            try:
                file_id = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            try:
                if self._shutdown_event.is_set():
                    break
                # file_id 已在 enqueue 时加入 processing，此处仅处理
                retry_count = 0
                max_retries = 5
                logger.info(f"{worker_name} 开始处理文件：{file_id}")
                success = False
                while retry_count <= max_retries:
                    try:
                        await self._parse_image(file_id)
                        self._total_processed += 1
                        logger.info(f"{worker_name} 完成处理文件：{file_id}")
                        success = True
                        break
                    except Exception as e:
                        retry_count += 1
                        err_msg = f"{type(e).__name__}: {e!r}" if not str(e).strip() else str(e)
                        err_detail = f"{type(e).__name__}: {e!r}"
                        if retry_count > max_retries:
                            self._total_failed += 1
                            logger.error(
                                f"{worker_name} 处理文件失败，已达到最大重试次数：{file_id}, 错误：{err_detail}"
                            )
                            logger.debug("处理失败时的堆栈：\n%s", traceback.format_exc())
                            break
                        delay = retry_delays[retry_count - 1] if retry_count <= len(retry_delays) else 90
                        logger.warning(
                            f"{worker_name} 处理文件失败，{delay}秒后重试（第{retry_count}次）：{file_id}, 错误：{err_detail}"
                        )
                        logger.debug("处理失败时的堆栈：\n%s", traceback.format_exc())
                        await asyncio.sleep(delay)
            except asyncio.CancelledError:
                logger.info(f"{worker_name} 被取消")
                break
            except Exception as e:
                logger.error(f"{worker_name} 发生错误：{e}")
            finally:
                async with self._processing_lock:
                    self.processing.discard(file_id)
                self.queue.task_done()

        logger.info(f"{worker_name} 已停止")

    async def _parse_image(self, file_id: str) -> None:
        """
        解析单个图片文件。
        
        参数：
            file_id: 文件 ID
        """
        # 获取文件元数据
        file_meta = self.file_repo.get_file_metadata_by_id(file_id)
        if file_meta is None:
            raise ValueError(f"文件不存在：{file_id}")
        
        # 检查是否已解析（可能在工作过程中被其他 worker 解析）
        if file_meta.is_ai_parsed:
            logger.info(f"文件已解析，跳过：{file_id}")
            return
        
        # 检查文件类型
        if not file_meta.filetype.startswith("image/"):
            logger.info(f"文件不是图片类型，跳过：{file_id}")
            return
        
        # 检查文件是否存在
        file_path = Path(file_meta.filepath)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在：{file_meta.filepath}")
        
        logger.info(f"开始 AI 解析图片：{file_id}, 路径：{file_path}")
        
        # 调用 Ollama 解析图片
        extracted_text = await self.ollama.parse_image_content(str(file_path))
        
        if not extracted_text or not extracted_text.strip():
            extracted_text = f"[图片内容] {file_meta.filename}"
        
        logger.info(f"图片解析完成：{file_id}, 提取文本长度：{len(extracted_text)}")
        
        # 生成向量
        embedding = await self.ollama.embed_text(extracted_text)
        logger.info(f"向量生成完成：{file_id}, 维度：{len(embedding)}")
        
        # 存储向量到 ChromaDB（metadata 文本过长可能导致 Chroma 写入失败，故截断）
        vector_metadata = {
            "filename": (file_meta.filename or "")[:CHROMA_METADATA_TEXT_MAX_LEN],
            "filetype": (file_meta.filetype or "")[:CHROMA_METADATA_TEXT_MAX_LEN],
            "file_size": file_meta.size,
            "parsed_text": (extracted_text or "")[:CHROMA_METADATA_TEXT_MAX_LEN],
            "parsed_at": datetime.now().isoformat(),
        }
        
        self.file_repo.add_or_update_vector(
            file_id=file_id,
            vector=embedding,
            metadata=vector_metadata,
        )
        logger.info(f"向量存储完成：{file_id}")
        
        # 更新文件状态为已解析
        self.file_repo.mark_as_ai_parsed(file_id)
        logger.info(f"文件状态更新完成：{file_id}, is_ai_parsed=True")

    def get_status(self) -> dict:
        """
        获取队列状态信息。
        
        返回：
            dict: 包含队列状态的字典
        """
        return {
            "queue_size": self.queue.qsize(),
            "processing_count": len(self.processing),
            "worker_count": self.worker_count,
            "total_processed": self._total_processed,
            "total_failed": self._total_failed,
            "is_running": not self._shutdown_event.is_set(),
        }


# 全局实例
_image_parser_queue: Optional[ImageParserQueue] = None


def get_image_parser_queue() -> Optional[ImageParserQueue]:
    """
    获取全局的 ImageParserQueue 实例。
    
    返回：
        Optional[ImageParserQueue]: 队列实例，未初始化返回 None
    """
    return _image_parser_queue


def set_image_parser_queue(queue: ImageParserQueue) -> None:
    """
    设置全局的 ImageParserQueue 实例。
    
    参数：
        queue: 队列实例
    """
    global _image_parser_queue
    _image_parser_queue = queue
    logger.info("全局 ImageParserQueue 实例已设置")
