#!/usr/bin/env python3
"""
AllahPan 统一启动器脚本。

负责启动和管理 AllahPan 的所有服务组件：
- Ollama 推理引擎
- FastAPI 后端服务
- PySide6 桌面前端

支持：
- 前台启动（显示 GUI）
- 后台启动（守护进程模式）
- 单组件启动/停止
- 状态检查

作者: AllahPan团队
创建日期: 2026-03-20
"""

import argparse
import atexit
import logging
import os
import platform
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

# ==================== 配置 ====================

# 打包后 (PyInstaller) 使用 bundle 根目录，否则使用脚本所在目录
_FROZEN = getattr(sys, "frozen", False)
_MEIPASS = getattr(sys, "_MEIPASS", None)
if _FROZEN and _MEIPASS:
    _BUNDLE_ROOT = Path(_MEIPASS)
    PROJECT_ROOT = _BUNDLE_ROOT
    BACKEND_DIR = _BUNDLE_ROOT / "backend"
    FRONTEND_DIR = _BUNDLE_ROOT / "frontend_desktop"
else:
    PROJECT_ROOT = Path(__file__).resolve().parent
    BACKEND_DIR = PROJECT_ROOT / "backend"
    FRONTEND_DIR = PROJECT_ROOT / "frontend_desktop"

DATA_DIR = PROJECT_ROOT / "data" if not _FROZEN else (Path.home() / ".allahpan" / "data")

API_HOST = os.environ.get("ALLAHPAN_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("ALLAHPAN_PORT", "8000"))
OLLAMA_PORT = int(os.environ.get("OLLAMA_PORT", "11434"))

LOG_DIR = Path.home() / ".allahpan" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "launcher.log"

PID_DIR = Path.home() / ".allahpan" / "pids"
PID_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_MANAGER_ENABLED = True


def setup_logging(verbose: bool = False) -> None:
    """配置日志系统。"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )


class ProcessManager:
    """进程管理器。"""
    
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
        self._setup_signal_handlers()
        atexit.register(self.cleanup)
    
    def _setup_signal_handlers(self) -> None:
        def signal_handler(signum, frame):
            logging.info(f"收到信号 {signum}，正在停止所有服务...")
            self.cleanup()
            sys.exit(0)
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def cleanup(self) -> None:
        logging.info("正在清理所有子进程...")
        for name, proc in list(self.processes.items()):
            try:
                if proc.poll() is None:
                    logging.info(f"停止 {name}...")
                    if platform.system() == "Windows":
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                     capture_output=True, timeout=5)
                    else:
                        proc.terminate()
                        proc.wait(timeout=5)
            except Exception as e:
                logging.error(f"停止 {name} 失败: {e}")
        self.processes.clear()
        for f in PID_DIR.glob("*.pid"):
            try:
                f.unlink()
            except Exception:
                pass
        logging.info("清理完成")
    
    def start_process(
        self,
        name: str,
        cmd: List[str],
        cwd: Optional[Path] = None,
        env: Optional[Dict] = None,
        wait_for: Optional[Callable[[], bool]] = None,
        wait_timeout: int = 30,
    ) -> bool:
        if name in self.processes and self.processes[name].poll() is None:
            logging.warning(f"{name} 已在运行中")
            return True
        
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        
        try:
            logging.info(f"启动 {name}: {' '.join(cmd[:3])}...")
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=full_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            self.processes[name] = proc
            
            if wait_for:
                logging.info(f"等待 {name} 就绪...")
                for i in range(wait_timeout):
                    time.sleep(1)
                    if proc.poll() is not None:
                        stderr = proc.stderr.read().decode('utf-8', errors='replace') if proc.stderr else ""
                        logging.error(f"{name} 启动失败: {stderr[:200]}")
                        return False
                    if wait_for():
                        break
                else:
                    logging.warning(f"{name} 启动超时")
            
            pid_file = PID_DIR / f"{name}.pid"
            pid_file.write_text(str(proc.pid))
            logging.info(f"{name} 已启动，PID: {proc.pid}")
            return True
        except Exception as e:
            logging.error(f"启动 {name} 失败: {e}")
            return False
    
    def stop_process(self, name: str) -> bool:
        if name not in self.processes:
            logging.warning(f"{name} 未运行")
            return True
        proc = self.processes[name]
        try:
            if proc.poll() is None:
                logging.info(f"停止 {name}...")
                if platform.system() == "Windows":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                 capture_output=True, timeout=10)
                else:
                    proc.terminate()
                    proc.wait(timeout=10)
            del self.processes[name]
            (PID_DIR / f"{name}.pid").unlink(missing_ok=True)
            logging.info(f"{name} 已停止")
            return True
        except Exception as e:
            logging.error(f"停止 {name} 失败: {e}")
            return False


class OllamaHelper:
    """Ollama 辅助类。"""
    
    @staticmethod
    def is_running() -> bool:
        try:
            import httpx
            response = httpx.get(f"http://localhost:{OLLAMA_PORT}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False
    
    @staticmethod
    def wait_for_service(timeout: int = 60) -> bool:
        logging.info(f"等待 Ollama 服务就绪（最多 {timeout} 秒）...")
        for i in range(timeout):
            if OllamaHelper.is_running():
                logging.info("Ollama 服务已就绪")
                return True
            time.sleep(1)
        logging.warning("Ollama 服务未在预期时间内就绪")
        return False
    
    @staticmethod
    def start_server() -> bool:
        if OllamaHelper.is_running():
            logging.info("Ollama 服务已在运行")
            return True
        try:
            env = os.environ.copy()
            env["OLLAMA_HOST"] = f"127.0.0.1:{OLLAMA_PORT}"
            subprocess.Popen(
                ["ollama", "serve"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return OllamaHelper.wait_for_service()
        except Exception as e:
            logging.error(f"启动 Ollama 失败: {e}")
            return False


class Launcher:
    """AllahPan 启动器。"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.process_manager = ProcessManager()
    
    def check_environment(self) -> bool:
        logging.info("检查运行环境...")
        
        if sys.version_info < (3, 10):
            logging.error("需要 Python 3.10 或更高版本")
            return False
        
        if not BACKEND_DIR.exists():
            logging.error(f"后端目录不存在: {BACKEND_DIR}")
            return False
        
        if not FRONTEND_DIR.exists():
            logging.error(f"前端目录不存在: {FRONTEND_DIR}")
            return False
        
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logging.warning(f"创建 DATA_DIR 失败（将使用默认）: {e}")
        logging.info("环境检查完成")
        return True
    
    def start_backend(self, wait: bool = True) -> bool:
        logging.info("启动后端服务...")
        
        if OLLAMA_MANAGER_ENABLED and not OllamaHelper.is_running():
            OllamaHelper.start_server()
        
        sys.path.insert(0, str(BACKEND_DIR))
        
        return self.process_manager.start_process(
            name="api",
            cmd=[sys.executable, "-m", "uvicorn", "app.main:app",
                 "--host", API_HOST, "--port", str(API_PORT)],
            cwd=BACKEND_DIR,
            env={
                "ALLAHPAN_HOST": API_HOST,
                "ALLAHPAN_PORT": str(API_PORT),
                "PYTHONPATH": str(BACKEND_DIR),
            },
            wait_for=(lambda: self._check_api_ready()) if wait else None,
            wait_timeout=30,
        )
    
    def _check_api_ready(self) -> bool:
        try:
            import httpx
            response = httpx.get(f"http://localhost:{API_PORT}/health", timeout=2)
            return response.status_code == 200
        except Exception:
            return False
    
    def start_frontend(self) -> bool:
        logging.info("启动前端界面...")
        
        if _FROZEN:
            # 打包后不能再用 subprocess 调 exe，由 run_frozen_gui() 在主线程启动
            return True
        
        return self.process_manager.start_process(
            name="gui",
            cmd=[sys.executable, "run.py"],
            cwd=FRONTEND_DIR,
            env={
                "ALLAHPAN_HOST": "localhost" if API_HOST == "0.0.0.0" else API_HOST,
                "ALLAHPAN_PORT": str(API_PORT),
            },
        )
    
    def _run_backend_in_thread(self) -> None:
        """在后台线程中运行 FastAPI（仅打包后使用）。"""
        import threading
        sys.path.insert(0, str(BACKEND_DIR))
        try:
            import uvicorn
            from app.main import app
            # 打包环境下避免 uvicorn 默认 log_config 的 formatter 解析失败（Unable to configure formatter 'default'）
            _log_config = (
                {
                    "version": 1,
                    "disable_existing_loggers": False,
                    "formatters": {
                        "default": {"format": "%(levelname)s %(message)s"},
                        "access": {"format": "%(levelname)s %(message)s"},
                    },
                    "handlers": {
                        "default": {"formatter": "default", "class": "logging.StreamHandler", "stream": "ext://sys.stderr"},
                        "access": {"formatter": "access", "class": "logging.StreamHandler", "stream": "ext://sys.stdout"},
                    },
                    "loggers": {
                        "uvicorn": {"handlers": ["default"], "level": "WARNING", "propagate": False},
                        "uvicorn.error": {"level": "WARNING"},
                        "uvicorn.access": {"handlers": ["access"], "level": "WARNING", "propagate": False},
                    },
                }
                if _FROZEN
                else None
            )
            uvicorn.run(
                app,
                host=API_HOST,
                port=API_PORT,
                log_level="warning",
                log_config=_log_config,
            )
        except Exception as e:
            logging.error(f"后端线程异常: {e}")
    
    def _run_frozen_gui(self) -> int:
        """打包后：在主线程运行 Qt GUI，返回 exit code。"""
        # 打包环境下：在导入任何 Qt 相关模块前，设置 DLL 搜索路径并预加载 Qt 依赖
        if _FROZEN and _MEIPASS:
            _m = os.path.abspath(_MEIPASS)
            _pyside6 = os.path.join(_m, "PySide6")
            _shiboken6 = os.path.join(_m, "shiboken6")
            _plugins = os.path.join(_pyside6, "plugins")
            _platforms = os.path.join(_plugins, "platforms")
            # 可执行文件所在目录（PyInstaller 6 one-folder 时 exe 在上级，依赖在 _MEIPASS）
            _exe_dir = os.path.dirname(sys.executable)
            _path = os.environ.get("PATH", "")
            os.environ["PATH"] = os.pathsep.join([_exe_dir, _m, _shiboken6, _pyside6, _plugins, _platforms, _path])
            os.environ["QT_PLUGIN_PATH"] = _plugins
            # 使用 add_dll_directory 确保 Windows 能从 bundle 内加载 Qt/shiboken 及平台插件依赖
            if hasattr(os, "add_dll_directory"):
                try:
                    if os.path.isdir(_exe_dir):
                        os.add_dll_directory(_exe_dir)
                    os.add_dll_directory(_m)
                    if os.path.isdir(_shiboken6):
                        os.add_dll_directory(_shiboken6)
                    if os.path.isdir(_pyside6):
                        os.add_dll_directory(_pyside6)
                    if os.path.isdir(_plugins):
                        os.add_dll_directory(_plugins)
                    if os.path.isdir(_platforms):
                        os.add_dll_directory(_platforms)
                except Exception as e:
                    logging.warning(f"add_dll_directory 设置失败（将仅依赖 PATH）: {e}")
            # 先导入 shiboken6，再导入前端（前端会导入 PySide6.QtWidgets），避免 DLL 加载顺序问题
            try:
                import shiboken6  # noqa: F401
            except Exception as e:
                logging.warning(f"预加载 shiboken6 失败: {e}")
            # 用 ctypes 按依赖顺序预加载 Qt 核心 DLL，避免系统 PATH 中错误版本被优先加载导致「找不到指定的程序」
            try:
                import ctypes
                _qt_dlls = [
                    os.path.join(_pyside6, "Qt6Core.dll"),
                    os.path.join(_pyside6, "Qt6Gui.dll"),
                    os.path.join(_pyside6, "Qt6Widgets.dll"),
                ]
                for _dll in _qt_dlls:
                    if os.path.isfile(_dll):
                        ctypes.CDLL(_dll)
            except Exception as e:
                logging.debug("预加载 Qt DLL 跳过或失败（将依赖默认加载）: %s", e)
        # 确保前端可被导入
        if str(FRONTEND_DIR) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        os.chdir(FRONTEND_DIR)
        os.environ.setdefault("ALLAHPAN_HOST", "localhost" if API_HOST == "0.0.0.0" else API_HOST)
        os.environ.setdefault("ALLAHPAN_PORT", str(API_PORT))
        try:
            import frontend_desktop.run as run_module
            return run_module.main()
        except Exception as e:
            logging.exception(f"启动 GUI 失败: {e}")
            return 1
    
    def start_all(self) -> bool:
        if not self.check_environment():
            return False
        
        if not self.start_backend(wait=True):
            return False
        
        time.sleep(2)
        
        return self.start_frontend()
    
    def stop_all(self) -> bool:
        self.process_manager.cleanup()
        return True
    
    def status(self) -> Dict[str, dict]:
        result = {
            "api": {"running": False, "pid": None},
            "ollama": {"running": OllamaHelper.is_running(), "port": OLLAMA_PORT},
            "gui": {"running": False, "pid": None},
        }
        
        for name in ["api", "gui"]:
            pid_file = PID_DIR / f"{name}.pid"
            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip())
                    try:
                        os.kill(pid, 0)
                        result[name]["running"] = True
                        result[name]["pid"] = pid
                    except OSError:
                        pid_file.unlink()
                except Exception:
                    pass
        
        return result


def main():
    parser = argparse.ArgumentParser(
        description="AllahPan 统一启动器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python launcher.py              启动所有组件
  python launcher.py --backend    仅启动后端
  python launcher.py --gui        仅启动前端
  python launcher.py --status    查看状态
  python launcher.py --stop      停止所有组件
  python launcher.py -v           详细输出
        """
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    parser.add_argument("--backend", action="store_true", help="仅启动后端")
    parser.add_argument("--gui", action="store_true", help="仅启动前端")
    parser.add_argument("--status", action="store_true", help="查看状态")
    parser.add_argument("--stop", action="store_true", help="停止所有组件")
    parser.add_argument("--no-ollama", action="store_true", help="不自动启动 Ollama")
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    if _FROZEN:
        logging.info("AllahPan.exe 已启动 (frozen)，工作目录: %s", os.getcwd())
    
    global OLLAMA_MANAGER_ENABLED
    if args.no_ollama:
        OLLAMA_MANAGER_ENABLED = False
    
    launcher = Launcher(args.verbose)
    
    if args.status:
        status = launcher.status()
        print("\n=== AllahPan 服务状态 ===")
        for name, info in status.items():
            pid = info.get("pid", "-")
            running = "运行中" if info.get("running") else "已停止"
            extra = f", 端口: {info.get('port')}" if "port" in info else f", PID: {pid}"
            print(f"  {name.upper()}: {running}{extra}")
        print()
        return 0
    
    if args.stop:
        launcher.stop_all()
        print("所有服务已停止")
        return 0
    
    # 打包后：单进程内启动后端线程 + 主线程 GUI，不弹控制台
    if _FROZEN and not (args.status or args.stop):
        if not launcher.check_environment():
            return 1
        if OLLAMA_MANAGER_ENABLED and not args.no_ollama and not OllamaHelper.is_running():
            OllamaHelper.start_server()
        # 后端在守护线程中运行
        backend_thread = threading.Thread(target=launcher._run_backend_in_thread, daemon=True)
        backend_thread.start()
        # 等待 API 就绪
        for _ in range(25):
            if launcher._check_api_ready():
                break
            time.sleep(0.2)
        # 主线程运行 Qt GUI
        return launcher._run_frozen_gui()
    
    if args.backend:
        success = launcher.start_backend()
    elif args.gui:
        success = launcher.start_frontend()
    else:
        success = launcher.start_all()
    
    if success:
        print("AllahPan 启动成功！")
        print(f"API 地址: http://localhost:{API_PORT}")
        print(f"按 Ctrl+C 停止所有服务")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            launcher.stop_all()
    else:
        print("启动失败，请检查日志")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
