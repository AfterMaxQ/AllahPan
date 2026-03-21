"""
文件数据模型模块。

提供 QAbstractTableModel 和 QAbstractListModel 的实现，
用于在文件列表视图和网格视图中显示文件数据。
支持使用系统原生文件图标（Windows / macOS 兼容），失败时回退到 emoji 图标。

作者: AllahPan团队
"""

import mimetypes
import tempfile
from typing import List, Optional, Dict, Any
from datetime import datetime

from PySide6.QtCore import (
    QAbstractTableModel, QAbstractListModel,
    QModelIndex, Qt, QUrl, QItemSelectionModel, QFileInfo, Signal,
)
from PySide6.QtGui import QIcon, QPixmap, QPainter, QFont, QAbstractFileIconProvider
from PySide6.QtWidgets import QFileIconProvider

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


# 系统图标缓存：(cache_key, size) -> QIcon，避免重复创建
_icon_cache: Dict[tuple, QIcon] = {}
# 用于按扩展名获取系统图标的占位文件目录（每个扩展名一个占位文件）
_icon_temp_dir: Optional[Path] = None
_icon_provider: Optional[QFileIconProvider] = None


def _get_icon_temp_dir() -> Path:
    """获取或创建图标占位文件目录。"""
    global _icon_temp_dir
    if _icon_temp_dir is None:
        _icon_temp_dir = Path(tempfile.gettempdir()) / "allahpan_icons"
        _icon_temp_dir.mkdir(parents=True, exist_ok=True)
    return _icon_temp_dir


def _extension_for_filetype(filetype: str) -> str:
    """根据 MIME 类型返回常用扩展名（带点），用于系统图标查询。"""
    if not filetype:
        return ".bin"
    filetype = filetype.strip().split(";")[0].strip()
    ext = mimetypes.guess_extension(filetype, strict=False)
    if ext:
        return ext
    # 常见类型手动映射
    mime_ext = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
        "image/svg+xml": ".svg",
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
        "audio/mpeg": ".mp3",
        "audio/wav": ".wav",
        "text/plain": ".txt",
        "text/markdown": ".md",
    }
    return mime_ext.get(filetype, ".bin")


def _get_system_file_icon(filetype: str, is_dir: bool, size: int = 48) -> Optional[QIcon]:
    """
    获取系统原生文件/文件夹图标，兼容 Windows 与 macOS。
    失败时返回 None，由调用方回退到 emoji 图标。
    """
    try:
        provider = _icon_provider or QFileIconProvider()
        if _icon_provider is None:
            globals()["_icon_provider"] = provider
        if is_dir:
            icon = provider.icon(QAbstractFileIconProvider.IconType.Folder)
        else:
            ext = _extension_for_filetype(filetype)
            temp_dir = _get_icon_temp_dir()
            placeholder = temp_dir / f"file{ext}"
            if not placeholder.exists():
                placeholder.touch()
            info = QFileInfo(str(placeholder))
            icon = provider.icon(info)
        if icon.isNull():
            return None
        pixmap = icon.pixmap(size, size)
        if pixmap.isNull():
            return None
        return QIcon(pixmap)
    except Exception:
        return None


def _file_icon_qicon(filetype: str, is_dir: bool, size: int = 48) -> QIcon:
    """
    返回文件/文件夹的 QIcon。优先使用系统原生图标（Windows/macOS），
    不可用时回退到 config 的 emoji 图标。
    """
    cache_key = ("inode/directory" if is_dir else (filetype or ""), size)
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]
    icon = _get_system_file_icon(filetype, is_dir, size)
    if icon is not None:
        _icon_cache[cache_key] = icon
        return icon
    # 回退：将 config 的 emoji 绘制到 QPixmap
    emoji = config.get_file_icon("inode/directory" if is_dir else filetype)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    font = QFont("Segoe UI Emoji" if sys.platform == "win32" else "Apple Color Emoji", max(12, int(size * 0.6)))
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, emoji)
    painter.end()
    fallback = QIcon(pixmap)
    _icon_cache[cache_key] = fallback
    return fallback


class FileItem:
    """文件数据项（支持文件和文件夹）。"""
    
    def __init__(
        self,
        file_id: str,
        filename: str,
        filepath: str,
        size: int,
        filetype: str,
        is_ai_parsed: bool = False,
        upload_time: str = "",
        is_dir: bool = False,
        virtual_path: str = "",
    ):
        self.file_id = file_id
        self.filename = filename
        self.filepath = filepath
        self.size = size
        self.filetype = filetype
        self.is_ai_parsed = is_ai_parsed
        self.upload_time = upload_time
        self.is_dir = is_dir or (filetype in ("directory", "inode/directory") or (filetype or "").startswith("inode/directory"))
        self.virtual_path = virtual_path
        
        self.icon = config.get_file_icon("inode/directory" if self.is_dir else filetype)
        self.category = config.get_file_category(filetype)
        self.size_display = "—" if self.is_dir else config.format_file_size(size)
        
        self.upload_datetime = self._parse_datetime(upload_time)
    
    def _parse_datetime(self, time_str: str) -> Optional[datetime]:
        """解析日期时间字符串。"""
        if not time_str:
            return None
        try:
            return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except Exception:
            return None
    
    @property
    def is_image(self) -> bool:
        """是否为图片文件。"""
        return self.filetype.startswith("image/")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "filepath": self.filepath,
            "size": self.size,
            "filetype": self.filetype,
            "is_ai_parsed": self.is_ai_parsed,
            "upload_time": self.upload_time,
            "is_dir": self.is_dir,
        }
    
    @classmethod
    def _normalize_is_ai_parsed(cls, raw: Any) -> bool:
        """将 API 返回的 is_ai_parsed 规范化为 bool（兼容 bool/int/str）。"""
        if raw is None:
            return False
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            return raw.lower() in ("true", "1", "yes", "on")
        if isinstance(raw, (int, float)):
            return bool(raw)
        return False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileItem":
        """从字典创建。支持 virtual_path（目录项导航路径）。"""
        return cls(
            file_id=data.get("file_id", ""),
            filename=data.get("filename", ""),
            filepath=data.get("filepath", ""),
            size=data.get("size", 0),
            filetype=data.get("filetype", ""),
            is_ai_parsed=cls._normalize_is_ai_parsed(data.get("is_ai_parsed")),
            upload_time=data.get("upload_time", ""),
            is_dir=data.get("is_dir", False),
            virtual_path=data.get("virtual_path", ""),
        )


class FileTableModel(QAbstractTableModel):
    """
    文件列表表格数据模型。
    
    用于 QTableView 显示文件列表。
    """

    row_check_toggled = Signal(int, bool)
    
    class Column:
        """列定义。"""
        CHECKBOX = 0
        ICON = 1
        NAME = 2
        SIZE = 3
        TYPE = 4
        TIME = 5
        AI_STATUS = 6
        
        HEADERS = ["", "", "文件名", "大小", "类型", "上传时间", "AI状态"]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._files: List[FileItem] = []
        self._selected_ids: set = set()
    
    def rowCount(self, parent=QModelIndex()) -> int:
        """返回文件数量。"""
        if parent.isValid():
            return 0
        return len(self._files)
    
    def columnCount(self, parent=QModelIndex()) -> int:
        """返回列数。"""
        if parent.isValid():
            return 0
        return len(self.Column.HEADERS)
    
    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole) -> any:
        """获取单元格数据。"""
        if not index.isValid():
            return None
        
        row = index.row()
        col = index.column()
        
        if row < 0 or row >= len(self._files):
            return None
        
        file_item = self._files[row]
        
        if role == Qt.ItemDataRole.DisplayRole:
            if col == self.Column.NAME:
                return file_item.filename
            elif col == self.Column.SIZE:
                return file_item.size_display
            elif col == self.Column.TYPE:
                return config.get_file_type_display_name(file_item.filetype)
            elif col == self.Column.TIME:
                if file_item.upload_datetime:
                    return file_item.upload_datetime.strftime("%Y-%m-%d %H:%M")
                return ""
            elif col == self.Column.AI_STATUS:
                return "已解析" if file_item.is_ai_parsed else "未解析"
        
        elif role == Qt.ItemDataRole.DecorationRole:
            if col == self.Column.ICON:
                return _file_icon_qicon(file_item.filetype, getattr(file_item, "is_dir", False), 32)
        
        elif role == Qt.ItemDataRole.CheckStateRole:
            if col == self.Column.CHECKBOX:
                # 由 FileBrowser._on_selection_changed 通过 sync_selection_display() 统一驱动，
                # 这里只读 _selected_ids 集合来渲染勾选状态，不再自行修改。
                return Qt.CheckState.Checked if file_item.file_id in self._selected_ids else Qt.CheckState.Unchecked
        
        elif role == Qt.ItemDataRole.UserRole:
            return file_item
        
        return None
    
    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role=Qt.ItemDataRole.DisplayRole
    ) -> any:
        """获取表头数据。"""
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self.Column.HEADERS[section] if section < len(self.Column.HEADERS) else ""
        return None
    
    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """获取单元格标志。"""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        
        col = index.column()
        if col == self.Column.CHECKBOX:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        
        return flags
    
    def setData(self, index: QModelIndex, value: any, role=Qt.ItemDataRole.EditRole) -> bool:
        """设置单元格数据。"""
        if not index.isValid():
            return False
        
        row = index.row()
        col = index.column()
        
        if row < 0 or row >= len(self._files):
            return False
        
        if role == Qt.ItemDataRole.CheckStateRole and col == self.Column.CHECKBOX:
            file_item = self._files[row]
            if value == Qt.CheckState.Checked:
                self._selected_ids.add(file_item.file_id)
            else:
                self._selected_ids.discard(file_item.file_id)
            self.dataChanged.emit(index, index, [role])
            self.row_check_toggled.emit(row, value == Qt.CheckState.Checked)
            return True
        
        return False
    
    def sync_selection_display(self, selected_ids: set) -> None:
        """
        根据传入的选中文件ID集合刷新所有 checkbox 的显示状态，
        同时更新内部的 _selected_ids 以保持一致。
        """
        self._selected_ids = set(selected_ids)
        if self._files:
            top_left = self.index(0, self.Column.CHECKBOX)
            bottom_right = self.index(len(self._files) - 1, self.Column.CHECKBOX)
            if top_left.isValid() and bottom_right.isValid():
                self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.CheckStateRole])
    
    def get_selected_files(self) -> List[FileItem]:
        """
        获取当前已选中的文件。
        
        由 FileBrowser._on_selection_changed 传入已从视图 selectionModel 中解析出的
        file_id 集合，再根据该集合返回对应的 FileItem 列表。
        """
        return [f for f in self._files if f.file_id in self._selected_ids]
    
    def set_files(self, files: List[FileItem]) -> None:
        """设置文件列表。"""
        self.beginResetModel()
        self._files = files
        self._selected_ids.clear()
        self.endResetModel()
    
    def get_files(self) -> List[FileItem]:
        """获取文件列表。"""
        return self._files
    
    def get_file_by_index(self, index: QModelIndex) -> Optional[FileItem]:
        """根据索引获取文件。"""
        if index.isValid() and index.row() < len(self._files):
            return self._files[index.row()]
        return None
    
    def clear_selection(self) -> None:
        """清除所有选中。"""
        self._selected_ids.clear()
        self.beginResetModel()
        self.endResetModel()
    
    def select_all(self) -> None:
        """全选所有文件。"""
        self._selected_ids = {f.file_id for f in self._files}
        self.beginResetModel()
        self.endResetModel()
    
    def filter_by_category(self, category: str) -> List[FileItem]:
        """根据分类筛选文件。"""
        if category == "all":
            return self._files
        
        return [
            f for f in self._files
            if f.category == category
        ]
    
    def filter_by_keyword(self, keyword: str) -> List[FileItem]:
        """根据关键字筛选文件。"""
        if not keyword:
            return self._files
        
        keyword_lower = keyword.lower()
        return [
            f for f in self._files
            if keyword_lower in f.filename.lower()
        ]


class FileListModel(QAbstractListModel):
    """
    文件网格列表数据模型。
    
    用于 QListView（IconMode）显示文件网格。
    """

    row_check_toggled = Signal(int, bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._files: List[FileItem] = []
        self._selected_ids: set = set()
    
    def rowCount(self, parent=QModelIndex()) -> int:
        """返回文件数量。"""
        if parent.isValid():
            return 0
        return len(self._files)
    
    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole) -> any:
        """获取数据。"""
        if not index.isValid():
            return None
        
        row = index.row()
        if row < 0 or row >= len(self._files):
            return None
        
        file_item = self._files[row]
        
        if role == Qt.ItemDataRole.DisplayRole:
            return file_item.filename
        
        elif role == Qt.ItemDataRole.DecorationRole:
            return _file_icon_qicon(file_item.filetype, getattr(file_item, "is_dir", False), 64)
        
        elif role == Qt.ItemDataRole.UserRole:
            return file_item
        
        elif role == Qt.ItemDataRole.CheckStateRole:
            return Qt.CheckState.Checked if file_item.file_id in self._selected_ids else Qt.CheckState.Unchecked
        
        return None
    
    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """获取标志。"""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable
    
    def setData(self, index: QModelIndex, value: any, role=Qt.ItemDataRole.EditRole) -> bool:
        """设置数据。"""
        if not index.isValid():
            return False
        
        row = index.row()
        if row < 0 or row >= len(self._files):
            return False
        
        if role == Qt.ItemDataRole.CheckStateRole:
            file_item = self._files[row]
            if value == Qt.CheckState.Checked:
                self._selected_ids.add(file_item.file_id)
            else:
                self._selected_ids.discard(file_item.file_id)
            self.dataChanged.emit(index, index, [role])
            self.row_check_toggled.emit(row, value == Qt.CheckState.Checked)
            return True
        
        return False
    
    def set_files(self, files: List[FileItem]) -> None:
        """设置文件列表。"""
        self.beginResetModel()
        self._files = files
        self._selected_ids.clear()
        self.endResetModel()
    
    def get_files(self) -> List[FileItem]:
        """获取文件列表。"""
        return self._files
    
    def get_selected_files(self) -> List[FileItem]:
        """获取选中的文件。"""
        return [f for f in self._files if f.file_id in self._selected_ids]
    
    def get_file_by_index(self, index: QModelIndex) -> Optional[FileItem]:
        """根据索引获取文件。"""
        if index.isValid() and index.row() < len(self._files):
            return self._files[index.row()]
        return None
    
    def sync_selection_display(self, selected_ids: set) -> None:
        """根据传入的选中文件ID集合刷新所有 checkbox 的显示状态。"""
        self._selected_ids = set(selected_ids)
        if self._files:
            top_left = self.index(0)
            bottom_right = self.index(len(self._files) - 1)
            if top_left.isValid() and bottom_right.isValid():
                self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.CheckStateRole])
    
    def clear_selection(self) -> None:
        """清除所有选中。"""
        self._selected_ids.clear()
        self.beginResetModel()
        self.endResetModel()
    
    def select_all(self) -> None:
        """全选所有文件。"""
        self._selected_ids = {f.file_id for f in self._files}
        self.beginResetModel()
        self.endResetModel()
    
    def filter_by_category(self, category: str) -> List[FileItem]:
        """根据分类筛选文件。"""
        if category == "all":
            return self._files
        return [f for f in self._files if f.category == category]
    
    def filter_by_keyword(self, keyword: str) -> List[FileItem]:
        """根据关键字筛选文件。"""
        if not keyword:
            return self._files
        keyword_lower = keyword.lower()
        return [f for f in self._files if keyword_lower in f.filename.lower()]
