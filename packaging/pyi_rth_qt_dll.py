# PyInstaller runtime hook (Windows): register bundle DLL search paths before Qt/shiboken load.
# See AllahPan.spec runtime_hooks.


def _pyi_rthook():
    import os
    import sys

    if not getattr(sys, "frozen", False) or not sys.platform.startswith("win"):
        return
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass or not hasattr(os, "add_dll_directory"):
        return
    candidates = [
        meipass,
        os.path.join(meipass, "shiboken6"),
        os.path.join(meipass, "PySide6"),
        os.path.join(meipass, "PySide6", "plugins"),
        os.path.join(meipass, "PySide6", "plugins", "platforms"),
    ]
    for d in candidates:
        if os.path.isdir(d):
            try:
                os.add_dll_directory(d)
            except OSError:
                pass


_pyi_rthook()
del _pyi_rthook
