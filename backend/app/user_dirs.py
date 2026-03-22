"""
解析 AllahPan 用户数据根目录。

数据库、向量库、server_settings、Tunnel 配置等均应位于此目录下，
与 .app / 安装包分离，以便升级或删除应用后数据仍可保留。

可通过环境变量 ALLAHPAN_USER_DATA_ROOT 覆盖。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _legacy_root() -> Path:
    return Path.home() / ".allahpan"


def _legacy_has_content(legacy: Path) -> bool:
    if not legacy.is_dir():
        return False
    try:
        next(legacy.iterdir())
        return True
    except StopIteration:
        return False
    except OSError:
        return False


def _default_platform_root() -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "AllahPan"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "").strip()
        if appdata:
            return Path(appdata) / "AllahPan"
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg:
        return Path(xdg).expanduser().resolve() / "allahpan"
    return home / ".local" / "share" / "allahpan"


def get_allahpan_user_root() -> Path:
    """
    用户可写数据根目录（配置、SQLite、Chroma、日志等）。

    解析顺序：
    1. ALLAHPAN_USER_DATA_ROOT
    2. 若 ~/.allahpan 已存在且非空，继续使用该路径（兼容已有安装）
    3. 否则使用各平台推荐目录（macOS: Application Support，等）
    """
    raw = os.environ.get("ALLAHPAN_USER_DATA_ROOT", "").strip()
    if raw:
        p = Path(raw).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    legacy = _legacy_root()
    if _legacy_has_content(legacy):
        return legacy
    chosen = _default_platform_root()
    chosen.mkdir(parents=True, exist_ok=True)
    return chosen


def running_from_macos_app_bundle() -> bool:
    """当前进程可执行文件是否位于 *.app/Contents/MacOS/ 下。"""
    if sys.platform != "darwin":
        return False
    try:
        exe = Path(sys.executable).resolve()
        parts = exe.parts
        for i, name in enumerate(parts):
            if name.endswith(".app") and i + 3 < len(parts):
                if parts[i + 1] == "Contents" and parts[i + 2] == "MacOS":
                    return True
    except Exception:
        pass
    return False


def should_store_data_outside_bundle() -> bool:
    """是否必须把可写数据放在安装包外（PyInstaller frozen 或 macOS .app 内运行）。"""
    if getattr(sys, "frozen", False):
        return True
    return running_from_macos_app_bundle()
