"""
文件浏览器组件模块。

提供文件网格视图和列表视图，支持切换显示。

作者: AllahPan团队
"""

from typing import Optional, List, Callable, Dict, Any

from PySide6.QtCore import (
    Signal, Qt, QSize, QModelIndex, QTimer, QItemSelectionModel, QEvent, QObject
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QListView, QTableView, QAbstractItemView,
    QHeaderView, QLabel, QPushButton, QToolButton,
    QMenu, QFileDialog, QMessageBox, QApplication
)
from PySide6.QtGui import QAction, QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QDropEvent

import os

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from widgets.file_list_model import FileTableModel, FileListModel, FileItem


class FileBrowser(QWidget):
    """
    文件浏览器组件。
    
    支持网格视图和列表视图切换，提供文件选择、预览、右键菜单等功能。
    
    信号:
        file_double_clicked(FileItem): 双击文件
        file_selection_changed(List[FileItem]): 选中文件改变
        upload_requested(List[str]): 请求上传文件
        download_requested(List[FileItem]): 请求下载文件
        preview_requested(FileItem): 请求预览文件
        delete_requested(List[FileItem]): 请求删除文件（AllahPan系统中此功能受限）
    """
    
    file_double_clicked = Signal(object)
    file_selection_changed = Signal(list)
    upload_requested = Signal(list)
    download_requested = Signal(list)
    preview_requested = Signal(object)
    delete_requested = Signal(list)
    refresh_requested = Signal()
    drag_enter = Signal()
    drag_leave = Signal()
    file_dropped = Signal(list)
    open_storage_in_explorer_requested = Signal()
    
    VIEW_MODE_GRID = "grid"
    VIEW_MODE_LIST = "list"
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._view_mode = self.VIEW_MODE_LIST
        self._files: List[FileItem] = []
        self._selected_files: List[FileItem] = []
        self._current_category = "all"
        self._context_menu_enabled = True
        self._setup_ui()
        self._connect_signals()
        self._install_event_filters()

    def _install_event_filters(self) -> None:
        """安装事件过滤器以支持键盘导航。"""
        self.list_view.installEventFilter(self)
        self.grid_view.installEventFilter(self)
    
    def _setup_ui(self) -> None:
        """设置 UI。"""
        self.setObjectName("ContentWidget")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        toolbar = self._create_toolbar()
        main_layout.addWidget(toolbar)
        
        self.stacked_widget = QStackedWidget()
        
        self.grid_view = self._create_grid_view()
        self.list_view = self._create_list_view()
        
        self.stacked_widget.addWidget(self.grid_view)
        self.stacked_widget.addWidget(self.list_view)
        
        main_layout.addWidget(self.stacked_widget)
        
        self._drop_overlay = self._create_drop_overlay()
        
        self._empty_state_icon = None
        self._empty_state_text_label = None
        self._empty_state_hint_label = None
        self._empty_state_override: Optional[tuple] = None  # (main_text, hint_text) 用于搜索无结果等
        self.empty_state = self._create_empty_state()
        main_layout.addWidget(self.empty_state)
        
        self._loading_overlay = self._create_loading_overlay()
        
        self._set_view_mode(self._view_mode)
    
    def _create_toolbar(self) -> QWidget:
        """创建工具栏。"""
        toolbar = QWidget()
        toolbar.setObjectName("ToolbarWidget")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 8, 16, 8)
        toolbar_layout.setSpacing(12)
        
        self.upload_button = QToolButton()
        self.upload_button.setText("📤 上传")
        self.upload_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.upload_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        upload_menu = QMenu(self)
        upload_file_action = QAction("上传文件", self)
        upload_file_action.triggered.connect(self._on_upload_files_clicked)
        upload_menu.addAction(upload_file_action)
        upload_folder_action = QAction("上传文件夹", self)
        upload_folder_action.triggered.connect(self._on_upload_folder_clicked)
        upload_menu.addAction(upload_folder_action)
        self.upload_button.setMenu(upload_menu)
        self.upload_button.clicked.connect(self._on_upload_files_clicked)
        toolbar_layout.addWidget(self.upload_button)
        
        self.download_button = QToolButton()
        self.download_button.setText("📥 下载")
        self.download_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_button.clicked.connect(self._on_download_clicked)
        self.download_button.setEnabled(False)
        toolbar_layout.addWidget(self.download_button)
        
        self.refresh_button = QToolButton()
        self.refresh_button.setText("🔄 刷新")
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.clicked.connect(self._on_refresh_clicked)
        toolbar_layout.addWidget(self.refresh_button)
        
        toolbar_layout.addStretch()
        
        self.view_mode_group = QWidget()
        view_mode_layout = QHBoxLayout(self.view_mode_group)
        view_mode_layout.setContentsMargins(0, 0, 0, 0)
        view_mode_layout.setSpacing(4)
        
        self.grid_button = QToolButton()
        self.grid_button.setText("⊞")
        grid_font = self.grid_button.font()
        grid_font.setPointSize(max(14, grid_font.pointSize() + 2))
        self.grid_button.setFont(grid_font)
        self.grid_button.setMinimumSize(36, 36)
        self.grid_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.grid_button.setCheckable(True)
        self.grid_button.setChecked(self._view_mode == self.VIEW_MODE_GRID)
        self.grid_button.clicked.connect(lambda: self._set_view_mode(self.VIEW_MODE_GRID))
        view_mode_layout.addWidget(self.grid_button)
        
        self.list_button = QToolButton()
        self.list_button.setText("☰")
        self.list_button.setMinimumSize(36, 36)
        self.list_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.list_button.setCheckable(True)
        self.list_button.setChecked(self._view_mode == self.VIEW_MODE_LIST)
        self.list_button.clicked.connect(lambda: self._set_view_mode(self.VIEW_MODE_LIST))
        view_mode_layout.addWidget(self.list_button)
        
        toolbar_layout.addWidget(self.view_mode_group)
        
        return toolbar
    
    def _create_grid_view(self) -> QListView:
        """创建网格视图。"""
        view = QListView()
        view.setObjectName("FileGridView")
        view.setViewMode(QListView.ViewMode.IconMode)
        view.setGridSize(QSize(config.GRID_ITEM_SIZE, config.GRID_ITEM_SIZE + 30))  # type: ignore[reportAttributeAccessIssue]
        view.setIconSize(QSize(config.GRID_ICON_SIZE, config.GRID_ICON_SIZE))  # type: ignore[reportAttributeAccessIssue]
        view.setSpacing(config.GRID_SPACING)  # type: ignore[reportAttributeAccessIssue]
        view.setResizeMode(QListView.ResizeMode.Adjust)
        view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        view.setDragEnabled(True)
        view.setAcceptDrops(False)
        view.setDropIndicatorShown(True)
        
        self.grid_model = FileListModel()
        view.setModel(self.grid_model)
        
        view.doubleClicked.connect(self._on_grid_double_clicked)
        sm = view.selectionModel()
        if sm is not None:
            sm.selectionChanged.connect(self._on_selection_changed)

        view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        view.customContextMenuRequested.connect(self._show_context_menu)
        
        return view
    
    def _create_loading_overlay(self) -> QWidget:
        """创建加载中覆盖层。"""
        overlay = QWidget(self.stacked_widget)
        overlay.setObjectName("LoadingOverlay")
        overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        overlay.setWindowFlags(Qt.WindowType.Widget)
        overlay.setCursor(Qt.CursorShape.WaitCursor)
        overlay.setStyleSheet("""
            QWidget#LoadingOverlay {
                background-color: rgba(245, 245, 247, 0.85);
            }
        """)
        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel("加载中…")
        label.setStyleSheet("font-size: 15px; color: #86868B;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label = label
        layout.addWidget(label)
        overlay.hide()
        return overlay
    
    def show_loading(self, show: bool, message: str = "加载中…") -> None:
        """显示或隐藏加载中覆盖层。"""
        if show:
            self._loading_label.setText(message)
        self._loading_overlay.setGeometry(self.stacked_widget.rect())
        if show:
            self._loading_overlay.raise_()
            self._loading_overlay.show()
        else:
            self._loading_overlay.hide()
    
    def set_empty_state_override(self, main_text: str, hint_text: str = "") -> None:
        """设置空状态覆盖文案（如搜索无结果）。"""
        self._empty_state_override = (main_text, hint_text)
        self._update_empty_state()
    
    def clear_empty_state_override(self) -> None:
        """清除空状态覆盖文案。"""
        self._empty_state_override = None
        self._update_empty_state()
    
    def _create_drop_overlay(self) -> QWidget:
        """创建拖拽时的毛玻璃覆盖层，覆盖文件显示区域（stacked_widget）。"""
        overlay = QWidget(self.stacked_widget)
        overlay.setObjectName("DropOverlayFrosted")
        overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        overlay.setWindowFlags(Qt.WindowType.Widget)
        overlay.setCursor(Qt.CursorShape.DragCopyCursor)
        # 毛玻璃效果：半透明白 + 圆角 + 虚线边框
        overlay.setStyleSheet("""
            QWidget#DropOverlayFrosted {
                background-color: rgba(255, 255, 255, 0.82);
                border: 3px dashed rgba(0, 122, 255, 0.65);
                border-radius: 24px;
            }
        """)
        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel("📤 释放文件上传")
        label.setStyleSheet("""
            font-size: 28px;
            font-weight: 600;
            color: rgba(0, 0, 0, 0.75);
        """)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        overlay.hide()
        return overlay
    
    def show_drop_overlay(self, show: bool) -> None:
        """显示或隐藏拖拽覆盖层（仅覆盖文件显示区域）。"""
        self._drop_overlay.setGeometry(self.stacked_widget.rect())
        if show:
            self._drop_overlay.raise_()
            self._drop_overlay.show()
        else:
            self._drop_overlay.hide()
    
    def resizeEvent(self, event) -> None:
        """窗口大小变化时更新覆盖层几何。"""
        super().resizeEvent(event)
        if self._drop_overlay.isVisible():
            self._drop_overlay.setGeometry(self.stacked_widget.rect())
        if self._loading_overlay.isVisible():
            self._loading_overlay.setGeometry(self.stacked_widget.rect())
    
    def _create_list_view(self) -> QTableView:
        """创建列表视图。"""
        view = QTableView()
        view.setObjectName("FileTableView")
        view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        view.setShowGrid(False)
        view.setSortingEnabled(True)
        
        vh = view.verticalHeader()
        if vh is not None:
            vh.setVisible(False)
        
        hh = view.horizontalHeader()
        if hh is not None:
            hh.setStretchLastSection(True)
        
        view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        self.table_model = FileTableModel()
        view.setModel(self.table_model)
        
        header = view.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(FileTableModel.Column.CHECKBOX, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(FileTableModel.Column.CHECKBOX, 40)
            header.setSectionResizeMode(FileTableModel.Column.ICON, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(FileTableModel.Column.ICON, 50)
            header.setSectionResizeMode(FileTableModel.Column.NAME, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(FileTableModel.Column.SIZE, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(FileTableModel.Column.SIZE, 100)
            header.setSectionResizeMode(FileTableModel.Column.TYPE, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(FileTableModel.Column.TYPE, 120)
            header.setSectionResizeMode(FileTableModel.Column.TIME, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(FileTableModel.Column.TIME, 140)
            header.setSectionResizeMode(FileTableModel.Column.AI_STATUS, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(FileTableModel.Column.AI_STATUS, 80)
        
        view.doubleClicked.connect(self._on_list_double_clicked)
        sm = view.selectionModel()
        if sm is not None:
            sm.selectionChanged.connect(self._on_selection_changed)
        
        view.customContextMenuRequested.connect(self._show_context_menu)
        
        return view
    
    def _create_empty_state(self) -> QWidget:
        """创建空状态组件。"""
        widget = QWidget()
        widget.setObjectName("EmptyStateWidget")
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)
        
        self._empty_state_icon = QLabel("📭")
        self._empty_state_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_state_icon.setStyleSheet("font-size: 64px;")
        layout.addWidget(self._empty_state_icon)
        
        self._empty_state_text_label = QLabel("暂无文件")
        self._empty_state_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_state_text_label.setStyleSheet("font-size: 16px; color: #86868B;")
        layout.addWidget(self._empty_state_text_label)
        
        self._empty_state_hint_label = QLabel("拖拽文件或文件夹到此处上传，或点击上方「上传」选择文件/文件夹")
        self._empty_state_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_state_hint_label.setStyleSheet("font-size: 13px; color: #AEAEB2;")
        layout.addWidget(self._empty_state_hint_label)
        
        widget.hide()
        return widget
    
    def _connect_signals(self) -> None:
        """连接信号。"""
        pass
    
    def _set_view_mode(self, mode: str) -> None:
        """
        设置视图模式。
        
        参数:
            mode: VIEW_MODE_GRID 或 VIEW_MODE_LIST
        """
        saved_ids = {f.file_id for f in self._selected_files}
        old_mode = self._view_mode
        
        self._view_mode = mode
        
        self.grid_button.setChecked(mode == self.VIEW_MODE_GRID)
        self.list_button.setChecked(mode == self.VIEW_MODE_LIST)
        
        if mode == self.VIEW_MODE_GRID:
            self.stacked_widget.setCurrentWidget(self.grid_view)
        else:
            self.stacked_widget.setCurrentWidget(self.list_view)
        
        if old_mode != mode:
            self._sync_selection_across_views(saved_ids)
        
        self._update_empty_state()
    
    def _sync_selection_across_views(self, saved_ids: set) -> None:
        """切换视图后恢复选中状态。"""
        new_model = (
            self.grid_model if self._view_mode == self.VIEW_MODE_GRID
            else self.table_model
        )
        new_model.sync_selection_display(saved_ids)
        self._selected_files = [f for f in self._files if f.file_id in saved_ids]
        self.download_button.setEnabled(len(self._selected_files) > 0)
    
    def set_files(self, files: List[FileItem]) -> None:
        """
        设置文件列表。
        
        同时更新网格模型和列表模型，确保切换视图时两侧数据一致，
        避免大图标/方格视图下文件不渲染的问题。
        
        参数:
            files: 文件项列表
        """
        self._empty_state_override = None
        self._files = files
        filtered_files = self._filter_files(files)
        self.grid_model.set_files(filtered_files)
        self.table_model.set_files(filtered_files)
        self._update_empty_state()
    
    def _filter_files(self, files: List[FileItem]) -> List[FileItem]:
        """根据当前分类筛选文件。"""
        if self._current_category == "all":
            return files
        return [f for f in files if f.category == self._current_category]
    
    def _update_empty_state(self) -> None:
        """更新空状态显示。"""
        filtered = self._filter_files(self._files)
        has_files = len(filtered) > 0
        self.empty_state.setVisible(not has_files)
        self.stacked_widget.setVisible(has_files)

        if not has_files:
            if self._empty_state_override:
                main_text, hint_text = self._empty_state_override
                if self._empty_state_text_label:
                    self._empty_state_text_label.setText(main_text)
                if self._empty_state_hint_label:
                    self._empty_state_hint_label.setText(hint_text or "")
            else:
                category_names = {
                    "all": "文件",
                    "image": "图片",
                    "document": "文档",
                    "video": "视频",
                    "audio": "音频",
                    "other": "其他",
                }
                name = category_names.get(self._current_category, "文件")
                if self._empty_state_text_label:
                    self._empty_state_text_label.setText(f"暂无{name}")
                if self._empty_state_hint_label:
                    self._empty_state_hint_label.setText(
                        f"拖拽{name}到此处上传，或点击上方「上传」选择文件/文件夹"
                    )
    
    def get_files(self) -> List[FileItem]:
        """获取文件列表。"""
        return self._files
    
    def get_selected_files(self) -> List[FileItem]:
        """获取选中的文件。"""
        if self._view_mode == self.VIEW_MODE_GRID:
            return self.grid_model.get_selected_files()
        else:
            return self.table_model.get_selected_files()
    
    def set_category(self, category: str) -> None:
        """
        设置当前分类。
        
        参数:
            category: 分类标识
        """
        if self._current_category == category:
            return
        
        self._current_category = category
        filtered = self._filter_files(self._files)
        self.grid_model.set_files(filtered)
        self.table_model.set_files(filtered)
        self._update_empty_state()
    
    def _on_upload_files_clicked(self) -> None:
        """处理「上传文件」：选择多个文件上传。"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择文件",
            "",
            "所有文件 (*.*)"
        )
        if file_paths:
            self.upload_requested.emit(file_paths)

    def _on_upload_folder_clicked(self) -> None:
        """处理「上传文件夹」：选择文件夹，递归收集其下所有文件并带相对路径加入上传队列。"""
        folder = QFileDialog.getExistingDirectory(self, "选择要上传的文件夹", "")
        if not folder:
            return
        paths_and_names = self._collect_files_from_folder_with_paths(folder)
        if not paths_and_names:
            QMessageBox.information(
                self,
                "上传文件夹",
                "该文件夹下没有可上传的文件。"
            )
            return
        self.upload_requested.emit(paths_and_names)

    @staticmethod
    def _collect_files_from_folder(folder: str) -> List[str]:
        """递归收集文件夹下所有文件路径（不含目录）。"""
        folder_path = Path(folder)
        if not folder_path.is_dir():
            return []
        out: List[str] = []
        try:
            for p in folder_path.rglob("*"):
                if p.is_file():
                    out.append(str(p))
        except (PermissionError, OSError):
            pass
        return out

    @staticmethod
    def _collect_files_from_folder_with_paths(folder: str) -> List[tuple]:
        """递归收集 (绝对路径, upload_name)，upload_name 为相对 folder 的路径如 证件/2024/合同.pdf。"""
        folder_path = Path(folder)
        if not folder_path.is_dir():
            return []
        out: List[tuple] = []
        try:
            for p in folder_path.rglob("*"):
                if not p.is_file():
                    continue
                abs_path = str(p)
                try:
                    rel = p.relative_to(folder_path)
                    parts = rel.parts
                    name = parts[-1] if parts else p.name
                    rel_dir = "/".join(parts[:-1]) if len(parts) > 1 else ""
                    upload_name = f"{rel_dir}/{name}" if rel_dir else name
                except ValueError:
                    upload_name = p.name
                out.append((abs_path, upload_name))
        except (PermissionError, OSError):
            pass
        return out
    
    def _on_download_clicked(self) -> None:
        """处理下载按钮点击。"""
        selected = self.get_selected_files()
        if selected:
            self.download_requested.emit(selected)
    
    def _on_refresh_clicked(self) -> None:
        """处理刷新按钮点击。"""
        self._emit_refresh_requested()
    
    def _emit_refresh_requested(self) -> None:
        """发射刷新请求信号。"""
        self.refresh_requested.emit()
    
    def _on_grid_double_clicked(self, index: QModelIndex) -> None:
        """处理网格视图双击。"""
        file_item = self.grid_model.get_file_by_index(index)
        if file_item:
            self.file_double_clicked.emit(file_item)
    
    def _on_list_double_clicked(self, index: QModelIndex) -> None:
        """处理列表视图双击。"""
        file_item = self.table_model.get_file_by_index(index)
        if file_item:
            self.file_double_clicked.emit(file_item)
    
    def _on_selection_changed(
        self,
        selected: Any = None,
        deselected: Any = None
    ) -> None:
        """
        处理视图选择改变。

        从当前活动视图的 selectionModel 中提取所有选中行的 file_id，
        通过 model.sync_selection_display() 驱动 checkbox 显示刷新，
        最后用 model.get_selected_files() 获取完整的选中文件列表。
        """
        if self._view_mode == self.VIEW_MODE_GRID:
            view = self.grid_view
            model = self.grid_model
        else:
            view = self.list_view
            model = self.table_model

        sm = view.selectionModel()
        if sm is None:
            return

        selected_indexes = sm.selectedIndexes()
        selected_ids: set = set()
        for idx in selected_indexes:
            row = idx.row()
            if 0 <= row < len(model._files):
                selected_ids.add(model._files[row].file_id)

        model.sync_selection_display(selected_ids)
        self._selected_files = model.get_selected_files()
        self.download_button.setEnabled(len(self._selected_files) > 0)
        self.file_selection_changed.emit(self._selected_files)
    
    def _show_context_menu(self, pos) -> None:
        """显示右键菜单。"""
        if not self._context_menu_enabled:
            return
        
        selected = self.get_selected_files()
        if not selected:
            return
        
        menu = QMenu(self)
        
        preview_action = QAction("👁️ 预览", menu)
        preview_action.triggered.connect(lambda: self._on_preview_action(selected))
        menu.addAction(preview_action)
        
        download_action = QAction("📥 下载", menu)
        download_action.triggered.connect(lambda: self._on_download_action(selected))
        menu.addAction(download_action)
        
        rename_action = QAction("✏️ 重命名", menu)
        rename_action.triggered.connect(lambda: self._on_rename_action(selected))
        menu.addAction(rename_action)
        
        copy_link_action = QAction("🔗 复制链接", menu)
        copy_link_action.triggered.connect(lambda: self._on_copy_link_action(selected))
        menu.addAction(copy_link_action)
        
        menu.addSeparator()
        open_storage_action = QAction("📂 在文件管理器中打开存储目录", menu)
        open_storage_action.triggered.connect(lambda: self.open_storage_in_explorer_requested.emit())
        menu.addAction(open_storage_action)
        
        menu.exec(self.cursor().pos())
    
    def _on_preview_action(self, files: List[FileItem]) -> None:
        """预览文件（多选时预览第一个，双击快捷键预览第一个）。"""
        if files:
            self.preview_requested.emit(files[0])
    
    def _on_download_action(self, files: List[FileItem]) -> None:
        """下载文件。"""
        if files:
            self.download_requested.emit(files)
    
    def _on_rename_action(self, files: List[FileItem]) -> None:
        """重命名文件（仅支持单选且为文件，不含目录）。"""
        if not files or len(files) != 1:
            return
        item = files[0]
        if getattr(item, "is_dir", False):
            QMessageBox.information(self, "重命名", "请选择文件进行重命名，目录暂不支持。")
            return
        from PySide6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(
            self,
            "重命名文件",
            "新文件名：",
            text=item.filename,
        )
        if not ok or not new_name or not new_name.strip():
            return
        new_name = new_name.strip().replace("\\", "/")
        if "/" in new_name or new_name in (".", ".."):
            QMessageBox.warning(self, "重命名", "文件名不能包含路径。")
            return
        try:
            from api.files import FilesAPI
            FilesAPI().rename_file(item.file_id, new_name)
            self._show_toast("重命名成功")
            self.refresh_requested.emit()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "重命名失败", str(e))
    
    def _on_copy_link_action(self, files: List[FileItem]) -> None:
        """复制链接。"""
        if not files:
            return
        try:
            from api.files import FilesAPI
            links = []
            files_api = FilesAPI()
            for f in files:
                url = files_api.get_file_url(f.file_id)
                links.append(url)
            from PySide6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText("\n".join(links))
            self._show_toast(f"已复制 {len(links)} 个链接到剪贴板")
        except Exception as e:
            QMessageBox.warning(self, "复制失败", f"复制链接失败:\n{str(e)}")

    def _show_toast(self, message: str) -> None:
        """显示短暂提示。"""
        toast = QLabel(message, self)
        toast.setObjectName("ToastLabel")
        toast.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toast.setStyleSheet("""
            QLabel#ToastLabel {
                background-color: #1C1C1E;
                color: #FFFFFF;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
            }
        """)
        toast.adjustSize()
        toast.setFixedWidth(min(toast.width(), 400))
        pos_x = (self.width() - toast.width()) // 2
        pos_y = self.height() // 2 - toast.height()
        toast.move(pos_x, pos_y)
        toast.show()
        QTimer.singleShot(2000, toast.hide)
    
    def _on_delete_action(self, files: List[FileItem]) -> None:
        """删除文件。"""
        if len(files) == 1:
            msg = f"确定要删除文件「{files[0].filename}」吗？\n此操作不可撤销。"
        else:
            msg = f"确定要删除选中的 {len(files)} 个文件吗？\n此操作不可撤销。"
        
        reply = QMessageBox.question(
            self,
            "确认删除",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit(files)
    
    def set_drag_drop_enabled(self, enabled: bool) -> None:
        """
        设置是否启用拖放。
        
        参数:
            enabled: 是否启用
        """
        self.grid_view.setAcceptDrops(enabled)
        self.setAcceptDrops(enabled)
    
    def add_files(self, new_files: List[FileItem]) -> None:
        """
        添加文件到列表。
        
        参数:
            new_files: 要添加的文件列表
        """
        all_files = self._files + new_files
        self.set_files(all_files)
    
    def remove_files(self, file_ids: List[str]) -> None:
        """
        从列表中移除文件。

        参数:
            file_ids: 要移除的文件ID列表
        """
        remaining = [f for f in self._files if f.file_id not in file_ids]
        self.set_files(remaining)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """拖拽进入事件。"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drag_enter.emit()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """拖拽移动事件。"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        """拖拽离开事件。"""
        self.drag_leave.emit()
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        """放下事件。"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            urls = event.mimeData().urls()
            self.file_dropped.emit(urls)
        else:
            event.ignore()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """事件过滤器，处理键盘导航。"""
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()  # type: ignore[reportAttributeAccessIssue]
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                selected = self.get_selected_files()
                if selected:
                    self.file_double_clicked.emit(selected[0])
                return True
            if key == Qt.Key.Key_A and (QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier):
                self._select_all_current_view()
                return True
        return super().eventFilter(obj, event)

    def _select_all_current_view(self) -> None:
        """全选当前视图的文件。"""
        if self._view_mode == self.VIEW_MODE_GRID:
            self.grid_model.select_all()  # type: ignore[reportAttributeAccessIssue]
        else:
            self.table_model.select_all()
        self._on_selection_changed()
