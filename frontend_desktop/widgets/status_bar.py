"""
状态栏组件模块。

显示存储空间、Ollama连接状态、同步状态、远程访问状态等信息。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-20
"""

from typing import Optional, Dict, Any

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QProgressBar, QPushButton
)
from PySide6.QtCore import Qt

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


class StatusIndicator(QWidget):
    """
    状态指示灯组件。
    
    显示不同颜色的圆点表示状态。
    """
    
    STATUS_NORMAL = "normal"
    STATUS_WARNING = "warning"
    STATUS_DANGER = "danger"
    STATUS_OFFLINE = "offline"
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        status: str = STATUS_NORMAL,
    ):
        super().__init__(parent)
        self._status = status
        self._setup_ui()
        self._update_style()
    
    def _setup_ui(self) -> None:
        """设置 UI。"""
        self.setFixedSize(8, 8)
        self.setObjectName("StatusIndicator")
    
    def _update_style(self) -> None:
        """更新样式。"""
        colors = {
            self.STATUS_NORMAL: "#34C759",
            self.STATUS_WARNING: "#FF9500",
            self.STATUS_DANGER: "#FF3B30",
            self.STATUS_OFFLINE: "#86868B",
        }
        color = colors.get(self._status, colors[self.STATUS_NORMAL])
        self.setStyleSheet(f"""
            QWidget#StatusIndicator {{
                background-color: {color};
                border-radius: 4px;
            }}
        """)
    
    def set_status(self, status: str) -> None:
        """
        设置状态。
        
        参数:
            status: STATUS_NORMAL, STATUS_WARNING, STATUS_DANGER, STATUS_OFFLINE
        """
        if self._status != status:
            self._status = status
            self._update_style()


class StatusBar(QWidget):
    """
    状态栏组件。
    
    显示：
    - 存储空间使用情况
    - Ollama 连接状态
    - 同步状态
    - 远程访问状态（Cloudflare Tunnel）
    """
    
    storage_clicked = Signal()
    ollama_clicked = Signal()
    tunnel_clicked = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()
        self._refresh_timer: Optional[QTimer] = None
    
    def _setup_ui(self) -> None:
        """设置 UI。"""
        self.setObjectName("StatusBarWidget")
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 8, 16, 8)
        main_layout.setSpacing(24)
        
        storage_layout = QHBoxLayout()
        storage_layout.setSpacing(8)
        storage_layout.addWidget(QLabel("💾"))
        
        self.storage_label = QLabel("存储空间")
        self.storage_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.storage_label.mousePressEvent = lambda e: self.storage_clicked.emit()
        storage_layout.addWidget(self.storage_label)
        
        self.storage_progress = QProgressBar()
        self.storage_progress.setObjectName("StorageProgressBar")
        self.storage_progress.setFixedSize(100, 6)
        self.storage_progress.setTextVisible(False)
        self.storage_progress.setMinimum(0)
        self.storage_progress.setMaximum(100)
        storage_layout.addWidget(self.storage_progress)
        
        self.storage_percent_label = QLabel("0%")
        self.storage_percent_label.setFixedWidth(35)
        storage_layout.addWidget(self.storage_percent_label)
        
        main_layout.addLayout(storage_layout)
        
        main_layout.addStretch()
        
        ollama_layout = QHBoxLayout()
        ollama_layout.setSpacing(6)
        
        self.ollama_indicator = StatusIndicator(status=StatusIndicator.STATUS_OFFLINE)
        ollama_layout.addWidget(self.ollama_indicator)
        
        self.ollama_label = QLabel("Ollama 未连接")
        self.ollama_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ollama_label.mousePressEvent = lambda e: self.ollama_clicked.emit()
        ollama_layout.addWidget(self.ollama_label)
        
        main_layout.addLayout(ollama_layout)
        
        main_layout.addSpacing(16)
        
        sync_layout = QHBoxLayout()
        sync_layout.setSpacing(6)
        
        self.sync_indicator = StatusIndicator(status=StatusIndicator.STATUS_NORMAL)
        sync_layout.addWidget(self.sync_indicator)
        
        self.sync_label = QLabel("已同步")
        sync_layout.addWidget(self.sync_label)
        
        main_layout.addLayout(sync_layout)
        
        main_layout.addSpacing(16)
        
        tunnel_layout = QHBoxLayout()
        tunnel_layout.setSpacing(6)
        
        self.tunnel_indicator = StatusIndicator(status=StatusIndicator.STATUS_OFFLINE)
        tunnel_layout.addWidget(self.tunnel_indicator)
        
        self.tunnel_label = QLabel("远程访问 未连接")
        self.tunnel_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tunnel_label.mousePressEvent = lambda e: self.tunnel_clicked.emit()
        tunnel_layout.addWidget(self.tunnel_label)
        
        self.tunnel_domain_label = QLabel("")
        self.tunnel_domain_label.setStyleSheet("color: #86868B; font-size: 11px;")
        tunnel_layout.addWidget(self.tunnel_domain_label)
        
        main_layout.addLayout(tunnel_layout)
    
    def set_storage_info(
        self,
        used_space: int,
        total_space: int,
    ) -> None:
        """
        设置存储信息。
        
        参数:
            used_space: 已使用空间（字节）
            total_space: 总空间（字节）
        """
        used_str = config.format_file_size(used_space)
        total_str = config.format_file_size(total_space)
        
        self.storage_label.setText(f"存储: {used_str} / {total_str}")
        
        if total_space > 0:
            percent = int((used_space / total_space) * 100)
            self.storage_progress.setValue(percent)
            self.storage_percent_label.setText(f"{percent}%")
            if percent >= 90:
                self.storage_label.setStyleSheet("color: #FF3B30; font-weight: 500;")
                self.storage_progress.setStyleSheet("QProgressBar::chunk { background-color: #FF3B30; }")
            else:
                self.storage_label.setStyleSheet("")
                self.storage_progress.setStyleSheet("")
        else:
            self.storage_progress.setValue(0)
            self.storage_percent_label.setText("0%")
    
    def set_ollama_status(self, available: bool, error: Optional[str] = None, models: list = None) -> None:
        """
        设置 Ollama 状态。
        
        参数:
            available: Ollama 是否可用
            error: 错误信息（如果有）
            models: 已加载的模型列表
        """
        if available:
            self.ollama_indicator.set_status(StatusIndicator.STATUS_NORMAL)
            if models:
                model_count = len(models) if isinstance(models, list) else 0
                self.ollama_label.setText(f"Ollama 已连接 ({model_count} 模型)")
            else:
                self.ollama_label.setText("Ollama 已连接")
            self.ollama_label.setToolTip("")
        else:
            self.ollama_indicator.set_status(StatusIndicator.STATUS_DANGER)
            if error:
                self.ollama_label.setText("Ollama 错误")
                self.ollama_label.setToolTip(error)
            else:
                self.ollama_label.setText("Ollama 未连接")
    
    def set_sync_status(self, synced: bool, message: str = "已同步") -> None:
        """
        设置同步状态。
        
        参数:
            synced: 是否已同步
            message: 状态消息
        """
        if synced:
            self.sync_indicator.set_status(StatusIndicator.STATUS_NORMAL)
        else:
            self.sync_indicator.set_status(StatusIndicator.STATUS_WARNING)
        
        self.sync_label.setText(message)
    
    def set_tunnel_status(
        self,
        running: bool,
        domain: Optional[str] = None,
        error: Optional[str] = None,
        configured: bool = False,
    ) -> None:
        """
        设置远程访问（Tunnel）状态。
        
        参数:
            running: Tunnel 是否正在运行
            domain: 绑定的域名
            error: 错误信息（如果有）
            configured: Token 是否已配置
        """
        if running:
            self.tunnel_indicator.set_status(StatusIndicator.STATUS_NORMAL)
            self.tunnel_label.setText("远程访问 已连接")
            if domain:
                self.tunnel_domain_label.setText(f"({domain})")
                self.tunnel_label.setToolTip(f"访问地址: https://{domain}")
            else:
                self.tunnel_domain_label.setText("")
        elif configured:
            self.tunnel_indicator.set_status(StatusIndicator.STATUS_WARNING)
            self.tunnel_label.setText("远程访问 已配置")
            self.tunnel_domain_label.setText("")
            if error:
                self.tunnel_label.setToolTip(f"错误: {error}")
            else:
                self.tunnel_label.setToolTip("点击启动远程访问")
        else:
            self.tunnel_indicator.set_status(StatusIndicator.STATUS_OFFLINE)
            self.tunnel_label.setText("远程访问 未配置")
            self.tunnel_domain_label.setText("")
            self.tunnel_label.setToolTip("点击前往设置配置远程访问")
    
    def set_from_summary(self, summary: Dict[str, Any]) -> None:
        """
        从系统状态摘要设置所有状态。
        
        参数:
            summary: 系统状态摘要字典
        """
        # 存储信息
        storage = summary.get("storage", {})
        self.set_storage_info(
            used_space=storage.get("used_space", 0),
            total_space=storage.get("total_space", 0),
        )
        
        # Ollama 状态：以 service_available 为准；若后端未设但返回了已加载模型，也视为已连接
        ollama = summary.get("ollama", {})
        models = ollama.get("loaded_models", []) or []
        available = ollama.get("service_available", False) or (
            len(models) > 0 if isinstance(models, list) else False
        )
        self.set_ollama_status(
            available=available,
            error=ollama.get("error"),
            models=models,
        )
        
        # Tunnel 状态
        tunnel = summary.get("tunnel", {})
        self.set_tunnel_status(
            running=tunnel.get("is_running", False),
            domain=tunnel.get("domain"),
            error=tunnel.get("error"),
            configured=tunnel.get("token_configured", False),
        )
        
        # 同步状态
        watcher = summary.get("watcher", {})
        self.set_sync_status(
            synced=watcher.get("running", False),
            message="已同步" if watcher.get("running", False) else "未同步",
        )
    
    def start_auto_refresh(self, interval_ms: int = 30000) -> None:
        """
        启动自动刷新。
        
        参数:
            interval_ms: 刷新间隔（毫秒）
        """
        if self._refresh_timer is None:
            self._refresh_timer = QTimer(self)
            self._refresh_timer.timeout.connect(self._on_refresh_timeout)
        
        self._refresh_timer.start(interval_ms)
    
    def stop_auto_refresh(self) -> None:
        """停止自动刷新。"""
        if self._refresh_timer:
            self._refresh_timer.stop()
    
    def _on_refresh_timeout(self) -> None:
        """刷新超时处理（子类可重写）。"""
        pass
