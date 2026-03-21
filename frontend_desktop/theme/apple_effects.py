"""
Apple 风格辅助：柔和阴影与页面淡入动画（Qt 无原生毛玻璃模糊，阴影与半透明由 QSS + 本模块配合）。
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QObject
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QWidget
from shiboken6 import isValid


def apply_acrylic_shadow(
    widget: QWidget,
    blur: float = 28.0,
    offset_y: int = 8,
    offset_x: int = 0,
    alpha: int = 42,
) -> QGraphicsDropShadowEffect:
    """为控件添加柔和投影（类似卡片浮起）。"""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(offset_x, offset_y)
    shadow.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(shadow)
    return shadow


def fade_in_widget(
    widget: QWidget,
    owner: QObject,
    duration_ms: int = 260,
    on_finished: Optional[Callable[[], None]] = None,
) -> None:
    """
    将 widget 从透明淡入到不透明；结束后移除 GraphicsEffect，便于与阴影等效果并存。
    owner 用于挂接动画，避免被 GC。
    """
    prev = widget.graphicsEffect()
    if prev is not None:
        widget.setGraphicsEffect(None)
        prev.deleteLater()

    eff = QGraphicsOpacityEffect(widget)
    eff.setOpacity(0.0)
    widget.setGraphicsEffect(eff)

    anim = QPropertyAnimation(eff, b"opacity", owner)
    anim.setDuration(duration_ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _cleanup() -> None:
        # setGraphicsEffect(None) 会销毁当前 QGraphicsOpacityEffect，再 deleteLater 会触发
        # “Internal C++ object already deleted”。
        widget.setGraphicsEffect(None)
        if isValid(eff):
            eff.deleteLater()
        if on_finished:
            on_finished()

    anim.finished.connect(_cleanup)
    setattr(owner, "_stack_page_fade_anim", anim)
    anim.start()
