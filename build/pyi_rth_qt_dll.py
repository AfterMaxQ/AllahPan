# -*- coding: utf-8 -*-
"""
自定义 PyInstaller runtime hook：在 Windows 上为 Qt/PySide6 注册 DLL 搜索路径。
必须在任何 PySide6/shiboken6 导入之前执行，故放在 runtime_hooks 最前。
"""
import os
import sys


def _hook():
    if not sys.platform.startswith("win"):
        return
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return
    meipass = os.path.abspath(meipass)
    # 优先从打包目录加载 DLL，避免加载到系统 PATH 中错误版本的 ICU/OpenSSL 等
    try:
        path_env = os.environ.get("PATH", "")
        os.environ["PATH"] = meipass + os.pathsep + os.path.join(meipass, "PySide6") + os.pathsep + path_env
    except Exception:
        pass
    if not hasattr(os, "add_dll_directory"):
        return
    pyside6 = os.path.join(meipass, "PySide6")
    plugins = os.path.join(pyside6, "plugins")
    platforms = os.path.join(plugins, "platforms")
    dirs = [
        meipass,
        os.path.join(meipass, "shiboken6"),
        pyside6,
        plugins,
        platforms,
    ]
    for d in dirs:
        if os.path.isdir(d):
            try:
                os.add_dll_directory(d)
            except Exception:
                pass


_hook()
del _hook
