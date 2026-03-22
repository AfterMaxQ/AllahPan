# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for AllahPan Windows Distribution.

This file replaces windows.yml (which was YAML-formatted and never used).
PyInstaller reads .spec files directly (they are Python scripts).

Build command:
    pyinstaller AllahPan.spec

The built .exe and all dependencies will be in dist/AllahPan/
"""

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_all
import PyInstaller

block_cipher = None

_jose_datas, _jose_binaries, _jose_collect_hidden = collect_all("jose")


# ==================== Configuration ====================

APP_NAME = "AllahPan"
VERSION = "1.0.0"
BUILD = "1"
AUTHOR = "AllahPan Team"

# PyInstaller 执行 spec 时不提供 __file__，用 SPECPATH（spec 所在目录 = 仓库根）
PROJECT_ROOT = Path(SPECPATH)

# Data dirs
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend_desktop"
FRONTEND_WEB_DIR = PROJECT_ROOT / "frontend_web"
BUILD_DIR = PROJECT_ROOT / "build"

# 确保 Qt/PySide6 相关 hook 在导入 Qt 前执行（必须放在 BUILD_DIR 定义之后）
_pyi_rthooks_dir = os.path.join(os.path.dirname(PyInstaller.__file__), "hooks", "rthooks")
_runtime_hooks = [
    str(PROJECT_ROOT / "packaging" / "pyi_rth_qt_dll.py"),
    os.path.join(_pyi_rthooks_dir, "pyi_rth_pyside6.py"),
]

# 显式收集 PySide6/Qt6 的 binaries 与 datas（DLL、平台插件等），避免因入口仅动态导入 frontend 导致 hook 未收集
_pyside6_binaries = []
_pyside6_datas = []
try:
    from PyInstaller.utils.hooks.qt import pyside6_library_info, add_qt6_dependencies
    _hook_dir = os.path.join(os.path.dirname(PyInstaller.__file__), "hooks")
    if pyside6_library_info.version is not None:
        _pyside6_binaries = list(pyside6_library_info.collect_extra_binaries())
        for _hook_name in ["hook-PySide6.QtCore.py", "hook-PySide6.QtWidgets.py", "hook-PySide6.QtGui.py"]:
            _h = os.path.join(_hook_dir, _hook_name)
            if os.path.isfile(_h):
                _hi, _bi, _da = add_qt6_dependencies(_h)
                _pyside6_binaries += _bi
                _pyside6_datas += _da
    # PyInstaller 的 format_binaries_and_datas 接受 hook 风格 (src, dest)，与 Qt hook 返回格式一致，无需互换
except Exception as _e:
    import warnings
    warnings.warn("PySide6 显式收集失败，GUI 可能缺 DLL: %s" % _e)

# Qt6Core 需要与 Qt 构建匹配的 ICU。不要将 System32 里的 icu*.dll 存根复制进 PySide6（Win10/11 上多为几 KB 转发器），
# 否则会先于系统 WinSxS 中的完整 ICU 被加载，触发 WinError 127（界面无控制台时表现为双击无反应）。
# 同时 chromadb/duckdb 等会把另一套 icuuc/icudt 打到 _internal 根目录，与 Qt 冲突；见 Analysis 后的 TOC 剔除。


# ==================== Hidden Imports (collect automatically where possible) ====================

# ChromaDB submodules (often missed by PyInstaller)
chromadb_hidden = collect_submodules("chromadb")
# Pydantic v1 compatibility layer
pydantic_hidden = [
    "pydantic.v1",
    "pydantic.fields",
    "pydantic.errors",
    "pydantic.validators",
    "pydantic.main",
    "pydantic.schema",
    "pydantic.generics",
]
# jose (JWT library)
jose_hidden = [
    "jose",
    "jose.exceptions",
    "jose.backends",
    "jose.backends.cryptography_backend",
    "jose.backends.rsa_backend",
    "jose.backends.ecdsa_backend",
    "jose.jwt",
    "jose.jwe",
    "jose.jwk",
    "jose.jws",
    "jose.utils",
    "cryptography.x509",
    "cryptography.hazmat.primitives",
    "cryptography.hazmat.backends",
]
# httpx (HTTP client)
httpx_hidden = [
    "httpx",
    "httpx._client",
    "httpx._models",
    "httpx._config",
    "httpx._content",
    "httpx._transports",
    "httpx._exceptions",
]
# uvicorn (ASGI server) - 与 uvicorn 0.42 实际结构一致，已移除不存在的 strip_path
uvicorn_hidden = [
    "uvicorn",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.logging",
    "uvicorn.middleware",
    "uvicorn.middleware.proxy_headers",
]
# starlette
starlette_hidden = [
    "starlette",
    "starlette.middleware",
    "starlette.middleware.cors",
    "starlette.middleware.base",
    "starlette.routing",
    "starlette.responses",
    "starlette.background",
    "starlette.requests",
    "starlette.types",
]
# watchdog
watchdog_hidden = [
    "watchdog",
    "watchdog.watchmedo",
]
# PySide6 (all submodules)
pyside6_hidden = collect_submodules("PySide6")
# python-multipart
multipart_hidden = ["multipart"]


# ==================== All Hidden Imports ====================

all_hidden_imports = (
    [
        # Core web framework
        "fastapi",
        "uvicorn",
        "starlette",
        "wsproto",
        "h11",
        "h2",
        "anyio",
        # Pydantic
        "pydantic",
        "pydantic.main",
        "pydantic.fields",
        "pydantic.errors",
        "pydantic.schema",
        "email_validator",
        # Database
        "chromadb",
        "chromadb.api",
        "chromadb.api.types",
        "chromadb.config",
        "chromadb.utils",
        "chromadb.embedding",
        "chromadb.embedding._default",
        "chromadb.utils.message_queue",
        "duckdb",
        "pypika",
        "numpy",
        # HTTP client
        "httpx",
        "httpx._client",
        "httpx._models",
        "httpcore",
        "httpcore._sync",
        # JWT / Security
        "jose",
        "jose.exceptions",
        "jose.backends",
        "bcrypt",
        "cryptography",
        "cryptography.x509",
        "cryptography.hazmat.primitives",
        # AI
        "ollama",
        "filelock",
        # File operations
        "python_multipart",
        "watchdog",
        "watchdog.watchmedo",
        # Frontend
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtXml",
        # Standard library modules (sometimes missed)
        "sqlite3",
        "asyncio",
        "concurrent.futures",
        "logging",
        "pathlib",
        "ctypes",
        "subprocess",
        "json",
        "uuid",
        "datetime",
        "tempfile",
        "mimetypes",
        "webbrowser",
        "platform",
        "shutil",
        "stat",
        "struct",
        "socket",
        "threading",
        "queue",
        "pickle",
        "hashlib",
        "base64",
        "binascii",
        "html",
        "urllib",
        "urllib.parse",
        "xml.etree",
        "xml.etree.ElementTree",
    ]
    + chromadb_hidden
    + pydantic_hidden
    + jose_hidden
    + httpx_hidden
    + uvicorn_hidden
    + starlette_hidden
    + watchdog_hidden
    + pyside6_hidden
    + multipart_hidden
)


# ==================== Analysis ====================

a = Analysis(
    [str(PROJECT_ROOT / "launcher.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=_pyside6_binaries + list(_jose_binaries),
    datas=[
        # Backend application code
        (str(BACKEND_DIR / "app"), "backend/app"),
        (str(BACKEND_DIR / "ollama"), "backend/ollama"),
        # Frontend code
        (str(FRONTEND_DIR), "frontend_desktop"),
        # Theme files
        (str(FRONTEND_DIR / "theme"), "frontend_desktop/theme"),
        # Web SPA：由 FastAPI 同端口托管，供局域网/远程浏览器访问
        (str(FRONTEND_WEB_DIR), "frontend_web"),
    ]
    + _pyside6_datas
    + list(_jose_datas),
    hiddenimports=all_hidden_imports + ["shiboken6"] + list(_jose_collect_hidden),
    hookspath=[os.path.join(os.path.dirname(PyInstaller.__file__), "hooks")],
    hooksconfig={},
    runtime_hooks=_runtime_hooks,
    excludes=[
        # Exclude unused heavy packages
        "tkinter",
        "matplotlib",
        "scipy",
        "PIL",          # Pillow removed from deps
        "requests",     # Removed from deps
        "psutil",       # Removed from deps
        "passlib",      # Removed from deps
        "PyQt5",        # Only PySide6 is used; PyInstaller rejects multiple Qt bindings
        "PyQt6",        # Only PySide6 is used; PyInstaller rejects multiple Qt bindings
        "torch",        # AllahPan does not use torch; hook fails in isolated subprocess
        "torchvision",
        "torchaudio",
        "test",
        "tests",
        "pytest",
        "unittest",
        "turtledemo",
        "pdb",
        "cProfile",
        "venv",
        "ensurepip",
        "idle",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Windows：从二进制列表中移除「仅位于 bundle 根（非子目录）」的 ICU DLL，避免 Qt6Core 误加载与 Qt 不兼容的版本。
if sys.platform == "win32":
    _icu_root_basenames = frozenset(
        n.lower()
        for n in (
            "icu.dll",
            "icuin.dll",
            "icuuc.dll",
            "icudt73.dll",
            "icudt74.dll",
            "icudt75.dll",
            "icudt76.dll",
        )
    )

    def _keep_win_binary(bin_entry):
        dest = bin_entry[0].replace("\\", "/")
        base = os.path.basename(dest).lower()
        if base not in _icu_root_basenames:
            return True
        return "/" in dest

    a.binaries = [b for b in a.binaries if _keep_win_binary(b)]


# ==================== PYZ ====================

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


# ==================== EXE ====================

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # No console window for desktop app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Windows-specific
    icon=str(BUILD_DIR / "AllahPan.ico") if (BUILD_DIR / "AllahPan.ico").exists() else None,
    # Version info (Windows executable properties)
    version=str(BUILD_DIR / "AllahPanVersion.txt") if (BUILD_DIR / "AllahPanVersion.txt").exists() else None,
)


# ==================== COLLECT ====================

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
