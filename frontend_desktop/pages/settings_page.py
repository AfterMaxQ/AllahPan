"""
设置页面模块。

提供应用设置界面，包括：
- 外观设置
- 远程访问配置（Tunnel）
- 存储路径配置
- 开机自启配置
- 日志查看
- 账号管理

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-20
"""

import json
import os
import socket
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QFormLayout, QComboBox,
    QLineEdit, QCheckBox, QMessageBox, QTextEdit,
    QDialog, QDialogButtonBox, QFileDialog, QSpinBox,
    QScrollArea, QSizePolicy, QProgressBar
)
from PySide6.QtGui import QFont

import sys
from pathlib import Path as SysPath
sys.path.insert(0, str(SysPath(__file__).parent.parent))

import config
from config import ThemeMode
from theme import LIGHT_QSS, DARK_QSS


class SettingsWorker(QThread):
    """在后台执行可调用对象，避免阻塞设置页 UI。"""
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, parent=None, **kwargs):
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


class LogViewerDialog(QDialog):
    """日志查看对话框。"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("日志查看器")
        self.setMinimumSize(700, 500)
        self._setup_ui()
        self.load_logs()
    
    def _setup_ui(self) -> None:
        """设置 UI。"""
        layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self.load_logs)
        toolbar.addWidget(self.refresh_btn)
        
        self.level_label = QLabel("日志级别:")
        toolbar.addWidget(self.level_label)
        
        self.level_combo = QComboBox()
        self.level_combo.addItems(["全部", "DEBUG", "INFO", "WARNING", "ERROR"])
        self.level_combo.setCurrentIndex(1)
        self.level_combo.currentIndexChanged.connect(self.filter_logs)
        toolbar.addWidget(self.level_combo)
        
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self.clear_logs)
        toolbar.addWidget(self.clear_btn)
        
        toolbar.addStretch()
        
        self.open_file_btn = QPushButton("📁 打开日志文件")
        self.open_file_btn.clicked.connect(self.open_log_file)
        toolbar.addWidget(self.open_file_btn)
        
        layout.addLayout(toolbar)
        
        # 日志显示区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self.log_text)
        
        # 按钮栏
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
    
    def load_logs(self) -> None:
        """加载日志。"""
        log_dir = Path.home() / ".allahpan" / "logs"
        if not log_dir.exists():
            self.log_text.setPlainText("暂无日志文件\n\n日志文件位于: ~/.allahpan/logs/")
            return
        
        log_files = sorted(log_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
        
        if not log_files:
            self.log_text.setPlainText("暂无日志文件\n\n日志文件位于: ~/.allahpan/logs/")
            return
        
        # 读取最新的日志文件
        latest_log = log_files[0]
        try:
            with open(latest_log, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            
            lines = content.split("\n")
            last_lines = lines[-500:] if len(lines) > 500 else lines
            self.log_text.setPlainText("\n".join(last_lines))
            
            # 滚动到底部
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.log_text.setTextCursor(cursor)
        except Exception as e:
            self.log_text.setPlainText(f"读取日志失败: {str(e)}")
    
    def filter_logs(self, index: int) -> None:
        """根据日志级别过滤。"""
        level_map = {0: None, 1: "DEBUG", 2: "INFO", 3: "WARNING", 4: "ERROR"}
        # 暂时不做过滤，因为重新加载日志代价较高
        pass
    
    def clear_logs(self) -> None:
        """清空显示。"""
        self.log_text.clear()
    
    def open_log_file(self) -> None:
        """打开日志文件目录。"""
        log_dir = Path.home() / ".allahpan" / "logs"
        if log_dir.exists():
            webbrowser.open(f"file://{log_dir}")
        else:
            QMessageBox.information(self, "提示", f"日志目录不存在:\n{log_dir}")


class StoragePathDialog(QDialog):
    """存储路径配置对话框。"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("配置存储路径")
        self.setMinimumSize(500, 150)
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """设置 UI。"""
        layout = QVBoxLayout(self)
        
        info_label = QLabel(
            "选择文件存储的根目录。修改后需要重启应用生效。"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        path_layout = QHBoxLayout()
        
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("选择存储目录...")
        self.path_input.setText(str(config.STORAGE_DIR))
        path_layout.addWidget(self.path_input)
        
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self.browse_path)
        path_layout.addWidget(self.browse_btn)
        
        layout.addLayout(path_layout)
        
        # 注意
        note_label = QLabel(
            "⚠️ 注意：修改存储路径后，需要手动迁移已有文件到新目录。"
        )
        note_label.setStyleSheet("color: #FF9500;")
        note_label.setWordWrap(True)
        layout.addWidget(note_label)
        
        layout.addStretch()
        
        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def browse_path(self) -> None:
        """浏览选择路径。"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择存储目录",
            str(config.STORAGE_DIR),
            QFileDialog.Option.ShowDirsOnly
        )
        if dir_path:
            self.path_input.setText(dir_path)
    
    def get_path(self) -> str:
        """获取选择的路径。"""
        return self.path_input.text()


class SettingsPage(QWidget):
    """
    设置页面。
    
    信号:
        theme_changed(str): 主题改变
        logout_requested(): 退出登录请求
        storage_path_changed(str): 存储路径改变
    """
    
    theme_changed = Signal(str)
    logout_requested = Signal()
    storage_path_changed = Signal(str)
    tunnel_config_requested = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("SettingsPage")
        self._setup_ui()
        self._load_server_settings_ui()
        self._load_current_status()
    
    def _setup_ui(self) -> None:
        """设置 UI。"""
        scroll = QScrollArea()
        scroll.setObjectName("SettingsPageScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        container = QWidget()
        container.setObjectName("SettingsPageContainer")
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(24)
        
        title_label = QLabel("设置")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        main_layout.addWidget(title_label)
        
        # 外观设置
        appearance_group = self._create_appearance_group()
        main_layout.addWidget(appearance_group)
        
        # 存储设置
        storage_group = self._create_storage_group()
        main_layout.addWidget(storage_group)

        # 本机服务（后端监听 + 局域网 Web）
        local_server_group = self._create_local_server_group()
        main_layout.addWidget(local_server_group)
        
        # 远程访问设置
        tunnel_group = self._create_tunnel_group()
        main_layout.addWidget(tunnel_group)
        
        # 系统服务设置
        service_group = self._create_service_group()
        main_layout.addWidget(service_group)
        
        # 账号设置
        account_group = self._create_account_group()
        main_layout.addWidget(account_group)
        
        # 日志设置
        log_group = self._create_log_group()
        main_layout.addWidget(log_group)
        
        # 关于设置
        about_group = self._create_about_group()
        main_layout.addWidget(about_group)
        
        main_layout.addStretch()
        
        scroll.setWidget(container)
        
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(10, 8, 10, 8)
        page_layout.addWidget(scroll)
    
    def _create_appearance_group(self) -> QGroupBox:
        """创建外观设置组。"""
        group = QGroupBox("外观")
        group_layout = QFormLayout(group)
        group_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        group_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        group_layout.setSpacing(16)
        
        self.theme_combo = QComboBox()
        self.theme_combo.setObjectName("SettingsThemeCombo")
        self.theme_combo.setMaximumWidth(260)
        self.theme_combo.addItems(["浅色模式", "深色模式", "跟随系统"])
        self.theme_combo.setCurrentIndex(0)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        group_layout.addRow("主题:", self.theme_combo)
        
        return group
    
    def _create_storage_group(self) -> QGroupBox:
        """创建存储设置组。"""
        group = QGroupBox("存储")
        group_layout = QFormLayout(group)
        group_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        group_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        group_layout.setSpacing(16)
        
        self.storage_path_label = QLabel()
        self.storage_path_label.setText(str(config.STORAGE_DIR))
        self.storage_path_label.setStyleSheet("font-family: monospace;")
        group_layout.addRow("存储路径:", self.storage_path_label)
        
        self.storage_path_btn = QPushButton("修改存储路径...")
        self.storage_path_btn.setObjectName("QPushButton__secondary")
        self.storage_path_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.storage_path_btn.clicked.connect(self._on_change_storage_path)
        group_layout.addRow("", self.storage_path_btn)
        
        return group

    @staticmethod
    def _guess_lan_ipv4() -> str:
        """推测本机局域网 IPv4，用于展示给其他设备的访问地址。"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.25)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except OSError:
            return "127.0.0.1"

    def _create_local_server_group(self) -> QGroupBox:
        """本机 API / Ollama 监听与局域网 Web 访问说明（写入 server_settings.json，重启生效）。"""
        group = QGroupBox("本机服务与局域网 Web")
        group_layout = QFormLayout(group)
        group_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        group_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        group_layout.setSpacing(16)

        self._srv_host = QLineEdit()
        self._srv_host.setPlaceholderText("0.0.0.0 表示允许局域网内其他设备访问")
        self._srv_host.textChanged.connect(self._update_web_access_hint)
        group_layout.addRow("API 监听地址:", self._srv_host)

        self._srv_port_spin = QSpinBox()
        self._srv_port_spin.setRange(1, 65535)
        self._srv_port_spin.setValue(8000)
        self._srv_port_spin.valueChanged.connect(self._update_web_access_hint)
        group_layout.addRow("API 端口:", self._srv_port_spin)

        self._ollama_port_spin = QSpinBox()
        self._ollama_port_spin.setRange(1, 65535)
        self._ollama_port_spin.setValue(11434)
        group_layout.addRow("Ollama 端口:", self._ollama_port_spin)

        self._web_hint_label = QLabel()
        self._web_hint_label.setWordWrap(True)
        self._web_hint_label.setStyleSheet("color: #86868B; font-size: 12px; font-family: monospace;")
        group_layout.addRow("其他设备 Web 入口:", self._web_hint_label)

        save_srv_btn = QPushButton("保存本机服务设置")
        save_srv_btn.setObjectName("QPushButton__secondary")
        save_srv_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_srv_btn.clicked.connect(self._on_save_server_settings)
        group_layout.addRow("", save_srv_btn)

        tip = QLabel(
            "保存后写入 ~/.allahpan/server_settings.json。请完全退出并重新启动 AllahPan（或 exe）后生效。\n"
            "手机/其他电脑在同一局域网内，用浏览器打开上方地址即可使用网页端；桌面前端仅在本机使用。\n"
            "若无法访问，请检查本机防火墙是否放行对应 TCP 端口。"
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #86868B; font-size: 12px;")
        group_layout.addRow("", tip)

        return group

    def _load_server_settings_ui(self) -> None:
        """从 server_settings.json 或默认值填充本机服务表单。"""
        p = config.SERVER_SETTINGS_PATH
        host = "0.0.0.0"
        api_p = int(os.environ.get("ALLAHPAN_PORT", "8000") or 8000)
        ollama_p = int(os.environ.get("OLLAMA_PORT", "11434") or 11434)
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    if "api_host" in data:
                        host = str(data["api_host"]).strip() or host
                    if "api_port" in data:
                        api_p = int(data["api_port"])
                    if "ollama_port" in data:
                        ollama_p = int(data["ollama_port"])
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                pass
        self._srv_host.setText(host)
        self._srv_port_spin.setValue(api_p)
        self._ollama_port_spin.setValue(ollama_p)
        self._update_web_access_hint()

    def _update_web_access_hint(self) -> None:
        if not hasattr(self, "_web_hint_label"):
            return
        port = self._srv_port_spin.value()
        ip = self._guess_lan_ipv4()
        self._web_hint_label.setText(
            f"http://{ip}:{port}/\n（将 IP 换成本机实际局域网地址即可；API 与网页由同一端口提供）"
        )

    def _on_save_server_settings(self) -> None:
        host = (self._srv_host.text() or "").strip() or "0.0.0.0"
        data = {
            "api_host": host,
            "api_port": int(self._srv_port_spin.value()),
            "ollama_port": int(self._ollama_port_spin.value()),
        }
        try:
            config.SERVER_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            config.SERVER_SETTINGS_PATH.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            QMessageBox.information(
                self,
                "已保存",
                "已写入 ~/.allahpan/server_settings.json。\n请完全退出并重新启动 AllahPan 后生效。",
            )
        except OSError as e:
            QMessageBox.warning(self, "保存失败", str(e))
    
    def _create_tunnel_group(self) -> QGroupBox:
        """创建远程访问设置组。"""
        group = QGroupBox("远程访问")
        group_layout = QFormLayout(group)
        group_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        group_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        group_layout.setSpacing(16)
        
        self.tunnel_status_label = QLabel("未连接")
        self.tunnel_status_label.setStyleSheet("font-weight: bold;")
        group_layout.addRow("状态:", self.tunnel_status_label)
        
        self.tunnel_domain_label = QLabel("-")
        group_layout.addRow("域名:", self.tunnel_domain_label)
        
        self.tunnel_configure_btn = QPushButton("配置远程访问...")
        self.tunnel_configure_btn.setObjectName("QPushButton__secondary")
        self.tunnel_configure_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tunnel_configure_btn.clicked.connect(self._on_configure_tunnel)
        group_layout.addRow("", self.tunnel_configure_btn)
        
        tunnel_tip = QLabel(
            "使用 Cloudflare Tunnel 实现远程访问，\n"
            "需要先在 Cloudflare Zero Trust 配置 Tunnel 并获取 Token。"
        )
        tunnel_tip.setStyleSheet("color: #86868B; font-size: 12px;")
        tunnel_tip.setWordWrap(True)
        group_layout.addRow("", tunnel_tip)
        
        return group
    
    def _create_service_group(self) -> QGroupBox:
        """创建系统服务设置组。"""
        group = QGroupBox("系统服务")
        group_layout = QFormLayout(group)
        group_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        group_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        group_layout.setSpacing(16)
        
        self.auto_start_checkbox = QCheckBox("开机自动启动")
        self.auto_start_checkbox.setChecked(self._check_auto_start())
        self.auto_start_checkbox.stateChanged.connect(self._on_auto_start_changed)
        group_layout.addRow("开机自启:", self.auto_start_checkbox)
        
        ollama_status_layout = QHBoxLayout()
        self.ollama_status_label = QLabel("检查中...")
        self.ollama_status_label.setStyleSheet("font-weight: bold;")
        ollama_status_layout.addWidget(self.ollama_status_label)
        ollama_status_layout.addStretch()
        
        self.ollama_start_btn = QPushButton("启动")
        self.ollama_start_btn.setObjectName("QPushButton__secondary")
        self.ollama_start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ollama_start_btn.clicked.connect(self._on_ollama_start)
        ollama_status_layout.addWidget(self.ollama_start_btn)
        
        self.ollama_stop_btn = QPushButton("停止")
        self.ollama_stop_btn.setObjectName("QPushButton__secondary")
        self.ollama_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ollama_stop_btn.clicked.connect(self._on_ollama_stop)
        ollama_status_layout.addWidget(self.ollama_stop_btn)
        
        group_layout.addRow("Ollama 引擎:", ollama_status_layout)
        
        return group
    
    def _create_account_group(self) -> QGroupBox:
        """创建账号设置组。"""
        group = QGroupBox("账号")
        group_layout = QFormLayout(group)
        group_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        group_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        group_layout.setSpacing(16)
        
        user = config.get_auth_user()
        username = user.get("username", "未知用户") if user else "未登录"
        
        username_label = QLabel(username)
        username_label.setStyleSheet("font-weight: 500;")
        group_layout.addRow("用户名:", username_label)
        
        logout_button = QPushButton("退出登录")
        logout_button.setObjectName("QPushButton__secondary")
        logout_button.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_button.clicked.connect(self._on_logout)
        group_layout.addRow("", logout_button)
        
        return group
    
    def _create_log_group(self) -> QGroupBox:
        """创建日志设置组。"""
        group = QGroupBox("日志")
        group_layout = QFormLayout(group)
        group_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        group_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        group_layout.setSpacing(16)
        
        log_viewer_btn = QPushButton("📋 查看系统日志...")
        log_viewer_btn.setObjectName("QPushButton__secondary")
        log_viewer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        log_viewer_btn.clicked.connect(self._on_view_logs)
        group_layout.addRow("日志查看:", log_viewer_btn)
        
        log_dir_label = QLabel("~/.allahpan/logs/")
        log_dir_label.setStyleSheet("font-family: monospace; color: #86868B;")
        group_layout.addRow("日志目录:", log_dir_label)
        
        return group
    
    def _create_about_group(self) -> QGroupBox:
        """创建关于组。"""
        group = QGroupBox("关于")
        group_layout = QFormLayout(group)
        group_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        group_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        group_layout.setSpacing(16)
        
        version_label = QLabel("v1.0.0")
        group_layout.addRow("版本:", version_label)
        
        desc_label = QLabel(
            "AllahPan 是一款本地部署的家庭私有网盘系统，"
            "集成 AI 语义搜索功能，支持 Cloudflare Tunnel 远程访问。"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #86868B;")
        group_layout.addRow("", desc_label)
        
        return group
    
    def _check_auto_start(self) -> bool:
        """检查是否配置了开机自启。"""
        import platform
        system = platform.system()
        
        if system == "Darwin":  # macOS
            plist_path = Path.home() / "Library" / "LaunchAgents" / "com.allahpan.app.plist"
            return plist_path.exists()
        elif system == "Linux":
            autostart_path = Path.home() / ".config" / "autostart" / "allahpan.desktop"
            return autostart_path.exists()
        elif system == "Windows":
            import winreg
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0,
                    winreg.KEY_READ
                )
                winreg.QueryValueEx(key, "AllahPan")
                winreg.CloseKey(key)
                return True
            except Exception:
                return False
        
        return False
    
    def _on_theme_changed(self, index: int) -> None:
        """处理主题改变。"""
        theme_modes = [
            ThemeMode.LIGHT,
            ThemeMode.DARK,
            ThemeMode.SYSTEM
        ]
        mode = theme_modes[index]
        
        config.set_theme_mode(mode)
        
        self.theme_changed.emit(mode)
    
    def _on_change_storage_path(self) -> None:
        """处理修改存储路径。"""
        dialog = StoragePathDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_path = dialog.get_path()
            if new_path and new_path != str(config.STORAGE_DIR):
                reply = QMessageBox.question(
                    self,
                    "确认修改",
                    f"确定要将存储路径修改为:\n{new_path}\n\n"
                    "修改后需要重启应用生效，且需要手动迁移已有文件。",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.storage_path_label.setText(new_path)
                    self.storage_path_changed.emit(new_path)
                    QMessageBox.information(
                        self,
                        "提示",
                        "存储路径已修改，请在设置中更新配置后重启应用。"
                    )
    
    def _on_configure_tunnel(self) -> None:
        """处理配置远程访问。"""
        self.tunnel_config_requested.emit()
    
    def _on_auto_start_changed(self, state: int) -> None:
        """处理开机自启变更。"""
        enabled = state == Qt.CheckState.Checked.value
        
        import platform
        system = platform.system()
        
        success = False
        
        if system == "Darwin":  # macOS
            success = self._configure_mac_auto_start(enabled)
        elif system == "Linux":
            success = self._configure_linux_auto_start(enabled)
        elif system == "Windows":
            success = self._configure_windows_auto_start(enabled)
        
        if not success:
            self.auto_start_checkbox.setChecked(not enabled)
            QMessageBox.warning(
                self,
                "设置失败",
                "无法配置开机自启功能。"
            )
    
    def _configure_mac_auto_start(self, enable: bool) -> bool:
        """配置 macOS 开机自启。"""
        plist_path = Path.home() / "Library" / "LaunchAgents" / "com.allahpan.app.plist"
        
        if enable:
            app_path = SysPath(sys.argv[0] if sys.argv else __file__).parent.parent
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.allahpan.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>{app_path}/run.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>"""
            try:
                plist_path.parent.mkdir(parents=True, exist_ok=True)
                with open(plist_path, "w") as f:
                    f.write(plist_content)
                return True
            except Exception:
                return False
        else:
            if plist_path.exists():
                try:
                    plist_path.unlink()
                    return True
                except Exception:
                    return False
            return True
    
    def _configure_linux_auto_start(self, enable: bool) -> bool:
        """配置 Linux 开机自启。"""
        autostart_path = Path.home() / ".config" / "autostart" / "allahpan.desktop"
        
        if enable:
            desktop_entry = """[Desktop Entry]
Type=Application
Name=AllahPan
Exec=/usr/bin/python3 /path/to/allahpan/run.py
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
"""
            try:
                autostart_path.parent.mkdir(parents=True, exist_ok=True)
                with open(autostart_path, "w") as f:
                    f.write(desktop_entry)
                return True
            except Exception:
                return False
        else:
            if autostart_path.exists():
                try:
                    autostart_path.unlink()
                    return True
                except Exception:
                    return False
            return True
    
    def _configure_windows_auto_start(self, enable: bool) -> bool:
        """配置 Windows 开机自启。"""
        import winreg
        
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE
            )
            
            if enable:
                app_path = sys.executable
                winreg.SetValueEx(key, "AllahPan", 0, winreg.REG_SZ, f'"{app_path}" run.py')
            else:
                try:
                    winreg.DeleteValue(key, "AllahPan")
                except Exception:
                    pass
            
            winreg.CloseKey(key)
            return True
        except Exception:
            return False
    
    def _on_ollama_start(self) -> None:
        """处理启动 Ollama（后台线程）。"""
        from api.ollama import start_ollama
        w = SettingsWorker(start_ollama, parent=self)
        w.finished.connect(self._on_ollama_start_done, Qt.ConnectionType.QueuedConnection)
        w.failed.connect(lambda e: QMessageBox.critical(self, "错误", f"启动 Ollama 失败:\n{e}"), Qt.ConnectionType.QueuedConnection)
        w.start()

    def _on_ollama_start_done(self, result: dict) -> None:
        if result.get("success"):
            self.ollama_status_label.setText("运行中")
            self.ollama_status_label.setStyleSheet("font-weight: bold; color: #34C759;")
            QMessageBox.information(self, "成功", "Ollama 引擎已启动")
            self._load_current_status()
        else:
            QMessageBox.warning(self, "失败", result.get("message", "启动失败"))

    def _on_ollama_stop(self) -> None:
        """处理停止 Ollama（后台线程）。"""
        from api.ollama import stop_ollama
        w = SettingsWorker(stop_ollama, parent=self)
        w.finished.connect(self._on_ollama_stop_done, Qt.ConnectionType.QueuedConnection)
        w.failed.connect(lambda e: QMessageBox.critical(self, "错误", f"停止 Ollama 失败:\n{e}"), Qt.ConnectionType.QueuedConnection)
        w.start()

    def _on_ollama_stop_done(self, result: dict) -> None:
        if result.get("success"):
            self.ollama_status_label.setText("已停止")
            self.ollama_status_label.setStyleSheet("font-weight: bold; color: #86868B;")
            QMessageBox.information(self, "成功", "Ollama 引擎已停止")
            self._load_current_status()
        else:
            QMessageBox.warning(self, "失败", result.get("message", "停止失败"))
    
    def _on_view_logs(self) -> None:
        """处理查看日志。"""
        dialog = LogViewerDialog(self)
        dialog.exec()
    
    def _on_logout(self) -> None:
        """处理退出登录。"""
        reply = QMessageBox.question(
            self,
            "退出登录",
            "确定要退出登录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.logout_requested.emit()
    
    def _load_current_status(self) -> None:
        """加载当前状态（后台线程）。"""
        def _fetch():
            from api.tunnel import TunnelAPI
            from api.ollama import OllamaAPI
            tunnel_api = TunnelAPI()
            ollama_api = OllamaAPI()
            tunnel_status = tunnel_api.get_status()
            ollama_status = ollama_api.get_status()
            return {"tunnel": tunnel_status, "ollama": ollama_status}

        def _on_ready(data: dict):
            tunnel_status = data.get("tunnel") or {}
            ollama_status = data.get("ollama") or {}
            if tunnel_status.get("is_running"):
                self.tunnel_status_label.setText("已连接")
                self.tunnel_status_label.setStyleSheet("font-weight: bold; color: #34C759;")
            elif tunnel_status.get("token_configured"):
                self.tunnel_status_label.setText("已配置（未启动）")
                self.tunnel_status_label.setStyleSheet("font-weight: bold; color: #FF9500;")
            else:
                self.tunnel_status_label.setText("未配置")
                self.tunnel_status_label.setStyleSheet("font-weight: bold; color: #86868B;")
            self.tunnel_domain_label.setText(tunnel_status.get("domain") or "-")
            if ollama_status.get("service_available"):
                self.ollama_status_label.setText("运行中")
                self.ollama_status_label.setStyleSheet("font-weight: bold; color: #34C759;")
            elif ollama_status.get("is_running"):
                self.ollama_status_label.setText("启动中...")
                self.ollama_status_label.setStyleSheet("font-weight: bold; color: #FF9500;")
            else:
                self.ollama_status_label.setText("已停止")
                self.ollama_status_label.setStyleSheet("font-weight: bold; color: #86868B;")

        w = SettingsWorker(_fetch, parent=self)
        w.finished.connect(_on_ready, Qt.ConnectionType.QueuedConnection)
        w.failed.connect(lambda _: None)
        w.start()
    
    def refresh_status(self) -> None:
        """刷新状态显示。"""
        self._load_current_status()
    
    def show_tunnel_config_dialog(self) -> None:
        """显示 Tunnel 配置对话框。"""
        dialog = TunnelConfigDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_current_status()


class TunnelConfigDialog(QDialog):
    """Tunnel 配置对话框。"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("配置远程访问")
        self.setMinimumSize(500, 300)
        self._setup_ui()
        self._load_current_config()
    
    def _setup_ui(self) -> None:
        """设置 UI。"""
        layout = QVBoxLayout(self)
        
        info_label = QLabel(
            "配置 Cloudflare Tunnel 以实现远程访问功能。\n"
            "请先在 Cloudflare Zero Trust 创建一个 Tunnel 并获取 Token。"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Token 输入
        token_layout = QHBoxLayout()
        token_layout.addWidget(QLabel("Tunnel Token:"))
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("请输入 Cloudflare Tunnel Token")
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        token_layout.addWidget(self.token_input)
        
        show_token_btn = QPushButton("👁")
        show_token_btn.setFixedWidth(40)
        show_token_btn.clicked.connect(lambda: self._toggle_token_visibility())
        token_layout.addWidget(show_token_btn)
        
        layout.addLayout(token_layout)
        
        # 域名输入
        domain_layout = QHBoxLayout()
        domain_layout.addWidget(QLabel("绑定的域名:"))
        self.domain_input = QLineEdit()
        self.domain_input.setPlaceholderText("可选，例如: allahpan.example.com")
        domain_layout.addWidget(self.domain_input)
        layout.addLayout(domain_layout)
        
        # 帮助信息
        help_label = QLabel(
            "\n获取 Token 的步骤:\n"
            "1. 登录 Cloudflare Zero Trust Dashboard\n"
            "2. 进入 Networks > Tunnels\n"
            "3. 创建一个新的 Cloudflare Tunnel\n"
            "4. 复制 Tunnel Token 并粘贴到上方输入框"
        )
        help_label.setStyleSheet("color: #86868B; font-size: 12px; background: #F5F5F7; padding: 10px;")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        
        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Reset
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Reset).setText("清除配置")
        buttons.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(self._on_clear)
        
        layout.addWidget(buttons)
    
    def _toggle_token_visibility(self) -> None:
        """切换 Token 显示/隐藏。"""
        if self.token_input.echoMode() == QLineEdit.EchoMode.Password:
            self.token_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
    
    def _load_current_config(self) -> None:
        """加载当前配置。"""
        try:
            from api.tunnel import get_tunnel_status
            status = get_tunnel_status()
            if status.get("token_configured"):
                self.token_input.setPlaceholderText("已配置（不显示）")
            if status.get("domain"):
                self.domain_input.setText(status.get("domain"))
        except Exception:
            pass
    
    def _on_save(self) -> None:
        """保存配置。"""
        token = self.token_input.text().strip()
        domain = self.domain_input.text().strip()
        
        if not token:
            QMessageBox.warning(self, "提示", "请输入 Tunnel Token")
            return
        
        try:
            from api.tunnel import configure_tunnel
            result = configure_tunnel(token=token, domain=domain if domain else None)
            
            if result.get("success"):
                QMessageBox.information(
                    self, 
                    "成功", 
                    "Tunnel 配置已保存\n\n"
                    "点击「启动」按钮即可开始远程访问。"
                )
                self.accept()
            else:
                QMessageBox.warning(self, "失败", result.get("message", "保存失败"))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置失败:\n{str(e)}")
    
    def _on_clear(self) -> None:
        """清除配置。"""
        reply = QMessageBox.question(
            self,
            "确认清除",
            "确定要清除 Tunnel 配置吗？\n清除后需要重新配置 Token。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from api.tunnel import clear_tunnel_config
                clear_tunnel_config()
                QMessageBox.information(self, "成功", "配置已清除")
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"清除配置失败:\n{str(e)}")
