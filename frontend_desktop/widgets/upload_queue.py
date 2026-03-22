"""
上传队列组件模块。

提供文件上传队列管理，支持并发上传、进度显示和断点续传。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-20
"""

import hashlib
import os
import json
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from PySide6.QtCore import Signal, QObject, QThread, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QScrollArea
)
from PySide6.QtGui import QMovie

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


# 断点续传配置：每个任务独立状态文件，避免多任务并发写同一文件
CHUNK_SIZE = 5 * 1024 * 1024  # 5MB per chunk
RESUME_STATE_DIR = Path.home() / ".allahpan" / "upload_resume"


class UploadTaskStatus(Enum):
    """上传任务状态。"""
    PENDING = "pending"
    UPLOADING = "uploading"
    PAUSED = "paused"
    RESUMING = "resuming"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class UploadTask:
    """上传任务数据类。"""
    file_path: str
    file_name: str
    file_size: int
    status: UploadTaskStatus = UploadTaskStatus.PENDING
    progress: float = 0.0
    error: Optional[str] = None
    task_id: str = ""
    file_id: Optional[str] = None
    upload_id: Optional[str] = None
    total_chunks: int = 0
    uploaded_chunks: List[int] = field(default_factory=list)
    upload_name: Optional[str] = None  # 传给后端的文件名，可含路径如 "证件/2024/合同.pdf"
    
    def __post_init__(self):
        if not self.task_id:
            import uuid
            self.task_id = str(uuid.uuid4())
        if self.total_chunks == 0 and self.file_size > 0:
            self.total_chunks = (self.file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    
    def get_resume_key(self) -> str:
        """获取恢复上传的键名（基于文件路径和大小）。"""
        return f"{self.file_path}:{self.file_size}"


def _resume_file_path(task: UploadTask) -> Path:
    """单个任务的状态文件路径，避免多任务写同一文件。"""
    key = task.get_resume_key().encode("utf-8")
    name = hashlib.md5(key).hexdigest() + ".json"
    return RESUME_STATE_DIR / name


def _load_resume_state_for_task(task: UploadTask) -> Optional[dict]:
    """加载单个任务的断点续传状态。"""
    path = _resume_file_path(task)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _save_resume_state_for_task(task: UploadTask, state: dict) -> None:
    """保存单个任务的断点续传状态。"""
    RESUME_STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = _resume_file_path(task)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _clear_resume_state(task: UploadTask) -> None:
    """清除单个任务的断点续传状态。"""
    path = _resume_file_path(task)
    if path.exists():
        try:
            path.unlink()
        except Exception:
            pass


class ChunkUploadWorker(QThread):
    """分片上传工作线程（支持断点续传）。"""
    
    progress_updated = Signal(str, float, int, int)
    upload_completed = Signal(str, dict)
    upload_failed = Signal(str, str)
    
    def __init__(self, task: UploadTask, api_client):
        super().__init__()
        self.task = task
        self._api_client = api_client
        self._cancelled = False
    
    def run(self) -> None:
        """执行分片上传。"""
        import httpx
        
        try:
            file_size = self.task.file_size
            chunk_size = CHUNK_SIZE
            total_chunks = self.task.total_chunks
            
            # 检查是否有恢复的进度（单任务独立文件，无并发写冲突）
            saved_state = _load_resume_state_for_task(self.task)
            if saved_state:
                self.task.upload_id = saved_state.get("upload_id") or self.task.upload_id
                self.task.uploaded_chunks = saved_state.get("uploaded_chunks", [])
                if self.task.uploaded_chunks:
                    logger.info(f"恢复上传进度，已上传分片: {self.task.uploaded_chunks}")
            
            headers = self._api_client._get_auth_headers()
            
            # 初始化上传（如果需要）
            if not self.task.upload_id:
                raw_fn = (self.task.file_name or "").strip().replace("\\", "/")
                if "/" in raw_fn:
                    rp, base_fn = raw_fn.rsplit("/", 1)
                    rp = rp.strip().strip("/") or None
                    base_fn = base_fn.strip() or "unnamed"
                else:
                    rp = None
                    base_fn = raw_fn or "unnamed"
                init_data = {
                    "filename": base_fn,
                    "file_size": file_size,
                    "chunk_size": chunk_size,
                    "content_type": self._guess_content_type(base_fn),
                }
                if rp:
                    init_data["relative_parent"] = rp
                response = self._api_client._client.post(
                    "/files/upload/init",
                    json=init_data,
                    headers=headers,
                )
                init_result = self._api_client._handle_response(response)
                self.task.upload_id = init_result["upload_id"]
                self.task.total_chunks = init_result["total_chunks"]
                logger.info(f"初始化分片上传成功，upload_id: {self.task.upload_id}")
            
            # 上传每个分片
            with open(self.task.file_path, "rb") as f:
                for chunk_index in range(self.task.total_chunks):
                    if self._cancelled:
                        raise Exception("Cancelled")
                    
                    if chunk_index in self.task.uploaded_chunks:
                        logger.debug(f"跳过已上传的分片: {chunk_index}")
                        continue
                    
                    f.seek(chunk_index * chunk_size)
                    chunk_data = f.read(chunk_size)
                    
                    # 上传分片
                    files = {"file": ("chunk", chunk_data)}
                    response = self._api_client._client.post(
                        f"/files/upload/chunk?upload_id={self.task.upload_id}&chunk_index={chunk_index}",
                        files=files,
                        headers=headers,
                    )
                    result = self._api_client._handle_response(response)
                    
                    # 记录已上传的分片
                    if chunk_index not in self.task.uploaded_chunks:
                        self.task.uploaded_chunks.append(chunk_index)
                        self.task.uploaded_chunks.sort()
                    
                    # 保存进度到断点续传状态（单任务独立文件）
                    _save_resume_state_for_task(self.task, {
                        "upload_id": self.task.upload_id,
                        "uploaded_chunks": self.task.uploaded_chunks,
                    })
                    
                    # 计算进度
                    uploaded = len(self.task.uploaded_chunks) * chunk_size
                    if chunk_index == self.task.total_chunks - 1:
                        uploaded = file_size
                    progress = (len(self.task.uploaded_chunks) / self.task.total_chunks) * 100
                    self.progress_updated.emit(self.task.task_id, progress, uploaded, file_size)
            
            # 完成上传
            response = self._api_client._client.post(
                f"/files/upload/complete/{self.task.upload_id}",
                headers=headers,
            )
            result = self._api_client._handle_response(response)
            
            # 清除断点续传状态
            _clear_resume_state(self.task)
            
            self.upload_completed.emit(self.task.task_id, result.get("file_metadata", {}))
            
        except Exception as e:
            if not self._cancelled:
                self.upload_failed.emit(self.task.task_id, str(e))
    
    def _guess_content_type(self, filename: str) -> str:
        """猜测文件 MIME 类型。"""
        import mimetypes
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "application/octet-stream"
    
    def cancel(self) -> None:
        """取消上传。"""
        self._cancelled = True


# 保留原有的简单上传Worker用于小文件
class UploadWorker(QThread):
    """上传工作线程。"""
    
    progress_updated = Signal(str, float, int, int)
    upload_completed = Signal(str, dict)
    upload_failed = Signal(str, str)
    
    def __init__(self, task: UploadTask, api_client):
        super().__init__()
        self.task = task
        self._api_client = api_client
        self._cancelled = False
    
    def run(self) -> None:
        """执行上传。"""
        try:
            from api.files import FilesAPI
            files_api = FilesAPI(self._api_client)
            
            def progress_callback(uploaded: int, total: int) -> None:
                if self._cancelled:
                    raise Exception("Cancelled")
                progress = (uploaded / total) * 100 if total > 0 else 0
                self.progress_updated.emit(self.task.task_id, progress, uploaded, total)
            
            result = files_api.upload_file(
                file_path=self.task.file_path,
                progress_callback=progress_callback,
                upload_name=self.task.upload_name,
            )
            
            self.upload_completed.emit(self.task.task_id, result)
            
        except Exception as e:
            if not self._cancelled:
                self.upload_failed.emit(self.task.task_id, str(e))
    
    def cancel(self) -> None:
        """取消上传。"""
        self._cancelled = True


import logging
logger = logging.getLogger(__name__)


class UploadQueueItem(QWidget):
    """单个上传队列项组件。"""
    
    cancelled = Signal(str)
    
    def __init__(self, task: UploadTask, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.task = task
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """设置 UI。"""
        self.setObjectName("UploadItemWidget")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        
        info_layout = QHBoxLayout()
        info_layout.setSpacing(8)
        
        self.icon_label = QLabel("📤")
        self.icon_label.setFixedWidth(24)
        info_layout.addWidget(self.icon_label)
        
        self.name_label = QLabel(self.task.file_name)
        self.name_label.setStyleSheet("font-weight: 500;")
        self.name_label.setFixedHeight(20)
        info_layout.addWidget(self.name_label, 1)
        
        self.size_label = QLabel(config.format_file_size(self.task.file_size))
        self.size_label.setStyleSheet("color: #86868B; font-size: 12px;")
        self.size_label.setFixedWidth(80)
        info_layout.addWidget(self.size_label)
        
        self.status_label = QLabel("等待中...")
        self.status_label.setStyleSheet("color: #86868B; font-size: 12px;")
        self.status_label.setFixedWidth(60)
        info_layout.addWidget(self.status_label)
        
        self.cancel_button = QPushButton("✕")
        self.cancel_button.setFixedSize(24, 24)
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.clicked.connect(lambda: self.cancelled.emit(self.task.task_id))
        info_layout.addWidget(self.cancel_button)
        
        layout.addLayout(info_layout)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("UploadProgressBar")
        self.progress_bar.setMinimumHeight(6)
        self.progress_bar.setMaximumHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
    
    def update_progress(self, progress: float, uploaded: int, total: int) -> None:
        """更新进度。"""
        self.task.progress = progress
        self.progress_bar.setValue(int(progress))
        self.status_label.setText(f"{int(progress)}%")
        
        if self.task.status != UploadTaskStatus.UPLOADING:
            self.task.status = UploadTaskStatus.UPLOADING
            self.status_label.setText("上传中")
    
    def set_completed(self) -> None:
        """设置为完成状态。"""
        self.task.status = UploadTaskStatus.COMPLETED
        self.progress_bar.setValue(100)
        self.status_label.setText("完成 ✓")
        self.status_label.setStyleSheet("color: #34C759; font-size: 12px; font-weight: 500;")
        self.cancel_button.hide()
    
    def set_failed(self, error: str) -> None:
        """设置为失败状态。"""
        self.task.status = UploadTaskStatus.FAILED
        self.task.error = error
        self.status_label.setText("失败 ✕")
        self.status_label.setStyleSheet("color: #FF3B30; font-size: 12px; font-weight: 500;")
    
    def set_uploading(self) -> None:
        """设置为上传中状态。"""
        self.task.status = UploadTaskStatus.UPLOADING
        self.status_label.setText("上传中...")
        self.status_label.setStyleSheet("color: #007AFF; font-size: 12px;")
    
    def set_pending(self) -> None:
        """设置为等待状态。"""
        self.task.status = UploadTaskStatus.PENDING
        self.status_label.setText("等待中...")
        self.status_label.setStyleSheet("color: #86868B; font-size: 12px;")
        self.progress_bar.setValue(0)


class UploadQueue(QWidget):
    """
    上传队列组件。
    
    信号:
        upload_completed(str, dict): 上传完成
            - str: 任务ID
            - dict: 文件元数据
        upload_failed(str, str): 上传失败
            - str: 任务ID
            - str: 错误信息
        all_completed(): 所有任务完成
    """
    
    upload_completed = Signal(str, dict)
    upload_failed = Signal(str, str)
    all_completed = Signal()
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        max_concurrent: int = 3,
    ):
        super().__init__(parent)
        self._max_concurrent = max_concurrent
        self._tasks: List[UploadTask] = []
        self._workers: Dict[str, UploadWorker] = {}
        self._items: Dict[str, UploadQueueItem] = {}
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """设置 UI。"""
        self.setObjectName("UploadQueueWidget")
        self.setMaximumHeight(300)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        self.icon_label = QLabel("📤")
        self.icon_label.setFixedWidth(24)
        header_layout.addWidget(self.icon_label)
        
        self.title_label = QLabel("上传队列")
        self.title_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        header_layout.addWidget(self.title_label, 1)
        
        self.count_label = QLabel("(0)")
        self.count_label.setStyleSheet("color: #86868B; font-size: 13px;")
        self.count_label.setFixedWidth(40)
        header_layout.addWidget(self.count_label)
        
        self.clear_button = QPushButton("清空")
        self.clear_button.setFixedSize(50, 24)
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.clicked.connect(self._clear_completed)
        header_layout.addWidget(self.clear_button)
        
        layout.addLayout(header_layout)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("border: none; background: transparent;")
        
        self.items_container = QWidget()
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(8)
        self.items_layout.addStretch()
        
        scroll_area.setWidget(self.items_container)
        layout.addWidget(scroll_area, 1)
        
        self.hide()
    
    def add_file(self, file_path: str, upload_name: Optional[str] = None) -> str:
        """
        添加文件到上传队列。
        
        参数:
            file_path: 文件路径
            upload_name: 传给后端的文件名，可含路径（如 "证件/2024/合同.pdf"），不传则用 basename
            
        返回:
            任务ID
        """
        import os
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        task = UploadTask(
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            upload_name=upload_name,
        )
        
        self._tasks.append(task)
        
        item = UploadQueueItem(task)
        item.cancelled.connect(self._on_item_cancelled)
        
        self._items[task.task_id] = item
        self.items_layout.insertWidget(
            self.items_layout.count() - 1,
            item
        )
        
        self._update_count()
        self._process_queue()
        
        self.show()
        
        return task.task_id
    
    def add_files(self, file_paths: List[str]) -> List[str]:
        """
        批量添加文件到上传队列（无路径，使用 basename）。
        """
        task_ids = []
        for path in file_paths:
            if os.path.isfile(path):
                task_id = self.add_file(path)
                task_ids.append(task_id)
        return task_ids

    def add_files_with_upload_names(self, paths_and_names: List[tuple]) -> List[str]:
        """
        批量添加文件到上传队列，每个文件指定传给后端的 upload_name（可含路径）。
        
        参数:
            paths_and_names: [(absolute_path, upload_name), ...]，upload_name 如 "证件/2024/合同.pdf"
        
        返回:
            任务ID列表
        """
        task_ids = []
        for item in paths_and_names:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                path, upload_name = item[0], item[1]
            else:
                path, upload_name = item, None
            if os.path.isfile(path):
                task_id = self.add_file(path, upload_name=upload_name)
                task_ids.append(task_id)
        return task_ids
    
    def _process_queue(self) -> None:
        """处理队列。"""
        active_count = sum(
            1 for t in self._tasks
            if t.status == UploadTaskStatus.UPLOADING
        )
        
        pending_tasks = [
            t for t in self._tasks
            if t.status == UploadTaskStatus.PENDING
        ]
        
        for task in pending_tasks:
            if active_count >= self._max_concurrent:
                break
            
            self._start_upload(task)
            active_count += 1
    
    def _start_upload(self, task: UploadTask) -> None:
        """开始上传。"""
        from api.client import get_api_client
        
        item = self._items.get(task.task_id)
        if item:
            item.set_uploading()
        
        # 大文件（>10MB）使用分片上传
        if task.file_size > 10 * 1024 * 1024:
            logger.info(f"使用分片上传，文件大小: {task.file_size}")
            worker = ChunkUploadWorker(task, get_api_client())
        else:
            worker = UploadWorker(task, get_api_client())
        
        worker.progress_updated.connect(
            self._on_progress_updated, Qt.ConnectionType.QueuedConnection
        )
        worker.upload_completed.connect(
            self._on_upload_completed, Qt.ConnectionType.QueuedConnection
        )
        worker.upload_failed.connect(
            self._on_upload_failed, Qt.ConnectionType.QueuedConnection
        )
        
        self._workers[task.task_id] = worker
        worker.start()
    
    def _on_progress_updated(self, task_id: str, progress: float, uploaded: int, total: int) -> None:
        """处理进度更新。"""
        item = self._items.get(task_id)
        if item:
            item.update_progress(progress, uploaded, total)
    
    def _on_upload_completed(self, task_id: str, result: dict) -> None:
        """处理上传完成。"""
        task = next((t for t in self._tasks if t.task_id == task_id), None)
        if task:
            task.status = UploadTaskStatus.COMPLETED
            task.file_id = result.get("file_id")
        
        item = self._items.get(task_id)
        if item:
            item.set_completed()
        
        self.upload_completed.emit(task_id, result)
        
        self._process_queue()
        self._check_all_completed()
    
    def _on_upload_failed(self, task_id: str, error: str) -> None:
        """处理上传失败。"""
        task = next((t for t in self._tasks if t.task_id == task_id), None)
        if task:
            task.status = UploadTaskStatus.FAILED
            task.error = error
        
        item = self._items.get(task_id)
        if item:
            item.set_failed(error)
        
        self.upload_failed.emit(task_id, error)
        
        self._process_queue()
        self._check_all_completed()
    
    def _on_item_cancelled(self, task_id: str) -> None:
        """处理取消。"""
        worker = self._workers.get(task_id)
        if worker and worker.isRunning():
            worker.cancel()
            worker.wait(5000)
        
        task = next((t for t in self._tasks if t.task_id == task_id), None)
        if task:
            task.status = UploadTaskStatus.CANCELLED
        
        self._remove_task(task_id)
    
    def _remove_task(self, task_id: str) -> None:
        """移除任务。"""
        self._tasks = [t for t in self._tasks if t.task_id != task_id]
        
        item = self._items.pop(task_id, None)
        if item:
            item.hide()
            self.items_layout.removeWidget(item)
            item.deleteLater()
        
        worker = self._workers.pop(task_id, None)
        if worker and worker.isRunning():
            worker.cancel()
            worker.wait(5000)
            if worker.isRunning():
                worker.terminate()
        
        self._update_count()
    
    def _clear_completed(self) -> None:
        """清空已完成的任务。"""
        completed_ids = [
            t.task_id for t in self._tasks
            if t.status in (UploadTaskStatus.COMPLETED, UploadTaskStatus.FAILED, UploadTaskStatus.CANCELLED)
        ]
        
        for task_id in completed_ids:
            self._remove_task(task_id)
        
        if not self._tasks:
            self.hide()
    
    def _update_count(self) -> None:
        """更新计数。"""
        count = len(self._tasks)
        self.count_label.setText(f"({count})")
    
    def _check_all_completed(self) -> None:
        """检查是否全部完成。"""
        if not self._tasks:
            return
        
        all_done = all(
            t.status in (
                UploadTaskStatus.COMPLETED,
                UploadTaskStatus.FAILED,
                UploadTaskStatus.CANCELLED,
            )
            for t in self._tasks
        )
        
        if all_done:
            self.all_completed.emit()
    
    def get_pending_count(self) -> int:
        """获取待处理任务数。"""
        return sum(
            1 for t in self._tasks
            if t.status in (UploadTaskStatus.PENDING, UploadTaskStatus.UPLOADING)
        )
    
    def cancel_all(self) -> None:
        """取消所有任务。"""
        for worker in self._workers.values():
            if worker.isRunning():
                worker.cancel()
                worker.wait(5000)
                if worker.isRunning():
                    worker.terminate()
        
        for task in self._tasks:
            if task.status == UploadTaskStatus.UPLOADING:
                task.status = UploadTaskStatus.CANCELLED
        
        self._workers.clear()
        self._update_count()
