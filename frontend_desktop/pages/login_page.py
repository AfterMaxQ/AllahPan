"""
登录/注册页面模块。

提供用户认证界面，支持登录和注册切换。

作者: AllahPan团队
"""

from typing import Optional, Callable

from PySide6.QtCore import Qt, Signal, QEvent, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox, QGraphicsOpacityEffect,
    QMessageBox, QApplication
)
from PySide6.QtGui import QFont, QPalette, QColor

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from api.auth import AuthAPI
from api.client import APIError


class AuthWorker(QThread):
    """后台执行登录/注册，避免阻塞 UI。"""
    success = Signal(dict)
    failed = Signal(str)

    def __init__(self, mode: str, username: str, password: str, email: str = "", parent=None):
        super().__init__(parent)
        self._mode = mode
        self._username = username
        self._password = password
        self._email = email

    def run(self) -> None:
        try:
            api = AuthAPI()
            if self._mode == LoginPage.MODE_REGISTER:
                api.register(self._username, self._password, self._email)
                self.success.emit({"action": "register", "username": self._username})
            else:
                result = api.login(self._username, self._password)
                self.success.emit(result.get("user", {}))
        except Exception as e:
            self.failed.emit(str(e))


class LoginPage(QWidget):
    """
    登录/注册页面。
    
    信号:
        login_success(dict): 登录成功，发射用户信息
    """
    
    login_success_signal = Signal(dict)
    
    MODE_LOGIN = "login"
    MODE_REGISTER = "register"
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._mode = self.MODE_LOGIN
        self._auth_api = AuthAPI()
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """设置 UI。"""
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("LoginPage")
        
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setSpacing(24)
        
        logo_layout = QVBoxLayout()
        logo_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_layout.setSpacing(8)
        
        logo_label = QLabel("📁")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("font-size: 64px;")
        logo_layout.addWidget(logo_label)
        
        self.title_label = QLabel("AllahPan")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(28)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: " + config.ThemeColors.LIGHT["primary"] + ";")
        logo_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("家庭私有网盘")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_font = QFont()
        subtitle_font.setPointSize(14)
        self.subtitle_label.setFont(subtitle_font)
        self.subtitle_label.setStyleSheet("color: #86868B;")
        logo_layout.addWidget(self.subtitle_label)
        
        main_layout.addLayout(logo_layout)
        
        card_container = QWidget()
        card_container.setFixedWidth(360)
        card_layout = QVBoxLayout(card_container)
        card_layout.setSpacing(20)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("用户名")
        self.username_input.setMinimumHeight(44)
        self.username_input.setMaximumHeight(48)
        self.username_input.returnPressed.connect(self._on_submit)
        card_layout.addWidget(self.username_input)
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("邮箱")
        self.email_input.setMinimumHeight(44)
        self.email_input.setMaximumHeight(48)
        self.email_input.setVisible(False)
        self.email_input.returnPressed.connect(self._on_submit)
        card_layout.addWidget(self.email_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("密码")
        self.password_input.setMinimumHeight(44)
        self.password_input.setMaximumHeight(48)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self._on_submit)
        card_layout.addWidget(self.password_input)
        
        self.submit_button = QPushButton("登录")
        self.submit_button.setObjectName("LoginSubmitButton")
        self.submit_button.setMinimumHeight(44)
        self.submit_button.setMaximumHeight(48)
        self.submit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submit_button.clicked.connect(self._on_submit)
        card_layout.addWidget(self.submit_button)
        
        self.switch_button = QPushButton("没有账号？立即注册")
        self.switch_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.switch_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #007AFF;
                border: none;
                font-size: 13px;
            }
            QPushButton:hover {
                text-decoration: underline;
            }
        """)
        self.switch_button.clicked.connect(self._toggle_mode)
        card_layout.addWidget(self.switch_button)
        
        self.error_label = QLabel()
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setStyleSheet("color: #FF3B30; font-size: 13px;")
        self.error_label.setVisible(False)
        card_layout.addWidget(self.error_label)
        
        main_layout.addWidget(card_container)
        
        self.hint_label = QLabel("AllahPan v1.0.0")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet("color: #86868B; font-size: 12px;")
        main_layout.addWidget(self.hint_label, alignment=Qt.AlignmentFlag.AlignBottom)
    
    def _toggle_mode(self) -> None:
        """切换登录/注册模式。"""
        if self._mode == self.MODE_LOGIN:
            self._mode = self.MODE_REGISTER
            self.submit_button.setText("注册")
            self.switch_button.setText("已有账号？立即登录")
            self.email_input.setVisible(True)
            self.email_input.clear()
        else:
            self._mode = self.MODE_LOGIN
            self.submit_button.setText("登录")
            self.switch_button.setText("没有账号？立即注册")
            self.email_input.setVisible(False)
        
        self.error_label.setVisible(False)
    
    def _on_submit(self) -> None:
        """处理提交。"""
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not username:
            self._show_error("请输入用户名")
            return
        
        if not password:
            self._show_error("请输入密码")
            return
        
        if self._mode == self.MODE_REGISTER:
            email = self.email_input.text().strip()
            if not email:
                self._show_error("请输入邮箱")
                return
            self._do_register(username, password, email)
        else:
            self._do_login(username, password)
    
    def _do_login(self, username: str, password: str) -> None:
        """执行登录（后台线程）。"""
        self.submit_button.setEnabled(False)
        self.submit_button.setText("登录中...")
        self.error_label.setVisible(False)
        w = AuthWorker(self.MODE_LOGIN, username, password, "", parent=self)
        w.success.connect(self._on_auth_success_login, Qt.ConnectionType.QueuedConnection)
        w.failed.connect(self._on_auth_failed_login, Qt.ConnectionType.QueuedConnection)
        w.start()

    def _on_auth_success_login(self, user: dict) -> None:
        self.submit_button.setEnabled(True)
        self.submit_button.setText("登录")
        self.login_success_signal.emit(user)

    def _on_auth_failed_login(self, error: str) -> None:
        self._show_error(error)
        self.submit_button.setEnabled(True)
        self.submit_button.setText("登录")

    def _do_register(self, username: str, password: str, email: str) -> None:
        """执行注册（后台线程）。"""
        self.submit_button.setEnabled(False)
        self.submit_button.setText("注册中...")
        self.error_label.setVisible(False)
        w = AuthWorker(self.MODE_REGISTER, username, password, email, parent=self)
        w.success.connect(self._on_auth_success_register, Qt.ConnectionType.QueuedConnection)
        w.failed.connect(self._on_auth_failed_register, Qt.ConnectionType.QueuedConnection)
        w.start()

    def _on_auth_success_register(self, data: dict) -> None:
        QMessageBox.information(
            self, "注册成功", "账号注册成功！请使用注册的账号登录。"
        )
        self._mode = self.MODE_LOGIN
        self.submit_button.setText("登录")
        self.submit_button.setEnabled(True)
        self.switch_button.setText("没有账号？立即注册")
        self.email_input.setVisible(False)
        self.username_input.setText(data.get("username", ""))
        self.password_input.clear()
        self.password_input.setFocus()

    def _on_auth_failed_register(self, error: str) -> None:
        self._show_error(error)
        self.submit_button.setEnabled(True)
        self.submit_button.setText("注册")
    
    def _show_error(self, message: str) -> None:
        """显示错误信息。"""
        self.error_label.setText(message)
        self.error_label.setVisible(True)
    
    def reset(self) -> None:
        """重置表单。"""
        self.username_input.clear()
        self.password_input.clear()
        self.email_input.clear()
        self.error_label.setVisible(False)
        self.submit_button.setEnabled(True)
        self.submit_button.setText("登录" if self._mode == self.MODE_LOGIN else "注册")

    def changeEvent(self, event) -> None:
        """响应全局主题/调色板变化。"""
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            self.update_theme_colors()

    def update_theme_colors(self) -> None:
        """根据当前主题更新颜色。"""
        mode = config._current_theme_mode
        if mode == config.ThemeMode.SYSTEM:
            palette = QApplication.palette()
            is_dark = palette.color(palette.ColorRole.Window).lightness() < 128
            colors = config.ThemeColors.DARK if is_dark else config.ThemeColors.LIGHT
        elif mode == config.ThemeMode.DARK:
            colors = config.ThemeColors.DARK
        else:
            colors = config.ThemeColors.LIGHT

        primary = colors["primary"]
        secondary = colors["text_secondary"]
        self.title_label.setStyleSheet(f"color: {primary};")
        self.subtitle_label.setStyleSheet(f"color: {secondary};")
        self.hint_label.setStyleSheet(f"color: {secondary}; font-size: 12px;")
