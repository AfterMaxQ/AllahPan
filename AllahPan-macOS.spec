# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for AllahPan macOS Distribution (.app bundle).

PyInstaller reads .spec files directly (they are Python scripts).

Build command:
    pyinstaller AllahPan-macOS.spec

The built .app bundle will be in dist/AllahPan.app/
"""

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_all
import PyInstaller

# PyInstaller 常把 jose 拆到 Frameworks 仅余 __init__.py，导致 jose.jwt 丢失而闪退；整包收集可避免
_jose_datas, _jose_binaries, _jose_collect_hidden = collect_all("jose")

block_cipher = None

# 在导入 PySide6 之前设置 Qt 插件路径（与 Windows 版 AllahPan.spec 一致，避免 macOS 上平台插件未找到）
_pyi_rthooks_dir = os.path.join(os.path.dirname(PyInstaller.__file__), "hooks", "rthooks")
_runtime_hooks = [
    os.path.join(_pyi_rthooks_dir, "pyi_rth_pyside6.py"),
]


# ==================== Configuration ====================

APP_NAME = "AllahPan"
VERSION = "1.0.0"
BUILD = "1"
AUTHOR = "AllahPan Team"

PROJECT_ROOT = Path(SPECPATH)
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend_desktop"
FRONTEND_WEB_DIR = PROJECT_ROOT / "frontend_web"
BUILD_DIR = PROJECT_ROOT / "build"


# ==================== Hidden Imports ====================

chromadb_hidden = collect_submodules("chromadb")
pydantic_hidden = [
    "pydantic.v1",
    "pydantic.fields",
    "pydantic.errors",
    "pydantic.validators",
    "pydantic.main",
    "pydantic.schema",
    "pydantic.generics",
]
jose_hidden = [
    "jose",
    "jose.jwt",
    "jose.jws",
    "jose.jwk",
    "jose.exceptions",
    "jose.backends",
    "jose.backends.cryptography_backend",
    "cryptography.x509",
    "cryptography.hazmat.primitives",
    "cryptography.hazmat.backends",
]
httpx_hidden = [
    "httpx",
    "httpx._client",
    "httpx._models",
    "httpx._config",
    "httpx._content",
    "httpx._transports",
    "httpx._exceptions",
]
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
watchdog_hidden = [
    "watchdog",
    "watchdog.watchmedo",
]
pyside6_hidden = collect_submodules("PySide6")
multipart_hidden = ["multipart"]


# ==================== All Hidden Imports ====================

all_hidden_imports = (
    [
        "fastapi",
        "uvicorn",
        "starlette",
        "wsproto",
        "h11",
        "h2",
        "anyio",
        "pydantic",
        "pydantic.main",
        "pydantic.fields",
        "pydantic.errors",
        "pydantic.schema",
        "email_validator",
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
        "httpx",
        "httpx._client",
        "httpx._models",
        "httpcore",
        "httpcore._sync",
        "jose",
        "jose.exceptions",
        "jose.backends",
        "bcrypt",
        "cryptography",
        "cryptography.x509",
        "cryptography.hazmat.primitives",
        "ollama",
        "filelock",
        "python_multipart",
        "watchdog",
        "watchdog.watchmedo",
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtXml",
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
        "socket",
        "threading",
        "queue",
        "pickle",
        "hashlib",
        "base64",
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
    binaries=list(_jose_binaries),
    datas=[
        (str(BACKEND_DIR / "app"), "backend/app"),
        (str(BACKEND_DIR / "ollama"), "backend/ollama"),
        (str(FRONTEND_DIR), "frontend_desktop"),
        (str(FRONTEND_DIR / "theme"), "frontend_desktop/theme"),
        (str(FRONTEND_WEB_DIR), "frontend_web"),
    ]
    + list(_jose_datas),
    hiddenimports=all_hidden_imports + ["shiboken6"] + list(_jose_collect_hidden),
    hookspath=[os.path.join(os.path.dirname(PyInstaller.__file__), "hooks")],
    runtime_hooks=_runtime_hooks,
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy",
        "PIL",
        "requests",
        "psutil",
        "passlib",
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
    cipher=block_cipher,
    noarchive=False,
)


# ==================== PYZ ====================

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


# ==================== BUNDLE (macOS .app) ====================

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    disable_windowed_traceback=False,
    icon=str(BUILD_DIR / "AllahPan.icns") if (BUILD_DIR / "AllahPan.icns").exists() else None,
)

# BUNDLE 的 name 必须包含「.app」后缀。若只写 "AllahPan"，PyInstaller 会生成 dist/AllahPan/
#（无 .app），macOS 不会把它当作应用程序：Finder 显示空白/通用图标，双击无反应。
app = BUNDLE(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name=f"{APP_NAME}.app",
    icon=str(BUILD_DIR / "AllahPan.icns") if (BUILD_DIR / "AllahPan.icns").exists() else None,
    version=VERSION,
    # PyInstaller 仅合并 dict；传 plist 路径无效。需要自定义键时用 dict。
    info_plist={},
    bundle_identifier="com.allahpan.app",
)
