"""
搜索栏组件模块。

提供 macOS 风格的搜索栏，支持文件名/AI搜索模式切换。

作者: AllahPan团队
"""

from typing import Optional, Callable

from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton,
    QLabel
)
from PySide6.QtGui import QIcon


class SearchBar(QWidget):
    """
    搜索栏组件。
    
    信号:
        search_triggered(str, bool): 当搜索触发时发射
            - str: 搜索关键字
            - bool: 是否为 AI 搜索模式
    """
    
    search_triggered = Signal(str, bool)
    
    MODE_FILE = "filename"
    MODE_AI = "ai"
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        debounce_ms: int = 500,
    ):
        super().__init__(parent)
        
        self._mode = self.MODE_FILE
        self._debounce_ms = debounce_ms
        self._debounce_timer: Optional[QTimer] = None
        self._last_text = ""
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """设置 UI。"""
        self.setObjectName("SearchBarWidget")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        self.search_icon_label = QLabel("🔍")
        self.search_icon_label.setFixedWidth(30)
        self.search_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.search_icon_label)
        
        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchLineEdit")
        self.search_input.setPlaceholderText("搜索文件...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self._on_search)
        self.search_input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.search_input, 1)
        
        self.mode_button = QPushButton("文件名")
        self.mode_button.setObjectName("SearchModeButton")
        self.mode_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mode_button.clicked.connect(self._toggle_mode)
        self.mode_button.setFixedWidth(70)
        layout.addWidget(self.mode_button)
    
    def _toggle_mode(self) -> None:
        """切换搜索模式。"""
        if self._mode == self.MODE_FILE:
            self._mode = self.MODE_AI
            self.mode_button.setText("🤖 AI")
            self.search_input.setPlaceholderText("输入自然语言搜索...")
        else:
            self._mode = self.MODE_FILE
            self.mode_button.setText("文件名")
            self.search_input.setPlaceholderText("搜索文件...")
        
        if self.search_input.text():
            self._on_search()
    
    def _on_search(self) -> None:
        """触发搜索。"""
        text = self.search_input.text().strip()
        
        if text == self._last_text:
            return
        
        self._last_text = text
        self.search_triggered.emit(text, self._mode == self.MODE_AI)
    
    def _on_text_changed(self, text: str) -> None:
        """文本改变（带防抖）。"""
        if self._debounce_timer is None:
            self._debounce_timer = QTimer(self)
            self._debounce_timer.setSingleShot(True)
            self._debounce_timer.timeout.connect(self._on_search)
        
        self._debounce_timer.start(self._debounce_ms)
    
    def get_mode(self) -> str:
        """获取当前搜索模式。"""
        return self._mode
    
    def get_mode_display(self) -> str:
        """获取当前搜索模式显示文本。"""
        return "AI 搜索" if self._mode == self.MODE_AI else "文件名搜索"
    
    def get_text(self) -> str:
        """获取搜索文本。"""
        return self.search_input.text().strip()
    
    def set_text(self, text: str) -> None:
        """设置搜索文本。"""
        self.search_input.setText(text)
        self._last_text = text
    
    def clear(self) -> None:
        """清空搜索框。"""
        self.search_input.clear()
        self._last_text = ""
    
    def set_mode(self, mode: str) -> None:
        """
        设置搜索模式。
        
        参数:
            mode: MODE_FILE 或 MODE_AI
        """
        if mode == self._mode:
            return
        
        if mode == self.MODE_AI:
            self._toggle_mode()
    
    def force_search(self) -> None:
        """强制触发搜索（不清空）。"""
        self._on_search()
