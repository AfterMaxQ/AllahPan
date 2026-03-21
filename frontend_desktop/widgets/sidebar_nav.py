"""
侧边栏导航组件模块。

提供百度网盘风格的侧边栏导航，支持文件类型分类筛选。

作者: AllahPan团队
"""

from typing import Optional, Dict, List

from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QSizePolicy,
)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


class SidebarNav(QWidget):
    """
    侧边栏导航组件。
    
    信号:
        category_changed(str): 当选中分类改变时发射，参数为分类标识
    """
    
    category_changed = Signal(str)

    CATEGORY_ITEMS = [
        {"id": "all", "name": "全部文件", "icon": "📁", "section": "main"},
        {"id": "image", "name": "图片", "icon": "🖼️", "section": "category"},
        {"id": "document", "name": "文档", "icon": "📄", "section": "category"},
        {"id": "video", "name": "视频", "icon": "🎬", "section": "category"},
        {"id": "audio", "name": "音频", "icon": "🎵", "section": "category"},
        {"id": "other", "name": "其他", "icon": "📦", "section": "category"},
        {"id": "ai_search", "name": "AI 搜索", "icon": "🤖", "section": "tool"},
        {"id": "ops_dashboard", "name": "运维看板", "icon": "📊", "section": "tool"},
    ]
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("SidebarWidget")
        self._current_category = "all"
        self._setup_ui()
        self._select_default()
    
    def _setup_ui(self) -> None:
        """设置 UI。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        header_label = QLabel("文件分类")
        header_label.setObjectName("SidebarTitle")
        header_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(header_label)
        
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("SidebarList")
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setSpacing(2)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        self._category_item_map: Dict[str, QListWidgetItem] = {}

        current_section = ""
        for item_config in self.CATEGORY_ITEMS:
            section = item_config["section"]
            
            if section == "category" and current_section != "category":
                separator = QListWidgetItem()
                separator.setFlags(Qt.ItemFlag.NoItemFlags)
                separator.setSizeHint(QSize(self.list_widget.width(), 1))
                self.list_widget.addItem(separator)
            
            current_section = section
            
            item = QListWidgetItem(f"{item_config['icon']}  {item_config['name']}")
            item.setData(Qt.ItemDataRole.UserRole, item_config["id"])
            item.setToolTip(item_config["name"])
            self._category_item_map[item_config["id"]] = item
            
            w = item.listWidget().width() if item.listWidget() else 220
            item.setSizeHint(QSize(max(160, w - 20), 44))
            
            self.list_widget.addItem(item)
        
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        self.list_widget.setHorizontalScrollMode(
            QListWidget.ScrollMode.ScrollPerPixel
        )
        layout.addWidget(self.list_widget, 1)
        
        info_label = QLabel("AllahPan v1.0.0")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("font-size: 11px; color: #86868B; padding: 10px;")
        layout.addWidget(info_label)
    
    def _select_default(self) -> None:
        """选择默认项。"""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == self._current_category:
                item.setSelected(True)
                break
    
    def _on_selection_changed(self) -> None:
        """处理选择改变。"""
        selected = self.list_widget.selectedItems()
        if not selected:
            return
        
        item = selected[0]
        category_id = item.data(Qt.ItemDataRole.UserRole)
        
        if category_id and category_id != self._current_category:
            self._current_category = category_id
            self.category_changed.emit(category_id)
    
    def get_current_category(self) -> str:
        """获取当前分类。"""
        return self._current_category
    
    def set_current_category(self, category: str) -> None:
        """
        设置当前分类。
        
        参数:
            category: 分类标识
        """
        if category == self._current_category:
            return
        
        self._current_category = category
        
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == category:
                item.setSelected(True)
                break
    
    def update_file_counts(self, counts: Dict[str, int]) -> None:
        """
        更新文件计数。
        
        参数:
            counts: 分类计数字典，键为分类标识，值为文件数量
        """
        for category_id, count in counts.items():
            item = self._category_item_map.get(category_id)
            if item is None:
                continue
            cat_info = next(
                (c for c in self.CATEGORY_ITEMS if c["id"] == category_id), None
            )
            if cat_info:
                icon = cat_info["icon"]
                name = cat_info["name"]
                item.setText(f"{icon}  {name} ({count})")
    
    def set_current_path(self, path: str) -> None:
        """兼容主窗口调用；侧栏已不再展示路径。"""
        return

    def set_root_directories(self, dirs: List[Dict[str, str]]) -> None:
        """兼容主窗口调用；已移除侧栏一级目录快捷入口。"""
        return
    
    def set_width(self, width: int) -> None:
        """
        设置侧边栏宽度。
        
        参数:
            width: 宽度（像素）
        """
        self.setFixedWidth(width)
        
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.flags() != Qt.ItemFlag.NoItemFlags:
                item.setSizeHint(QSize(max(160, width - 24), 44))
