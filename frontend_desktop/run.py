"""
AllahPan PySide6 桌面端入口脚本。

作者: AllahPan团队
创建日期: 2026-03-19
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPalette, QColor, QFont, QIcon

import config
from theme import LIGHT_QSS, DARK_QSS
from main_window import MainWindow


def setup_application(app: QApplication) -> None:
    """
    配置应用程序全局属性。
    
    参数:
        app: QApplication 实例
    """
    app.setApplicationName(config.APP_NAME)
    app.setApplicationVersion(config.APP_VERSION)
    app.setOrganizationName("AllahPan Team")

    icon_path = config.resolve_app_icon_path()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))

    app.setStyle("Fusion")
    
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#1D1D1F"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#F5F5F7"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#1D1D1F"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#1D1D1F"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#F5F5F7"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1D1D1F"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#007AFF"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#86868B"))
    
    palette.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.WindowText, QColor("#86868B"))
    palette.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Highlight, QColor("#D2D2D7"))
    
    app.setPalette(palette)
    
    font = QFont()
    font.setFamily("Segoe UI, Microsoft YaHei, -apple-system, BlinkMacSystemFont, sans-serif")
    font.setPointSize(13)
    app.setFont(font)


def apply_theme(app: QApplication, theme: str = "light") -> None:
    """
    应用主题样式。
    
    参数:
        app: QApplication 实例
        theme: 主题名称 "light" 或 "dark"
    """
    if theme == "dark":
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor("#1C1C1E"))
        dark_palette.setColor(QPalette.ColorRole.WindowText, QColor("#FFFFFF"))
        dark_palette.setColor(QPalette.ColorRole.Base, QColor("#2C2C2E"))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#3A3A3C"))
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#3A3A3C"))
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#FFFFFF"))
        dark_palette.setColor(QPalette.ColorRole.Text, QColor("#FFFFFF"))
        dark_palette.setColor(QPalette.ColorRole.Button, QColor("#2C2C2E"))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor("#FFFFFF"))
        dark_palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor("#0A84FF"))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        dark_palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#636366"))
        
        app.setPalette(dark_palette)
        app.setStyleSheet(DARK_QSS)
    else:
        light_palette = QPalette()
        light_palette.setColor(QPalette.ColorRole.Window, QColor("#FFFFFF"))
        light_palette.setColor(QPalette.ColorRole.WindowText, QColor("#1D1D1F"))
        light_palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
        light_palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#F5F5F7"))
        light_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#1D1D1F"))
        light_palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#FFFFFF"))
        light_palette.setColor(QPalette.ColorRole.Text, QColor("#1D1D1F"))
        light_palette.setColor(QPalette.ColorRole.Button, QColor("#F5F5F7"))
        light_palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1D1D1F"))
        light_palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
        light_palette.setColor(QPalette.ColorRole.Highlight, QColor("#007AFF"))
        light_palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        light_palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#86868B"))

        app.setPalette(light_palette)
        app.setStyleSheet(LIGHT_QSS)


def main() -> int:
    """
    应用程序入口函数。
    
    返回:
        int: 应用程序退出码
    """
    app = QApplication(sys.argv)
    
    setup_application(app)
    
    apply_theme(app, "light")
    
    window = MainWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
