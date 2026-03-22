"""
主窗口模块。

整合所有组件，提供完整的文件管理界面。

作者: AllahPan团队
"""

from typing import Optional, List
import os

from PySide6.QtCore import Qt, QTimer, QThread, Signal, QUrl, QEvent, QObject
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QMenuBar, QMenu, QMessageBox, QFileDialog,
    QFrame, QStackedWidget,
    QDialog, QDialogButtonBox, QFormLayout, QProgressBar,
    QLineEdit,
)
from PySide6.QtGui import (
    QAction,
    QDragEnterEvent,
    QDropEvent,
    QPalette,
    QColor,
    QPixmap,
    QGuiApplication,
    QIcon,
)

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import config
from theme import LIGHT_QSS, DARK_QSS
from theme.apple_effects import apply_acrylic_shadow, fade_in_widget
from api.auth import AuthAPI
from api.files import FilesAPI
from api.ai import AIAPI
from api.system import SystemAPI
from api.client import APIError
from api.tunnel import TunnelAPI
from api.ollama import OllamaAPI, get_system_summary
from widgets.sidebar_nav import SidebarNav
from widgets.search_bar import SearchBar
from widgets.status_bar import StatusBar
from widgets.upload_queue import UploadQueue
from widgets.file_browser import FileBrowser
from widgets.file_list_model import FileItem
from pages.login_page import LoginPage
from pages.settings_page import SettingsPage, TunnelConfigDialog
from pages.ops_dashboard_page import OpsDashboardPage


class UploadConfirmDialog(QDialog):
    """
    拖拽上传确认对话框。
    显示保存位置（当前所在目录）和待上传文件数量，用户确认后执行上传。
    """
    def __init__(
        self,
        parent: Optional[QWidget],
        save_location: str,
        file_count: int,
        total_size: int,
    ):
        super().__init__(parent)
        self.setWindowTitle("确认上传")
        layout = QVBoxLayout(self)
        location_display = save_location.strip().replace("\\", "/") if save_location else "根目录"
        size_str = config.format_file_size(total_size)
        intro = QLabel()
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)
        intro.setText(
            f"<p style='line-height:1.45;'>是否将 <b>{file_count}</b> 个文件"
            f"（合计 <b>{size_str}</b>）上传到当前网盘目录下的 "
            f"<b>「{location_display}」</b>？</p>"
            f"<p style='color:#86868B;font-size:12px;margin-top:8px;'>"
            "可在下方填写子目录，将文件保存到该文件夹内。</p>"
        )
        layout.addWidget(intro)
        form = QFormLayout()
        self._location_label = QLabel(location_display)
        self._location_label.setStyleSheet("color: #1D1D1F; font-size: 13px;")
        form.addRow("目标路径:", self._location_label)
        self._count_label = QLabel(f"{file_count} 个文件 · {size_str}")
        self._count_label.setStyleSheet("color: #1D1D1F; font-size: 13px;")
        form.addRow("数量与大小:", self._count_label)
        self._subdir_edit = QLineEdit()
        self._subdir_edit.setPlaceholderText("留空则保存到当前目录；可输入如 文档/2024")
        self._subdir_edit.setStyleSheet("color: #1D1D1F; font-size: 13px;")
        form.addRow("子目录（可选）:", self._subdir_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setOrientation(Qt.Orientation.Horizontal)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_btn is not None:
            ok_btn.setText("上传")
        if cancel_btn is not None:
            cancel_btn.setText("取消")
        layout.addWidget(buttons)

    def get_subdir(self) -> str:
        """返回用户输入的子目录（已去除首尾空格与反斜杠，统一为 /）。"""
        text = (self._subdir_edit.text() or "").strip().replace("\\", "/").strip("/")
        return text


class StatusRefreshWorker(QThread):
    """
    后台线程获取系统状态摘要，避免阻塞主 UI 线程。
    """
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

    def run(self) -> None:
        """在后台线程执行 API 调用。"""
        try:
            summary = get_system_summary()
            self.finished.emit(summary)
        except Exception as e:
            self.failed.emit(str(e))


class CallableWorker(QThread):
    """在后台线程执行可调用对象，通过信号返回结果或错误。"""
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, parent: Optional[QObject] = None, **kwargs):
        super().__init__(parent)
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class DownloadWorker(QThread):
    """下载多个文件，并发射进度信号。"""
    progress_updated = Signal(int, int)  # current, total
    finished = Signal(int)
    failed = Signal(str)

    def __init__(self, files: List[FileItem], save_path: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._files = files
        self._save_path = save_path

    def run(self) -> None:
        try:
            files_api = FilesAPI()
            for i, file_item in enumerate(self._files):
                dest = os.path.join(self._save_path, file_item.filename) if os.path.isdir(self._save_path) else self._save_path
                files_api.download_file(file_item.file_id, dest)
                self.progress_updated.emit(i + 1, len(self._files))
            self.finished.emit(len(self._files))
        except Exception as e:
            self.failed.emit(str(e))


class DownloadProgressDialog(QDialog):
    """下载进度对话框，显示「正在下载 k/N」和进度条。"""
    def __init__(self, total: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("下载")
        self.setMinimumWidth(320)
        layout = QVBoxLayout(self)
        self._label = QLabel(f"正在下载 0/{total}")
        self._label.setStyleSheet("color: #1D1D1F; font-size: 13px;")
        layout.addWidget(self._label)
        self._progress = QProgressBar()
        self._progress.setMinimum(0)
        self._progress.setMaximum(total)
        self._progress.setValue(0)
        layout.addWidget(self._progress)
        self.setModal(True)

    def set_progress(self, current: int, total: int) -> None:
        self._label.setText(f"正在下载 {current}/{total}")
        self._progress.setValue(current)


class MainWindow(QMainWindow):
    """
    主窗口组件。
    
    整合侧边栏、搜索栏、文件浏览器、状态栏等组件，
    提供完整的文件管理界面。
    """
    
    logout_signal = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._applying_theme = False
        self._current_path = ""  # 当前目录相对根路径，空为根目录
        self._root_directories: List[dict] = []  # 根目录下的一级目录，供侧边栏快捷入口
        self._setup_window()
        self._setup_ui()
        self._setup_theme()
        self._connect_signals()
        self._start_refresh_timer()
        self._install_system_theme_filter()

    def _install_system_theme_filter(self) -> None:
        """安装系统主题变化监听（跟随系统模式时需要）。"""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)
    
    def _setup_window(self) -> None:
        """设置窗口属性。"""
        self.setWindowTitle(f"{config.APP_NAME} - {config.APP_DESCRIPTION}")
        icon_path = config.resolve_app_icon_path()
        if icon_path is not None:
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setMinimumSize(config.WINDOW_MIN_WIDTH, config.WINDOW_MIN_HEIGHT)
        self.resize(config.WINDOW_DEFAULT_WIDTH, config.WINDOW_DEFAULT_HEIGHT)

        self.setAcceptDrops(True)
    
    def _setup_ui(self) -> None:
        """设置 UI。"""
        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        self.setCentralWidget(central_widget)
        
        self.login_page = LoginPage()
        self.login_page.login_success_signal.connect(self._on_login_success)
        central_layout.addWidget(self.login_page)
        
        self.main_widget = QWidget()
        self.main_widget.setObjectName("MainShell")
        self.main_widget.setVisible(False)
        main_layout = QHBoxLayout(self.main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        central_layout.addWidget(self.main_widget)
        
        self.sidebar = SidebarNav()
        self.sidebar.setFixedWidth(config.SIDEBAR_WIDTH)
        main_layout.addWidget(self.sidebar)
        
        content_widget = QWidget()
        content_widget.setObjectName("MainContentColumn")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        header_widget = QWidget()
        header_widget.setObjectName("MainHeaderBar")
        header_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(16)
        
        self._back_button = QLabel("◀ 返回")
        self._back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_button.setStyleSheet("color: " + config.ThemeColors.LIGHT["primary"] + "; font-size: 13px;")
        self._back_button.mousePressEvent = lambda e: self._on_breadcrumb_back()
        self._back_button.hide()
        header_layout.addWidget(self._back_button)
        
        logo_label = QLabel("📁 AllahPan")
        logo_font = logo_label.font()
        logo_font.setPointSize(20)
        logo_font.setBold(True)
        logo_label.setFont(logo_font)
        self._logo_label = logo_label
        logo_label.setStyleSheet("color: " + config.ThemeColors.LIGHT["primary"] + ";")
        header_layout.addWidget(logo_label)
        
        self._breadcrumb_container = QWidget()
        self._breadcrumb_layout = QHBoxLayout(self._breadcrumb_container)
        self._breadcrumb_layout.setContentsMargins(0, 0, 0, 0)
        self._breadcrumb_layout.setSpacing(4)
        header_layout.addWidget(self._breadcrumb_container, 1)
        
        self.search_bar = SearchBar()
        self.search_bar.setMinimumWidth(300)
        self.search_bar.setMaximumWidth(500)
        header_layout.addWidget(self.search_bar, 1)
        
        self.user_menu_button = QLabel("👤")
        self.user_menu_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.user_menu_button.mousePressEvent = lambda ev: self._show_user_menu()
        header_layout.addWidget(self.user_menu_button)
        
        content_layout.addWidget(header_widget)
        
        stacked_shell = QFrame()
        stacked_shell.setObjectName("StackedGlassPanel")
        stacked_shell.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        stacked_shell_layout = QVBoxLayout(stacked_shell)
        stacked_shell_layout.setContentsMargins(12, 10, 12, 10)
        stacked_shell_layout.setSpacing(0)

        self.stacked_pages = QStackedWidget()
        
        self.file_browser = FileBrowser()
        self.file_browser.upload_requested.connect(self._on_upload_requested)
        self.file_browser.download_requested.connect(self._on_download_requested)
        self.file_browser.file_double_clicked.connect(self._on_file_double_clicked)
        self.file_browser.delete_requested.connect(self._on_delete_requested)
        self.file_browser.refresh_requested.connect(self._on_refresh_requested)
        self.file_browser.drag_enter.connect(lambda: self._show_drop_overlay(True))
        self.file_browser.drag_leave.connect(lambda: self._show_drop_overlay(False))
        self.file_browser.file_dropped.connect(self._on_file_dropped)
        self.file_browser.open_storage_in_explorer_requested.connect(self._on_open_storage_in_explorer)
        self.file_browser.set_drag_drop_enabled(True)
        self.stacked_pages.addWidget(self.file_browser)

        self.ops_dashboard_page = OpsDashboardPage()
        self.stacked_pages.addWidget(self.ops_dashboard_page)
        
        self.settings_page = SettingsPage()
        self.settings_page.theme_changed.connect(self._on_theme_changed)
        self.settings_page.theme_changed.connect(self._on_theme_changed_login)
        self.settings_page.logout_requested.connect(self._on_logout_requested)
        self.settings_page.tunnel_config_requested.connect(self._show_tunnel_config)
        self.stacked_pages.addWidget(self.settings_page)

        stacked_shell_layout.addWidget(self.stacked_pages)
        content_layout.addWidget(stacked_shell, 1)

        apply_acrylic_shadow(self.sidebar, blur=24, offset_y=6, alpha=30)
        apply_acrylic_shadow(stacked_shell, blur=40, offset_y=12, alpha=38)
        
        self.upload_queue = UploadQueue(max_concurrent=config.UPLOAD_QUEUE_MAX_CONCURRENT)
        self.upload_queue.upload_completed.connect(self._on_upload_completed)
        self.upload_queue.upload_failed.connect(self._on_upload_failed)
        content_layout.addWidget(self.upload_queue)
        
        self.status_bar = StatusBar()
        content_layout.addWidget(self.status_bar)
        
        main_layout.addWidget(content_widget, 1)
    
    def _setup_theme(self) -> None:
        """设置主题。"""
        self._apply_theme(config.ThemeMode.LIGHT)
    
    def _apply_theme(self, mode: str) -> None:
        """应用主题。"""
        if self._applying_theme:
            return
        self._applying_theme = True
        try:
            if mode == config.ThemeMode.SYSTEM:
                palette = QGuiApplication.palette()
                is_dark = palette.color(palette.ColorRole.Window).lightness() < 128
                mode = config.ThemeMode.DARK if is_dark else config.ThemeMode.LIGHT

            if mode == config.ThemeMode.DARK:
                qss = DARK_QSS
                colors = config.ThemeColors.DARK
            else:
                qss = LIGHT_QSS
                colors = config.ThemeColors.LIGHT

            self.setStyleSheet(qss)
            if hasattr(self, "_logo_label"):
                self._logo_label.setStyleSheet(
                    f"color: {colors['primary']};"
                )
        finally:
            self._applying_theme = False

    def _switch_main_page(self, widget: QWidget) -> None:
        """切换主内容堆叠页并做短暂淡入动画。"""
        if self.stacked_pages.currentWidget() is widget:
            return
        prev = self.stacked_pages.currentWidget()
        if prev is not None and prev.graphicsEffect() is not None:
            prev.setGraphicsEffect(None)  # type: ignore[arg-type]
        self.stacked_pages.setCurrentWidget(widget)
        fade_in_widget(widget, self, duration_ms=240)

    def _connect_signals(self) -> None:
        """连接信号。"""
        self.sidebar.category_changed.connect(self._on_category_changed)
        self.search_bar.search_triggered.connect(self._on_search_triggered)
        self.status_bar.storage_clicked.connect(self._on_storage_clicked)
        self.status_bar.ollama_clicked.connect(self._on_ollama_clicked)
        self.status_bar.tunnel_clicked.connect(self._on_tunnel_clicked)
    
    def _start_refresh_timer(self) -> None:
        """启动刷新定时器（状态栏 + 文件列表）。"""
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_status)
        self._refresh_timer.start(30000)
        # 定期刷新文件列表，以便后端解析完成后「AI状态」列能显示「已解析」
        self._file_list_refresh_timer = QTimer(self)
        self._file_list_refresh_timer.timeout.connect(self._on_file_list_refresh_tick)
        self._file_list_refresh_timer.start(15000)

    def _on_file_list_refresh_tick(self) -> None:
        """定时刷新文件列表（仅当当前在文件浏览页时），以更新 AI 解析状态。"""
        if not self.main_widget.isVisible():
            return
        if self.stacked_pages.currentWidget() != self.file_browser:
            return
        self._load_files()

    def _on_login_success(self, user: dict) -> None:
        """处理登录成功。"""
        self._session_expired_handled = False  # 登录后允许下次会话过期时再次处理
        self.login_page.setVisible(False)
        self.main_widget.setVisible(True)
        # 若因会话过期曾停止过定时器，重新登录后需恢复
        if getattr(self, "_refresh_timer", None) and not self._refresh_timer.isActive():
            self._start_refresh_timer()
        self._load_files()
        self._refresh_status()
    
    def _load_files(self) -> None:
        """加载当前路径下的文件列表（以磁盘为事实来源）。"""
        self.file_browser.show_loading(True, "加载中…")
        self.file_browser.clear_empty_state_override()
        current_path = getattr(self, "_current_path", "") or ""
        def _fetch():
            files_api = FilesAPI()
            return files_api.list_files(path=current_path if current_path else None)
        w = CallableWorker(_fetch, parent=self)
        w.finished.connect(self._on_load_files_ready, Qt.ConnectionType.QueuedConnection)
        w.failed.connect(self._on_load_files_failed, Qt.ConnectionType.QueuedConnection)
        w.start()

    def _on_load_files_ready(self, result: dict) -> None:
        """文件列表加载成功（主线程）。合并目录项与文件项，更新面包屑与侧边栏快捷入口。"""
        self.file_browser.show_loading(False)
        directories = result.get("directories", [])
        files_data = result.get("files", [])
        current_path = getattr(self, "_current_path", "") or ""
        if not current_path:
            self._root_directories = directories
        else:
            self._root_directories = getattr(self, "_root_directories", [])
        file_items: List[FileItem] = []
        for d in directories:
            file_items.append(FileItem(
                file_id="",
                filename=d.get("name", ""),
                filepath="",
                size=0,
                filetype="inode/directory",
                is_dir=True,
                virtual_path=d.get("path", ""),
            ))
        for f in files_data:
            file_items.append(FileItem.from_dict(f))
        self.file_browser.set_files(file_items)
        counts = {"all": len(files_data)}
        for category in ("image", "document", "video", "audio", "other"):
            counts[category] = sum(1 for f in file_items if not getattr(f, "is_dir", False) and f.category == category)
        self.sidebar.update_file_counts(counts)
        self.sidebar.set_current_path(current_path)
        self.sidebar.set_root_directories(self._root_directories)
        self._update_breadcrumb()

    def _update_breadcrumb(self) -> None:
        """更新面包屑与返回按钮显示（可点击跳转层级）。"""
        path = (getattr(self, "_current_path", "") or "").strip().replace("\\", "/")
        if self._back_button:
            self._back_button.setVisible(bool(path))
        primary = config.get_current_colors().get("primary", config.ThemeColors.LIGHT.get("primary", "#007AFF"))
        while self._breadcrumb_layout.count():
            item = self._breadcrumb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        parts = path.strip("/").split("/") if path else []
        for i in range(len(parts) + 1):
            if i > 0:
                sep = QLabel(" / ")
                sep.setStyleSheet("color: #86868B; font-size: 13px;")
                self._breadcrumb_layout.addWidget(sep)
            link_path = "/".join(parts[:i]) if i > 0 else ""
            label_text = parts[i - 1] if i > 0 else "根目录"
            link = QLabel(label_text)
            link.setCursor(Qt.CursorShape.PointingHandCursor)
            link.setStyleSheet(f"color: {primary}; font-size: 13px;")
            link.mousePressEvent = lambda e, p=link_path: self._on_breadcrumb_click(p)
            self._breadcrumb_layout.addWidget(link)
        self._breadcrumb_layout.addStretch()

    def _on_breadcrumb_click(self, path: str) -> None:
        """点击面包屑某级，跳转至该路径。"""
        self._current_path = path
        self._load_files()

    def _on_breadcrumb_back(self) -> None:
        """返回上级目录。"""
        path = (getattr(self, "_current_path", "") or "").strip().replace("\\", "/")
        if not path:
            return
        parts = path.strip("/").split("/")
        if len(parts) <= 1:
            self._current_path = ""
        else:
            self._current_path = "/".join(parts[:-1])
        self._load_files()

    def _is_auth_error(self, error: str) -> bool:
        """判断是否为认证/登录过期类错误，用于统一处理会话过期并避免重复弹窗。"""
        if not error:
            return False
        return "认证失败" in error or "请重新登录" in error

    def _handle_session_expired(self) -> None:
        """会话过期：停止后台刷新、显示登录页，只提示一次。"""
        if getattr(self, "_session_expired_handled", False):
            return
        self._session_expired_handled = True
        self._refresh_timer.stop()
        if hasattr(self, "_file_list_refresh_timer") and self._file_list_refresh_timer:
            self._file_list_refresh_timer.stop()
        worker = getattr(self, "_status_worker", None)
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            worker.wait(2000)
        self._status_worker = None
        self.main_widget.setVisible(False)
        self.login_page.setVisible(True)
        self.login_page.reset()
        QMessageBox.information(
            self,
            "登录已过期",
            "登录已过期，请重新登录。",
        )
        # _session_expired_handled 在 _on_login_success 中清除，避免同一过期周期内重复弹窗

    def _on_load_files_failed(self, error: str) -> None:
        """文件列表加载失败（主线程）。认证失败时统一跳转登录页，避免重复弹窗。"""
        self.file_browser.show_loading(False)
        if self._is_auth_error(error):
            self._handle_session_expired()
            return
        QMessageBox.warning(self, "加载失败", f"加载文件列表失败:\n{error}")
    
    def _refresh_status(self) -> None:
        """刷新状态信息（在后台线程中执行 API 调用）。"""
        # 防止重复刷新
        if hasattr(self, '_status_worker') and self._status_worker is not None:
            if self._status_worker.isRunning():
                return

        self._status_worker = StatusRefreshWorker(self)
        self._status_worker.finished.connect(self._on_status_ready, Qt.ConnectionType.QueuedConnection)
        self._status_worker.failed.connect(self._on_status_failed, Qt.ConnectionType.QueuedConnection)
        self._status_worker.start()

    def _on_status_ready(self, summary: dict) -> None:
        """状态获取成功后的处理（已在主线程）。"""
        self.status_bar.set_from_summary(summary)
        if self._status_worker:
            self._status_worker.deleteLater()
        self._status_worker = None

    def _on_status_failed(self, error: str) -> None:
        """状态获取失败后的处理（已在主线程）。认证失败时统一跳转登录页，避免重复请求与弹窗。"""
        if self._status_worker:
            self._status_worker.deleteLater()
        self._status_worker = None
        if self._is_auth_error(error):
            self._handle_session_expired()
            return
        print(f"刷新状态失败: {error}")
        # 非认证错误时，回退到单独获取存储信息（在后台线程执行，避免阻塞）
        def _fetch_storage():
            system_api = SystemAPI()
            return system_api.get_storage_info()
        w = CallableWorker(_fetch_storage, parent=self)
        w.finished.connect(
            lambda info: self.status_bar.set_storage_info(
                used_space=info.get("used_space", 0),
                total_space=info.get("total_space", 0)
            ),
            Qt.ConnectionType.QueuedConnection
        )
        w.failed.connect(
            lambda err: self._on_status_storage_fallback_failed(err),
            Qt.ConnectionType.QueuedConnection
        )
        w.start()

    def _on_status_storage_fallback_failed(self, error: str) -> None:
        """状态刷新失败后回退的存储信息请求也失败时（如认证失败），统一处理。"""
        if self._is_auth_error(error):
            self._handle_session_expired()
    
    def _on_category_changed(self, category: str) -> None:
        """处理分类切换。"""
        if category == "ops_dashboard":
            self._switch_main_page(self.ops_dashboard_page)
            self.ops_dashboard_page.on_show()
            return

        if self.stacked_pages.currentWidget() != self.file_browser:
            self._switch_main_page(self.file_browser)

        self.file_browser.set_category(category)
    
    def _on_search_triggered(self, keyword: str, is_ai: bool) -> None:
        """处理搜索触发。"""
        if self.stacked_pages.currentWidget() != self.file_browser:
            self._switch_main_page(self.file_browser)

        if not keyword:
            self._load_files()
            return
        if not is_ai:
            current_path = (getattr(self, "_current_path", "") or "").strip().replace("\\", "/")
            self.file_browser.show_loading(True, "搜索中…")

            def _search_under():
                return FilesAPI().search_under(q=keyword, path=current_path or None, limit=200)

            def _on_filename_ready(data: dict) -> None:
                self.file_browser.show_loading(False)
                files_data = data.get("files", []) or []
                total = int(data.get("total", len(files_data)))
                file_items = [FileItem.from_dict(f) for f in files_data]
                if total == 0:
                    self.file_browser.set_files([])
                    self.file_browser.set_empty_state_override(
                        f'未找到文件名包含 "{keyword}" 的结果',
                        "可尝试其他关键词或切换到图片/语义搜索",
                    )
                else:
                    self.file_browser.set_files(file_items)
                self.status_bar.set_sync_status(True, f"文件名搜索: {total} 结果")

            def _on_filename_failed(err: str) -> None:
                self.file_browser.show_loading(False)
                QMessageBox.warning(self, "搜索失败", f"文件名搜索失败:\n{err}")

            w = CallableWorker(_search_under, parent=self)
            w.finished.connect(_on_filename_ready, Qt.ConnectionType.QueuedConnection)
            w.failed.connect(_on_filename_failed, Qt.ConnectionType.QueuedConnection)
            w.start()
            return

        self.file_browser.show_loading(True, "AI 搜索中…")

        def _search():
            ai_api = AIAPI()
            return ai_api.search(keyword)

        def _on_search_ready(data):
            self.file_browser.show_loading(False)
            files_data = data.get("results", [])
            total = data.get("total", 0)
            file_items = [FileItem.from_dict(f) for f in files_data]
            if total == 0:
                self.file_browser.set_files([])
                self.file_browser.set_empty_state_override(
                    f'未找到与 "{keyword}" 相关的结果',
                    "尝试其他关键词或使用文件名搜索",
                )
            else:
                self.file_browser.set_files(file_items)
            self.status_bar.set_sync_status(True, f"AI搜索: {total} 结果")

        def _on_search_failed(err):
            self.file_browser.show_loading(False)
            QMessageBox.warning(self, "搜索失败", f"搜索失败:\n{err}")

        w = CallableWorker(_search, parent=self)
        w.finished.connect(_on_search_ready, Qt.ConnectionType.QueuedConnection)
        w.failed.connect(_on_search_failed, Qt.ConnectionType.QueuedConnection)
        w.start()
    
    def _on_upload_requested(self, payload) -> None:
        """处理上传请求。支持 List[str] 或 List[Tuple[str, str]]（路径, upload_name）。先弹确认框（含可选子目录），再加入队列。"""
        if not payload:
            return
        first = payload[0]
        if isinstance(first, (list, tuple)) and len(first) >= 2:
            paths_with_names = [(p[0], p[1]) for p in payload]
            file_count = len(paths_with_names)
            total_size = sum(os.path.getsize(p[0]) for p in paths_with_names if os.path.isfile(p[0]))
        else:
            paths_with_names = [(p, os.path.basename(p)) for p in payload if os.path.isfile(p)]
            file_count = len(paths_with_names)
            total_size = sum(os.path.getsize(p[0]) for p in paths_with_names)
        if not paths_with_names:
            return
        current_path = (getattr(self, "_current_path", "") or "").strip().replace("\\", "/")
        dialog = UploadConfirmDialog(
            self,
            save_location=current_path,
            file_count=file_count,
            total_size=total_size,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        subdir = dialog.get_subdir()
        base = "/".join(filter(None, [current_path.strip("/"), subdir.strip("/")])) if (current_path or subdir) else ""
        full_list = []
        for local_path, upload_name in paths_with_names:
            full_upload_name = f"{base}/{upload_name}".lstrip("/") if base else upload_name
            full_list.append((local_path, full_upload_name))
        self.upload_queue.add_files_with_upload_names(full_list)
    
    def _on_download_requested(self, files: List[FileItem]) -> None:
        """处理下载请求（下载在后台线程执行，带进度）。"""
        if not files:
            return
        if len(files) == 1:
            save_path, _ = QFileDialog.getSaveFileName(
                self, "保存文件", files[0].filename, "所有文件 (*.*)"
            )
        else:
            folder = QFileDialog.getExistingDirectory(self, "选择保存文件夹")
            if not folder:
                return
            save_path = folder
        if not save_path:
            return

        dialog = DownloadProgressDialog(len(files), self)
        worker = DownloadWorker(files, save_path, parent=self)
        worker.progress_updated.connect(
            lambda cur, total: dialog.set_progress(cur, total),
            Qt.ConnectionType.QueuedConnection
        )
        worker.finished.connect(
            lambda n: (dialog.accept(), QMessageBox.information(self, "下载完成", f"已下载 {n} 个文件"), self._load_files()),
            Qt.ConnectionType.QueuedConnection
        )
        worker.failed.connect(
            lambda err: (dialog.reject(), QMessageBox.warning(self, "下载失败", f"下载失败:\n{err}")),
            Qt.ConnectionType.QueuedConnection
        )
        dialog.show()
        worker.start()
    
    def _on_file_double_clicked(self, file_item: FileItem) -> None:
        """处理文件/文件夹双击。文件夹则进入该目录，文件则预览。"""
        if getattr(file_item, "is_dir", False) and getattr(file_item, "virtual_path", ""):
            self._current_path = file_item.virtual_path
            self._load_files()
            return
        self._preview_file(file_item)
    
    def _preview_file(self, file_item: FileItem) -> None:
        """预览文件（拉取内容在后台线程执行）。"""
        if getattr(file_item, "is_dir", False):
            return
        self.file_browser.show_loading(True, "预览加载中…")
        def _fetch():
            files_api = FilesAPI()
            return files_api.preview_file(file_item.file_id)

        def _on_preview_ready(content: bytes):
            self.file_browser.show_loading(False)
            if not content:
                return
            if file_item.is_image:
                from PySide6.QtWidgets import QLabel, QDialog, QVBoxLayout, QScrollArea
                dialog = QDialog(self)
                dialog.setWindowTitle(f"预览: {file_item.filename}")
                dialog.resize(800, 600)
                layout = QVBoxLayout(dialog)
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                pixmap = QPixmap()
                pixmap.loadFromData(content)
                label = QLabel()
                label.setPixmap(pixmap)
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                scroll.setWidget(label)
                layout.addWidget(scroll)
                dialog.exec()
            else:
                import tempfile
                suffix = os.path.splitext(file_item.filename)[1]
                fd, temp_path = tempfile.mkstemp(suffix=suffix)
                os.close(fd)
                with open(temp_path, "wb") as f:
                    f.write(content)
                if not self._open_file_cross_platform(temp_path):
                    QMessageBox.warning(
                        self, "无法打开", f"无法自动打开文件:\n{file_item.filename}"
                    )

        def _on_preview_failed(err):
            self.file_browser.show_loading(False)
            QMessageBox.warning(self, "预览失败", f"预览失败:\n{err}")
        w = CallableWorker(_fetch, parent=self)
        w.finished.connect(_on_preview_ready, Qt.ConnectionType.QueuedConnection)
        w.failed.connect(_on_preview_failed, Qt.ConnectionType.QueuedConnection)
        w.start()
    
    def _on_delete_requested(self, files: List[FileItem]) -> None:
        """处理删除请求：调用后端 DELETE /files/{id}，遇错即停并刷新列表。"""
        to_delete = [f for f in files if not getattr(f, "is_dir", False)]
        if not to_delete:
            return
        api = FilesAPI()
        deleted = 0
        for f in to_delete:
            try:
                api.delete_file(f.file_id)
                deleted += 1
            except APIError as e:
                QMessageBox.warning(
                    self,
                    "删除失败",
                    f"删除「{f.filename}」失败：\n{e}\n\n已成功删除 {deleted} 个文件。",
                )
                self._load_files()
                return
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(
                    self,
                    "删除失败",
                    f"删除「{f.filename}」时出错：\n{e}\n\n已成功删除 {deleted} 个文件。",
                )
                self._load_files()
                return
        if deleted:
            QMessageBox.information(self, "删除完成", f"已删除 {deleted} 个文件。")
        self._load_files()
    
    def _on_upload_completed(self, task_id: str, result: dict) -> None:
        """处理上传完成。"""
        if hasattr(self, "_refresh_debounce_timer"):
            self._refresh_debounce_timer.stop()
        if not hasattr(self, "_refresh_debounce_timer"):
            self._refresh_debounce_timer = QTimer(self)
            self._refresh_debounce_timer.setSingleShot(True)
            self._refresh_debounce_timer.timeout.connect(self._load_files)
        self._refresh_debounce_timer.start(800)

    def _on_refresh_requested(self) -> None:
        """处理刷新请求（来自 FileBrowser）。"""
        self._load_files()
    
    def _on_upload_failed(self, task_id: str, error: str) -> None:
        """处理上传失败。"""
        QMessageBox.warning(self, "上传失败", f"文件上传失败:\n{error}")
    
    def _on_open_storage_in_explorer(self) -> None:
        """在系统文件管理器中打开存储目录。"""
        try:
            system_api = SystemAPI()
            info = system_api.get_storage_directory()
            path = info.get("path")
            if path and info.get("exists", True):
                if self._open_file_cross_platform(path):
                    return
            QMessageBox.information(
                self,
                "打开存储目录",
                f"存储目录路径:\n{path or '未知'}\n\n若无法自动打开，请手动复制路径到文件管理器。",
            )
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"获取存储目录失败:\n{str(e)}")

    def _on_storage_clicked(self) -> None:
        """处理存储信息点击。"""
        try:
            system_api = SystemAPI()
            info = system_api.get_storage_info()
            
            used = config.format_file_size(info.get("used_space", 0))
            total = config.format_file_size(info.get("total_space", 0))
            free = config.format_file_size(info.get("free_space", 0))
            count = info.get("file_count", 0)
            
            QMessageBox.information(
                self,
                "存储信息",
                f"总空间: {total}\n"
                f"已使用: {used}\n"
                f"可用空间: {free}\n"
                f"文件数量: {count}"
            )
        except Exception as e:
            QMessageBox.warning(self, "获取失败", f"获取存储信息失败:\n{str(e)}")
    
    def _on_ollama_clicked(self) -> None:
        """处理 Ollama 状态点击。"""
        try:
            ollama_api = OllamaAPI()
            status = ollama_api.get_status()
            
            info_lines = [
                f"状态: {status.get('status', '未知')}",
                f"运行中: {'是' if status.get('is_running') else '否'}",
                f"服务可用: {'是' if status.get('service_available') else '否'}",
                f"端口: {status.get('port', 11434)}",
            ]
            
            models = status.get("loaded_models", [])
            if models:
                info_lines.append(f"已加载模型: {len(models)}")
                for m in models[:3]:
                    name = m.get("name", "未知")
                    info_lines.append(f"  - {name}")
                if len(models) > 3:
                    info_lines.append(f"  ... 还有 {len(models) - 3} 个模型")
            else:
                info_lines.append("已加载模型: 无")
            
            if status.get("error"):
                info_lines.append(f"\n错误: {status.get('error')}")
            
            QMessageBox.information(
                self,
                "Ollama 引擎状态",
                "\n".join(info_lines)
            )
        except Exception as e:
            QMessageBox.warning(self, "获取失败", f"获取 Ollama 状态失败:\n{str(e)}")
    
    def _on_tunnel_clicked(self) -> None:
        """处理 Tunnel 状态点击。"""
        try:
            tunnel_api = TunnelAPI()
            status = tunnel_api.get_status()
            
            info_lines = [
                f"状态: {status.get('status', '未知')}",
                f"运行中: {'是' if status.get('is_running') else '否'}",
                f"Token 已配置: {'是' if status.get('token_configured') else '否'}",
            ]
            
            domain = status.get("domain")
            if domain:
                info_lines.append(f"域名: {domain}")
            
            url = status.get("connection_url")
            if url:
                info_lines.append(f"访问地址: {url}")
            
            if status.get("is_running") and status.get("uptime"):
                uptime_minutes = int(status.get("uptime", 0) / 60)
                info_lines.append(f"运行时长: {uptime_minutes} 分钟")
            
            if status.get("error"):
                info_lines.append(f"\n错误: {status.get('error')}")
            
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("远程访问状态")
            msg_box.setText("\n".join(info_lines))
            
            if not status.get("is_running") and status.get("token_configured"):
                msg_box.setStandardButtons(
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
                msg_box.setText(
                    "\n".join(info_lines) + "\n\n是否现在启动远程访问？"
                )
                msg_box.button(QMessageBox.StandardButton.Yes).setText("启动")
                msg_box.button(QMessageBox.StandardButton.No).setText("稍后")
                
                if msg_box.exec() == QMessageBox.StandardButton.Yes:
                    self._start_tunnel()
            else:
                msg_box.exec()
                
        except Exception as e:
            QMessageBox.warning(self, "获取失败", f"获取远程访问状态失败:\n{str(e)}")
    
    def _start_tunnel(self) -> None:
        """启动 Tunnel。"""
        try:
            from api.tunnel import start_tunnel
            result = start_tunnel()
            if result.get("success"):
                QMessageBox.information(
                    self,
                    "成功",
                    f"远程访问已启动！\n\n"
                    f"访问地址: {result.get('connection_info', {}).get('url', '请刷新查看')}"
                )
                self._refresh_status()
            else:
                QMessageBox.warning(
                    self,
                    "启动失败",
                    result.get("message", "无法启动远程访问")
                )
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动远程访问失败:\n{str(e)}")
    
    def _on_theme_changed(self, mode: str) -> None:
        """处理主题改变。"""
        self._apply_theme(mode)

    def _on_theme_changed_login(self, mode: str) -> None:
        """处理主题改变——同时更新登录页面。"""
        self.login_page.update_theme_colors()
    
    def _on_logout_requested(self) -> None:
        """处理退出登录。"""
        reply = QMessageBox.question(
            self,
            "退出登录",
            "确定要退出登录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._refresh_timer.stop()
            if hasattr(self, "_file_list_refresh_timer") and self._file_list_refresh_timer:
                self._file_list_refresh_timer.stop()
            worker = getattr(self, "_status_worker", None)
            if worker is not None and worker.isRunning():
                worker.requestInterruption()
                worker.wait(3000)
            self._status_worker = None

            auth_api = AuthAPI()
            auth_api.logout()
            
            self.main_widget.setVisible(False)
            self.login_page.setVisible(True)
            self.login_page.reset()
    
    def _show_user_menu(self) -> None:
        """显示用户菜单。"""
        menu = QMenu(self)
        
        user = config.get_auth_user()
        username = user.get("username", "用户") if user else "用户"
        
        profile_action = QAction(f"👤 {username}", menu)
        profile_action.setEnabled(False)
        menu.addAction(profile_action)
        
        menu.addSeparator()
        
        settings_action = QAction("⚙️ 设置", menu)
        settings_action.triggered.connect(lambda: self._show_settings())
        menu.addAction(settings_action)
        
        menu.addSeparator()
        
        logout_action = QAction("🚪 退出登录", menu)
        logout_action.triggered.connect(self._on_logout_requested)
        menu.addAction(logout_action)
        
        menu.exec(self.user_menu_button.cursor().pos())
    
    def _show_settings(self) -> None:
        """显示设置页面。"""
        self.settings_page.refresh_status()
        self._switch_main_page(self.settings_page)
    
    def _show_tunnel_config(self) -> None:
        """显示 Tunnel 配置对话框。"""
        dialog = TunnelConfigDialog(self)
        if dialog.exec() == TunnelConfigDialog.DialogCode.Accepted:
            self._refresh_status()
            # 若当前在设置页，刷新设置页的远程访问状态，使「未配置」立即变为「已配置」
            self.settings_page.refresh_status()
    
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """拖拽进入事件。"""
        mime = event.mimeData()
        if mime is not None and mime.hasUrls():
            event.acceptProposedAction()
            self._show_drop_overlay(True)
        else:
            event.ignore()
    
    def dragLeaveEvent(self, event) -> None:
        """拖拽离开事件。"""
        self._show_drop_overlay(False)
    
    def _on_file_dropped(self, urls: list) -> None:
        """处理拖拽释放：先隐藏毛玻璃层，再解析文件，弹出确认框（保存位置 + 数量），确认后上传到当前目录。"""
        self._show_drop_overlay(False)

        INVALID_NAMES = {
            "CON", "PRN", "AUX", "NUL",
            "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
            "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
        }
        INVALID_CHARS = set(':.*?<>|')

        # 统一收集为 (本地路径, 云端相对名)，云端名暂不含当前目录前缀
        paths_with_names: List[tuple] = []

        for url in urls:
            path = url.toLocalFile()
            if not path:
                continue
            if os.path.isfile(path):
                basename = os.path.basename(path).upper()
                name_only = os.path.splitext(basename)[0]
                if name_only in INVALID_NAMES:
                    continue
                if any(c in os.path.basename(path) for c in INVALID_CHARS):
                    continue
                if os.path.basename(path).startswith("."):
                    continue
                paths_with_names.append((path, os.path.basename(path)))
            elif os.path.isdir(path):
                root_dir = path
                for root, _, files in os.walk(path):
                    for f in files:
                        if f.startswith("."):
                            continue
                        if f.upper() in ("DESKTOP.INI", "THUMBS.DB", ".DS_STORE"):
                            continue
                        fp = os.path.join(root, f)
                        basename = os.path.basename(fp).upper()
                        name_only = os.path.splitext(basename)[0]
                        if name_only in INVALID_NAMES:
                            continue
                        if any(c in f for c in INVALID_CHARS):
                            continue
                        try:
                            rel = os.path.relpath(os.path.dirname(fp), root_dir)
                            rel = rel.replace("\\", "/")
                            upload_name = f if rel == "." else f"{rel}/{f}"
                            paths_with_names.append((fp, upload_name))
                        except ValueError:
                            paths_with_names.append((fp, f))

        if not paths_with_names:
            return

        file_count = len(paths_with_names)
        total_size = sum(os.path.getsize(p[0]) for p in paths_with_names)
        current_path = (getattr(self, "_current_path", "") or "").strip().replace("\\", "/")

        dialog = UploadConfirmDialog(
            self,
            save_location=current_path,
            file_count=file_count,
            total_size=total_size,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        subdir = dialog.get_subdir()
        base = "/".join(filter(None, [current_path.strip("/"), subdir.strip("/")])) if (current_path or subdir) else ""

        full_list = []
        for local_path, upload_name in paths_with_names:
            full_upload_name = f"{base}/{upload_name}".lstrip("/") if base else upload_name
            full_list.append((local_path, full_upload_name))
        self.upload_queue.add_files_with_upload_names(full_list)

    def dropEvent(self, event: QDropEvent) -> None:
        """放下事件（MainWindow 级别的处理，作为 FileBrowser 的后备）。"""
        self._on_file_dropped(event.mimeData().urls())
        event.acceptProposedAction()

    def closeEvent(self, event) -> None:
        """应用关闭时清理资源。"""
        self._refresh_timer.stop()
        if hasattr(self, "_file_list_refresh_timer") and self._file_list_refresh_timer:
            self._file_list_refresh_timer.stop()
        worker = getattr(self, "_status_worker", None)
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            worker.wait(3000)
        self._status_worker = None
        self.upload_queue.cancel_all()
        self.upload_queue.hide()
        from api.client import close_api_client
        close_api_client()
        event.accept()
    
    def changeEvent(self, event) -> None:
        """处理窗口状态变化（最小化时暂停刷新timer）。"""
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized:
                self._refresh_timer.stop()
                if hasattr(self, "_file_list_refresh_timer") and self._file_list_refresh_timer:
                    self._file_list_refresh_timer.stop()
            elif self.isVisible() and not (self.windowState() & Qt.WindowState.WindowMinimized):
                self._refresh_timer.start()
                if hasattr(self, "_file_list_refresh_timer") and self._file_list_refresh_timer:
                    self._file_list_refresh_timer.start(15000)

    def eventFilter(self, obj, event) -> bool:
        """全局事件过滤器，监听系统主题变化。"""
        if event.type() == QEvent.Type.PaletteChange:
            if config._current_theme_mode == config.ThemeMode.SYSTEM:
                self._apply_theme(config.ThemeMode.SYSTEM)
        return super().eventFilter(obj, event)

    def _show_drop_overlay(self, show: bool) -> None:
        """显示/隐藏拖拽覆盖层（仅在文件浏览页时，于文件显示区域显示毛玻璃效果）。"""
        if self.stacked_pages.currentWidget() is not self.file_browser:
            return
        self.file_browser.show_drop_overlay(show)
    
    def keyPressEvent(self, event) -> None:
        """键盘事件。"""
        if event.key() == Qt.Key.Key_F5:
            self._load_files()
        elif event.key() == Qt.Key.Key_Escape:
            self._switch_main_page(self.file_browser)
        elif event.key() == Qt.Key.Key_Backspace:
            if self.stacked_pages.currentWidget() == self.file_browser and (getattr(self, "_current_path", "") or ""):
                self._on_breadcrumb_back()
                return
        super().keyPressEvent(event)

    @staticmethod
    def _open_file_cross_platform(file_path: str) -> bool:
        """跨平台打开文件。

        替代 os.startfile()，兼容 Windows/macOS/Linux。

        参数:
            file_path: 要打开的文件路径

        返回:
            bool: 打开是否成功
        """
        import subprocess
        import sys

        try:
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", file_path], check=True, capture_output=True)
            else:
                subprocess.run(["xdg-open", file_path], check=True, capture_output=True)
            return True
        except Exception:
            return False
