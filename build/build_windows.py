"""
AllahPan Windows Build Script (pure Python, no PowerShell encoding issues)
Usage: python build/build_windows.py
"""
import os
import sys
import subprocess
import shutil
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent.absolute()
BUILD_DIR = PROJECT_ROOT / "build"
DIST_DIR = PROJECT_ROOT / "dist"
APP_NAME = "AllahPan"
APP_DIR = DIST_DIR / APP_NAME
SPEC_FILE = PROJECT_ROOT / "AllahPan.spec"

# Resolve .venv python BEFORE any sys.executable use
_VENV_PY = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
if _VENV_PY.exists():
    PYTHON = str(_VENV_PY)
else:
    # fallback to current interpreter
    PYTHON = sys.executable


def info(msg):
    print(f"[INFO] {msg}")


def warn(msg):
    print(f"[WARN] {msg}")


def error(msg):
    print(f"[ERROR] {msg}")


def check_dependencies():
    info("Checking dependencies...")

    # Python
    result = subprocess.run([PYTHON, "--version"], capture_output=True, text=True)
    info(f"  Python: {result.stdout.strip()}")

    # PyInstaller
    result = subprocess.run([PYTHON, "-c", "import PyInstaller"], capture_output=True)
    if result.returncode != 0:
        warn("  PyInstaller not found, installing...")
        subprocess.run([PYTHON, "-m", "pip", "install", "pyinstaller"], check=True)
    else:
        info("  PyInstaller: OK")

    # Key packages
    pkgs = ["PySide6", "fastapi", "chromadb", "httpx", "uvicorn", "watchdog", "bcrypt"]
    missing_pkgs = []
    for pkg in pkgs:
        import_name = pkg.replace("-", "_")
        r = subprocess.run([PYTHON, "-c", f"import {import_name}"], capture_output=True)
        status = "OK" if r.returncode == 0 else "MISSING"
        info(f"  {pkg}: {status}")
        if r.returncode != 0:
            missing_pkgs.append(pkg)

    if missing_pkgs:
        warn(f"  Installing missing: {', '.join(missing_pkgs)}")
        subprocess.run([PYTHON, "-m", "pip", "install"] + missing_pkgs, check=True)
        info("  Missing packages installed.")

    # Spec file
    if not SPEC_FILE.exists():
        error(f"Spec file not found: {SPEC_FILE}")
        sys.exit(1)
    info(f"  Spec file: {SPEC_FILE}")


def clean():
    info("Cleaning build output directories...")
    dirs_to_clean = [
        DIST_DIR,
        PROJECT_ROOT / "backend" / "build",
        PROJECT_ROOT / "backend" / "dist",
        PROJECT_ROOT / "frontend_desktop" / "build",
        PROJECT_ROOT / "frontend_desktop" / "dist",
    ]
    for d in dirs_to_clean:
        if d.exists():
            shutil.rmtree(d)
            info(f"  Deleted: {d}")

    # Delete PyInstaller work/ cache inside build/ (NOT the whole directory!)
    # The build/ directory holds icons and plist files - protect it
    work_cache = PROJECT_ROOT / "build" / "build"
    if work_cache.exists():
        shutil.rmtree(work_cache)
        info(f"  Deleted cache: {work_cache}")

    # Delete __pycache__
    for cache in (PROJECT_ROOT / "build").rglob("__pycache__"):
        shutil.rmtree(cache)
        info(f"  Deleted: {cache}")

    for pattern in ["*.log"]:
        for f in PROJECT_ROOT.glob(pattern):
            if f.is_file():
                f.unlink()
                info(f"  Deleted: {f}")

    info("Clean complete")


def create_user_dirs():
    info("Creating user data directories...")
    dirs = [
        Path.home() / "Documents" / "AllahPan" / "files",
        Path.home() / "Documents" / "AllahPan" / "data",
        Path.home() / ".allahpan" / "logs",
        Path.home() / ".allahpan" / "data",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        info(f"  {d}")


def run_pyinstaller():
    info("Running PyInstaller...")

    # NOTE: When a .spec file is given, only general options are valid.
    # Do NOT use makespec-only options (--onedir, --windowed, --specpath, etc.)
    # Those are set inside the spec file itself.
    work_path = PROJECT_ROOT / "build"

    cmd = [
        PYTHON, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        str(SPEC_FILE),
    ]

    info(f"Running: {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)

    if result.returncode != 0:
        error(f"PyInstaller failed (exit code {result.returncode})")
        sys.exit(1)

    if APP_DIR.exists():
        info(f"Build output: {APP_DIR}")
        exe_path = APP_DIR / f"{APP_NAME}.exe"
        if exe_path.exists():
            size = exe_path.stat().st_size / (1024 * 1024)
            info(f"  AllahPan.exe: {size:.1f} MB")
    else:
        error(f"Build output not found: {APP_DIR}")
        sys.exit(1)

    info("PyInstaller complete")


def create_zip():
    info("Creating zip archive...")
    zip_path = DIST_DIR / "AllahPan-1.0.0-Windows-x64.zip"
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(APP_DIR):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(APP_DIR)
                zf.write(file_path, arcname)

    size = zip_path.stat().st_size / (1024 * 1024)
    info(f"  {zip_path} ({size:.1f} MB)")


def _get_special_folder(csidl):
    """Use ctypes to call Windows API SHGetFolderPathW directly."""
    import ctypes
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
    return Path(buf.value)


CSIDL_DESKTOP = 0x0000
CSIDL_PROGRAMS = 0x0002


def create_shortcuts():
    info("Creating shortcuts...")

    try:
        import pythoncom
        import win32com.client
    except ImportError:
        info("  pywin32 not installed, skipping shortcuts")
        return

    exe_path = APP_DIR / f"{APP_NAME}.exe"

    desktop = _get_special_folder(CSIDL_DESKTOP)
    desktop_lnk = desktop / f"{APP_NAME}.lnk"
    _make_shortcut(str(exe_path), str(desktop_lnk), str(APP_DIR))
    info(f"  Desktop: {desktop_lnk}")

    programs = _get_special_folder(CSIDL_PROGRAMS)
    start_lnk = programs / f"{APP_NAME}.lnk"
    _make_shortcut(str(exe_path), str(start_lnk), str(APP_DIR))
    info(f"  Start Menu: {start_lnk}")


def _make_shortcut(target, lnk_path, working_dir):
    import win32com.client
    import pythoncom

    pythoncom.CoInitialize()
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(lnk_path)
        shortcut.TargetPath = target
        shortcut.WorkingDirectory = working_dir
        shortcut.Description = "AllahPan - Family Private Cloud"
        shortcut.Save()
    finally:
        pythoncom.CoUninitialize()


def main():
    print("")
    print("=" * 50)
    print("  AllahPan Build Script (Windows)")
    print("=" * 50)
    print("")

    clean()
    check_dependencies()
    create_user_dirs()
    run_pyinstaller()
    create_zip()
    create_shortcuts()

    print("")
    print("=" * 50)
    print("  Build Complete!")
    print("=" * 50)
    print(f"  Output: {APP_DIR}")
    print(f"  Zip:    {DIST_DIR / 'AllahPan-1.0.0-Windows-x64.zip'}")
    print(f"  Run:    {APP_DIR / APP_NAME}.exe")
    print("")


if __name__ == "__main__":
    main()
