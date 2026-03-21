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
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None


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
    binaries=[],
    datas=[
        (str(BACKEND_DIR / "app"), "backend/app"),
        (str(BACKEND_DIR / "ollama"), "backend/ollama"),
        (str(FRONTEND_DIR), "frontend_desktop"),
        (str(FRONTEND_DIR / "theme"), "frontend_desktop/theme"),
        (str(FRONTEND_WEB_DIR), "frontend_web"),
    ],
    hiddenimports=all_hidden_imports + ["shiboken6"],
    hookspath=[],
    runtime_hooks=[],
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

app = BUNDLE(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name=APP_NAME,
    icon=str(BUILD_DIR / "AllahPan.icns") if (BUILD_DIR / "AllahPan.icns").exists() else None,
    # PyInstaller 仅合并 dict；传 plist 路径无效。需要自定义键时用 dict。
    info_plist={},
    bundle_identifier="com.allahpan.app",
)
