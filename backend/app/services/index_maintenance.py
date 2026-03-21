"""
向量索引定期对齐：后台线程轻量扫描 Chroma 与 SQLite，清理孤立向量并调度缺失向量修复。

设计要点：
- 使用分页 get（不含 embedding），控制内存与单次 IO。
- 孤立向量批量 delete，失败时降级为逐条删除。
- 「已解析但 Chroma 无向量」通过 ImageParserQueue 修复，每轮有上限，避免压垮 Ollama。
"""

from __future__ import annotations

import asyncio
import logging
import random
import threading
import time
from concurrent.futures import Future as ConcurrentFuture
from typing import List, Optional, Set

from app.config import (
    INDEX_MAINTENANCE_CHROMA_PAGE_SIZE,
    INDEX_MAINTENANCE_INTERVAL_SEC,
    INDEX_MAINTENANCE_ORPHAN_DELETE_BATCH,
    INDEX_MAINTENANCE_REPAIR_MAX_PER_RUN,
)

logger = logging.getLogger(__name__)


def _file_id_from_chroma_doc(doc_id: str, meta: Optional[dict]) -> Optional[str]:
    if isinstance(meta, dict):
        raw = meta.get("file_id")
        if raw is not None:
            s = str(raw).strip()
            if s:
                return s
    if isinstance(doc_id, str) and doc_id.startswith("file_"):
        return doc_id[5:]
    if doc_id:
        return str(doc_id)
    return None


class IndexMaintenanceService:
    """单例式后台维护线程（daemon）。"""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_run_mono: float = 0.0
        self._last_summary: str = ""

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="AllahPanIndexMaint",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "向量索引维护线程已启动，周期间隔约 %s 秒",
            INDEX_MAINTENANCE_INTERVAL_SEC,
        )

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=12.0)
            self._thread = None
        logger.info("向量索引维护线程已停止")

    def last_summary(self) -> str:
        return self._last_summary

    def _loop(self) -> None:
        first = True
        while not self._stop.is_set():
            if first:
                delay = min(15.0, max(3.0, INDEX_MAINTENANCE_INTERVAL_SEC * 0.2))
                first = False
            else:
                jitter = random.uniform(0, min(60.0, INDEX_MAINTENANCE_INTERVAL_SEC * 0.2))
                delay = float(INDEX_MAINTENANCE_INTERVAL_SEC) + jitter
            if self._stop.wait(timeout=delay):
                break
            try:
                self._reconcile_pass()
            except Exception:
                logger.exception("索引维护周期失败")

    def _reconcile_pass(self) -> None:
        from app.api.v1.dependencies import get_file_repo
        from app.services.image_parser import get_image_parser_queue

        t0 = time.monotonic()
        file_repo = get_file_repo()
        valid_ids: Set[str] = set(file_repo.get_all_file_ids())
        orphan_file_ids: List[str] = []
        seen_orphan: Set[str] = set()
        # 本轮扫描中 Chroma 里出现的业务 file_id（与逐条 get_vector 等价，避免修复阶段 O(N) 次查询）
        chroma_file_ids: Set[str] = set()

        page_size = max(32, INDEX_MAINTENANCE_CHROMA_PAGE_SIZE)
        for doc_ids, metas in file_repo.chroma.iter_index_pages(page_size=page_size):
            for i, doc_id in enumerate(doc_ids):
                meta = metas[i] if i < len(metas) else None
                fid = _file_id_from_chroma_doc(doc_id, meta)
                if fid:
                    chroma_file_ids.add(fid)
                if not fid or fid in valid_ids:
                    continue
                if fid not in seen_orphan:
                    seen_orphan.add(fid)
                    orphan_file_ids.append(fid)

        deleted_vectors = 0
        batch = max(1, INDEX_MAINTENANCE_ORPHAN_DELETE_BATCH)
        batch_delete_rounds = (len(orphan_file_ids) + batch - 1) // batch if orphan_file_ids else 0
        for i in range(0, len(orphan_file_ids), batch):
            chunk = orphan_file_ids[i : i + batch]
            deleted_vectors += file_repo.chroma.delete_vectors_batch(chunk)

        repair_enqueued = 0
        queue = get_image_parser_queue()
        loop = queue.get_event_loop() if queue else None
        repair_cap = max(0, INDEX_MAINTENANCE_REPAIR_MAX_PER_RUN)

        if queue is not None and loop is not None and repair_cap > 0:
            for fid in file_repo.get_ai_parsed_image_file_ids():
                if repair_enqueued >= repair_cap:
                    break
                if fid in chroma_file_ids:
                    continue

                def _schedule(fid_inner: str) -> None:
                    fut = asyncio.run_coroutine_threadsafe(
                        queue.enqueue_embedding_repair(fid_inner),
                        loop,
                    )

                    def _done(f: ConcurrentFuture, x: str = fid_inner) -> None:
                        try:
                            ok = f.result()
                            if ok:
                                logger.debug("索引维护已排程向量修复：%s", x)
                        except Exception as ex:
                            logger.warning("索引维护排程向量修复失败 %s：%s", x, ex)

                    fut.add_done_callback(_done)

                _schedule(fid)
                repair_enqueued += 1

        elapsed = time.monotonic() - t0
        self._last_run_mono = time.monotonic()
        self._last_summary = (
            f"orphan_file_ids={len(orphan_file_ids)}, deleted_vectors={deleted_vectors}, "
            f"batch_delete_rounds={batch_delete_rounds}, repair_scheduled={repair_enqueued}, "
            f"valid_files={len(valid_ids)}, chroma_docs_seen={len(chroma_file_ids)}, "
            f"{elapsed:.2f}s"
        )
        logger.info("索引维护完成：%s", self._last_summary)


_service_lock = threading.Lock()
_service: Optional[IndexMaintenanceService] = None


def start_index_maintenance_thread() -> None:
    global _service
    with _service_lock:
        if _service is not None:
            return
        _service = IndexMaintenanceService()
        _service.start()


def stop_index_maintenance_thread() -> None:
    global _service
    with _service_lock:
        if _service is None:
            return
        _service.stop()
        _service = None


def get_index_maintenance_service() -> Optional[IndexMaintenanceService]:
    return _service
