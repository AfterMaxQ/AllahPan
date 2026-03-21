"""
页面资源初始化模块。

作者: AllahPan团队
"""

from .login_page import LoginPage
from .ops_dashboard_page import OpsDashboardPage
from .settings_page import SettingsPage, TunnelConfigDialog

__all__ = ["LoginPage", "OpsDashboardPage", "SettingsPage", "TunnelConfigDialog"]
