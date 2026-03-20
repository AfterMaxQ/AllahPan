"""
Ollama 引擎管理器模块。

本模块负责管理 Ollama 推理引擎的进程生命周期，包括：
- 启动和停止 Ollama 服务进程
- 检测端口占用情况
- 自动加载 AI 模型
- 异常检测和自动重启机制
- 状态监控和健康检查

适用于一体化打包场景，提供本地 Ollama 引擎的自动化管理。

作者: AllahPan团队
创建日期: 2026-03-20
"""

import asyncio
import json
import logging
import os
import platform
import signal
import socket
import subprocess
import sys
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

logger = logging.getLogger(__name__)


class OllamaStatus(Enum):
    """Ollama 引擎状态枚举。"""
    STOPPED = "stopped"           # 已停止
    STARTING = "starting"          # 正在启动
    RUNNING = "running"           # 运行中
    LOADING_MODEL = "loading"     # 正在加载模型
    ERROR = "error"               # 错误状态
    UNKNOWN = "unknown"           # 未知状态


class OllamaManager:
    """
    Ollama 推理引擎管理器类。
    
    负责 Ollama 进程的完整生命周期管理，支持：
    - 进程启动/停止/重启
    - 端口检测和占用处理
    - 模型自动加载
    - 异常自动恢复
    - 状态监控和事件回调
    
    属性:
        ollama_path: Ollama 可执行文件路径
        host: Ollama 服务监听地址
        port: Ollama 服务监听端口
        models: 需要自动加载的模型列表
        auto_restart: 是否启用自动重启
        restart_delay: 重启延迟时间（秒）
    """
    
    DEFAULT_PORT = 11434
    DEFAULT_HOST = "localhost"
    OLLAMA_ENV_VAR = "OLLAMA_HOST"
    OLLAMA_MODELS_ENV_VAR = "OLLAMA_MODELS"
    
    # Ollama 官方模型列表（常用的视觉和嵌入模型）
    DEFAULT_MODELS = [
        "qwen3-vl:4b",           # 多模态视觉模型
        "nomic-embed-text-v2-moe",  # 文本向量化模型
        "bge-m3",                # 向量化备选模型
    ]
    
    def __init__(
        self,
        ollama_path: Optional[str] = None,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        models: Optional[List[str]] = None,
        auto_restart: bool = True,
        restart_delay: int = 5,
        restart_max_attempts: int = 3,
    ):
        """
        初始化 Ollama 管理器。
        
        参数:
            ollama_path: Ollama 可执行文件路径，默认自动检测
            host: Ollama 服务监听地址
            port: Ollama 服务监听端口
            models: 需要自动加载的模型列表
            auto_restart: 是否启用异常自动重启
            restart_delay: 重启延迟时间（秒）
            restart_max_attempts: 最大重启尝试次数
        """
        self.ollama_path = ollama_path or self._detect_ollama_path()
        self.host = host
        self.port = port
        self.models = models or self.DEFAULT_MODELS.copy()
        self.auto_restart = auto_restart
        self.restart_delay = restart_delay
        self.restart_max_attempts = restart_max_attempts
        
        # 内部状态
        self._process: Optional[subprocess.Popen] = None
        self._status = OllamaStatus.STOPPED
        self._status_lock = threading.RLock()
        self._start_time: Optional[float] = None
        self._restart_count = 0
        self._error_message: Optional[str] = None
        self._running_loop: Optional[asyncio.AbstractEventLoop] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._watchdog_timer: Optional[threading.Timer] = None
        self._shutdown_event = threading.Event()
        self._consecutive_failures = 0  # 连续失败计数器
        self._max_consecutive_failures = 3  # 最大连续失败次数阈值
        
        # 事件回调
        self._on_status_change: Optional[Callable[[OllamaStatus, Optional[str]], None]] = None
        self._on_model_loaded: Optional[Callable[[str], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None
        
        logger.info(
            f"OllamaManager 初始化完成: "
            f"路径={self.ollama_path}, 主机={self.host}:{self.port}, "
            f"自动重启={auto_restart}, 模型={self.models}"
        )
    
    def _detect_ollama_path(self) -> str:
        """
        自动检测 Ollama 可执行文件路径。
        
        检测顺序：
        1. 环境变量 OLLAMA_PATH
        2. 系统 PATH 中的 ollama 命令
        3. 常见安装路径（macOS/Linux/Windows）
        
        返回:
            str: Ollama 可执行文件路径
        """
        # 优先检查环境变量
        env_path = os.environ.get("OLLAMA_PATH")
        if env_path and Path(env_path).exists():
            logger.info(f"从环境变量检测到 Ollama 路径: {env_path}")
            return env_path
        
        system = platform.system()
        
        if system == "Darwin":  # macOS
            common_paths = [
                "/usr/local/bin/ollama",
                "/opt/homebrew/bin/ollama",
                str(Path.home() / ".local" / "bin" / "ollama"),
                "/Applications/Ollama.app/Contents/MacOS/ollama",
            ]
        elif system == "Linux":
            common_paths = [
                "/usr/local/bin/ollama",
                "/usr/bin/ollama",
                str(Path.home() / ".local" / "bin" / "ollama"),
            ]
        elif system == "Windows":
            common_paths = [
                str(Path(os.environ.get("LOCALAPPDATA", "")) / "Ollama" / "ollama.exe"),
                str(Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Ollama" / "ollama.exe"),
                "ollama.exe",  # PATH 中
            ]
        else:
            common_paths = ["ollama"]  # 假设在 PATH 中
        
        for path in common_paths:
            if Path(path).exists():
                logger.info(f"自动检测到 Ollama 路径: {path}")
                return path
        
        # 尝试从 PATH 获取
        try:
            result = subprocess.run(
                ["which", "ollama"] if system != "Windows" else ["where", "ollama"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                found_path = result.stdout.strip().split("\n")[0]
                logger.info(f"从 PATH 检测到 Ollama: {found_path}")
                return found_path
        except Exception as e:
            logger.debug(f"从 PATH 检测 Ollama 失败: {e}")
        
        logger.warning("未检测到 Ollama，使用默认路径 'ollama'（需要确保在 PATH 中）")
        return "ollama"
    
    @property
    def status(self) -> OllamaStatus:
        """获取当前状态。"""
        with self._status_lock:
            return self._status
    
    @property
    def is_running(self) -> bool:
        """检查 Ollama 是否正在运行。"""
        return self.status == OllamaStatus.RUNNING or self.status == OllamaStatus.LOADING_MODEL
    
    @property
    def error_message(self) -> Optional[str]:
        """获取错误信息。"""
        return self._error_message
    
    @property
    def uptime(self) -> Optional[float]:
        """获取运行时间（秒）。"""
        if self._start_time is None:
            return None
        return time.time() - self._start_time
    
    def set_status(self, status: OllamaStatus, error: Optional[str] = None) -> None:
        """
        设置状态并触发回调。
        
        参数:
            status: 新状态
            error: 错误信息（如果有）
        """
        with self._status_lock:
            old_status = self._status
            self._status = status
            self._error_message = error
            
            if status == OllamaStatus.ERROR:
                logger.error(f"Ollama 状态变为 ERROR: {error}")
            elif old_status != status:
                logger.info(f"Ollama 状态变化: {old_status.value} -> {status.value}")
        
        # 触发回调（线程安全）
        if self._on_status_change:
            try:
                self._on_status_change(status, error)
            except Exception as e:
                logger.error(f"状态变化回调执行失败: {e}")
    
    def set_on_status_change(self, callback: Callable[[OllamaStatus, Optional[str]], None]) -> None:
        """设置状态变化回调。"""
        self._on_status_change = callback
    
    def set_on_model_loaded(self, callback: Callable[[str], None]) -> None:
        """设置模型加载完成回调。"""
        self._on_model_loaded = callback
    
    def set_on_error(self, callback: Callable[[str], None]) -> None:
        """设置错误回调。"""
        self._on_error = callback
    
    def is_port_in_use(self, port: int = None) -> bool:
        """
        检查端口是否被占用。
        
        参数:
            port: 端口号，默认使用配置的端口
            
        返回:
            bool: 端口已被占用返回 True
        """
        port = port or self.port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(1)
            result = sock.connect_ex(("localhost", port))
            return result == 0
        except socket.error:
            return False
        finally:
            sock.close()
    
    def _find_process_by_port(self, port: int = None) -> Optional[Dict[str, Any]]:
        """
        根据端口查找进程信息。
        
        参数:
            port: 端口号
            
        返回:
            dict: 进程信息，包含 pid, name, cmdline 等
        """
        port = port or self.port
        system = platform.system()
        
        try:
            if system == "Darwin" or system == "Linux":
                # 使用 lsof 命令查找
                result = subprocess.run(
                    ["lsof", "-i", f":{port}", "-P", "-n", "-sTCP:LISTEN"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    if len(lines) > 1:
                        parts = lines[1].split()
                        if len(parts) >= 2:
                            return {
                                "pid": int(parts[1]),
                                "name": parts[0],
                            }
            elif system == "Windows":
                # 使用 netstat 查找端口对应的 PID
                result = subprocess.run(
                    ["netstat", "-ano", "-p", "tcp"],
                    capture_output=True,
                    text=True,
                    encoding="gbk",
                    timeout=10,
                )
                pid = None
                for line in result.stdout.split("\n"):
                    if f":{port}" in line and "LISTENING" in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            pid = int(parts[-1])
                            break
                
                if pid:
                    # 使用 tasklist 查询进程名称
                    try:
                        tasklist_result = subprocess.run(
                            ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                            capture_output=True,
                            text=True,
                            encoding="gbk",
                            timeout=5,
                        )
                        if tasklist_result.returncode == 0:
                            lines = tasklist_result.stdout.strip().split("\n")
                            if lines:
                                # CSV 格式：Image Name,PID,Session Name,Session#,Mem Usage
                                csv_parts = lines[0].strip('"').split('","')
                                if len(csv_parts) >= 2:
                                    process_name = csv_parts[0].strip('"')
                                    return {
                                        "pid": pid,
                                        "name": process_name,
                                    }
                    except Exception as e:
                        logger.debug(f"查询进程名称失败：{e}")
                    
                    # 如果查询失败，至少返回 PID
                    return {
                        "pid": pid,
                        "name": "unknown",
                    }
        except Exception as e:
            logger.warning(f"查找端口 {port} 进程失败: {e}")
        
        return None
    
    def check_service_available(self) -> bool:
        """
        检查 Ollama HTTP 服务是否可用。
        
        通过发送健康检查请求验证服务状态；失败时重试一次以减少误报。
        
        返回:
            bool: 服务可用返回 True
        """
        import httpx

        def _do_get(timeout: float = 5.0) -> bool:
            try:
                response = httpx.get(
                    f"http://{self.host}:{self.port}/api/tags",
                    timeout=timeout,
                )
                return response.status_code == 200
            except Exception as e:
                logger.debug(f"Ollama 服务不可用: {e}")
                return False

        if _do_get():
            return True
        time.sleep(1)
        return _do_get()
    
    async def _check_service_available_async(self) -> bool:
        """
        异步检查 Ollama HTTP 服务是否可用。
        
        返回:
            bool: 服务可用返回 True
        """
        import httpx
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://{self.host}:{self.port}/api/tags",
                    timeout=5.0,
                )
                return response.status_code == 200
        except Exception:
            return False
    
    def start(self, timeout: int = 60) -> bool:
        """
        启动 Ollama 引擎。
        
        如果端口已被占用，会尝试终止占用进程或使用已有服务。
        
        参数:
            timeout: 启动超时时间（秒）
            
        返回:
            bool: 启动成功返回 True
        """
        if self.is_running:
            logger.info("Ollama 已在运行中，无需重复启动")
            return True
        
        self.set_status(OllamaStatus.STARTING)
        self._shutdown_event.clear()
        self._consecutive_failures = 0  # 重置失败计数
        
        # 检查端口是否已被占用
        if self.is_port_in_use():
            logger.info(f"端口 {self.port} 已被占用，检查是否有 Ollama 服务运行...")
            if self.check_service_available():
                logger.info("检测到已有的 Ollama 服务，正在使用...")
                self._start_time = time.time()
                self.set_status(OllamaStatus.RUNNING)
                self._schedule_model_loading()
                return True
            else:
                # 端口被占用但不是 Ollama，尝试终止
                process_info = self._find_process_by_port()
                if process_info:
                    logger.warning(f"端口被进程 {process_info['name']}(PID: {process_info['pid']}) 占用")
                    # 不自动终止其他进程，抛出错误
                    self.set_status(OllamaStatus.ERROR, f"端口 {self.port} 被其他进程占用")
                    return False
        
        # 启动 Ollama 进程
        try:
            logger.info(f"正在启动 Ollama 引擎: {self.ollama_path}")
            
            # 构建环境变量
            env = os.environ.copy()
            env["OLLAMA_HOST"] = f"{self.host}:{self.port}"
            env["OLLAMA_MODELS"] = str(Path.home() / ".ollama" / "models")
            
            # 启动进程
            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            self._process = subprocess.Popen(
                [self.ollama_path, "serve"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
                encoding="utf-8",
                errors="replace",
            )
            
            # 等待服务就绪
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self.check_service_available():
                    logger.info(f"Ollama 引擎启动成功 (PID: {self._process.pid})")
                    self._start_time = time.time()
                    self.set_status(OllamaStatus.RUNNING)
                    self._restart_count = 0
                    self._consecutive_failures = 0  # 重置失败计数
                    self._start_watchdog()
                    self._schedule_model_loading()
                    return True
                time.sleep(0.5)
            
            # 超时但进程仍在运行
            if self._process.poll() is None:
                logger.warning("Ollama 启动超时，但进程仍在运行")
                self._start_time = time.time()
                self.set_status(OllamaStatus.RUNNING)
                return True
            
            # 进程已退出
            stderr = self._process.stderr.read().decode("utf-8", errors="replace") if self._process.stderr else ""
            error_msg = f"Ollama 启动失败: {stderr or '进程异常退出'}"
            logger.error(error_msg)
            self.set_status(OllamaStatus.ERROR, error_msg)
            return False
            
        except FileNotFoundError:
            error_msg = f"Ollama 可执行文件未找到: {self.ollama_path}"
            logger.error(error_msg)
            self.set_status(OllamaStatus.ERROR, error_msg)
            return False
        except PermissionError:
            error_msg = f"没有权限启动 Ollama: {self.ollama_path}"
            logger.error(error_msg)
            self.set_status(OllamaStatus.ERROR, error_msg)
            return False
        except Exception as e:
            error_msg = f"启动 Ollama 失败: {str(e)}"
            logger.error(error_msg)
            self.set_status(OllamaStatus.ERROR, error_msg)
            return False
    
    def stop(self, timeout: int = 10) -> bool:
        """
        停止 Ollama 引擎。
        
        参数:
            timeout: 停止超时时间（秒）
            
        返回:
            bool: 停止成功返回 True
        """
        logger.info("正在停止 Ollama 引擎...")
        self._shutdown_event.set()
        self._stop_watchdog()
        
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            self._monitor_task = None
        
        if self._process is None:
            logger.info("Ollama 进程不存在，已停止")
            self.set_status(OllamaStatus.STOPPED)
            return True
        
        try:
            # 尝试优雅终止
            system = platform.system()
            
            if system == "Windows":
                # Windows 使用 taskkill
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self._process.pid)],
                    capture_output=True,
                    timeout=timeout,
                )
            else:
                # Unix 系统使用 SIGTERM
                self._process.terminate()
                try:
                    self._process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # 强制杀死
                    self._process.kill()
                    self._process.wait()
            
            logger.info("Ollama 引擎已停止")
            self._process = None
            self._start_time = None
            self.set_status(OllamaStatus.STOPPED)
            return True
            
        except Exception as e:
            logger.error(f"停止 Ollama 失败: {e}")
            # 强制终止
            try:
                if self._process:
                    self._process.kill()
            except Exception:
                pass
            self._process = None
            self.set_status(OllamaStatus.STOPPED)
            return False
    
    def restart(self, timeout: int = 60) -> bool:
        """
        重启 Ollama 引擎。
        
        参数:
            timeout: 启动超时时间（秒）
            
        返回:
            bool: 重启成功返回 True
        """
        logger.info("正在重启 Ollama 引擎...")
        self.stop()
        time.sleep(1)
        return self.start(timeout)
    
    def _start_watchdog(self) -> None:
        """启动看门狗定时器，监控进程状态。"""
        self._watchdog_timer = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name="OllamaWatchdog",
        )
        self._watchdog_timer.start()
        logger.debug("看门狗线程已启动")
    
    def _stop_watchdog(self) -> None:
        """停止看门狗线程：先 join 再清空引用，与 tunnel_manager 一致，避免线程泄漏。"""
        t = self._watchdog_timer
        self._watchdog_timer = None
        if t is not None and getattr(t, "is_alive", lambda: False)():
            t.join(timeout=5)
    
    def _watchdog_loop(self) -> None:
        """看门狗循环，监控 Ollama 进程状态。"""
        check_interval = 5  # 每 5 秒检查一次
        
        while not self._shutdown_event.is_set():
            try:
                if self._shutdown_event.wait(timeout=check_interval):
                    break
                
                # 检查进程状态
                if self._process is not None:
                    poll_result = self._process.poll()
                    if poll_result is not None:
                        # 进程已退出
                        stderr = ""
                        try:
                            stderr = self._process.stderr.read().decode("utf-8", errors="replace") if self._process.stderr else ""
                        except Exception:
                            pass
                        
                        error_msg = f"Ollama 进程异常退出，退出码: {poll_result}"
                        if stderr:
                            error_msg += f"，错误信息: {stderr[:200]}"
                        
                        logger.error(error_msg)
                        self._handle_process_exit(error_msg)
                        break
                
                # 检查服务可用性（仅当进程已退出或未管理进程时才计失败，避免与前端 200 OK 矛盾）
                if not self.check_service_available():
                    process_alive = self._process is not None and self._process.poll() is None
                    if not process_alive:
                        self._consecutive_failures += 1
                        logger.warning(f"Ollama HTTP 服务不可用 (连续失败 {self._consecutive_failures}/{self._max_consecutive_failures})")
                        if self._consecutive_failures >= self._max_consecutive_failures:
                            logger.warning("达到连续失败阈值，处理服务不可用情况")
                            self._handle_service_unavailable()
                    else:
                        if self._consecutive_failures > 0:
                            self._consecutive_failures = 0
                else:
                    if self._consecutive_failures > 0:
                        logger.info("Ollama HTTP 服务恢复，重置失败计数")
                        self._consecutive_failures = 0
                    
            except Exception as e:
                logger.error(f"看门狗检查失败: {e}")
    
    def _handle_process_exit(self, error_msg: str) -> None:
        """处理进程异常退出。"""
        self.set_status(OllamaStatus.ERROR, error_msg)
        
        if self.auto_restart and self._restart_count < self.restart_max_attempts:
            self._restart_count += 1
            logger.info(f"尝试自动重启 Ollama ({self._restart_count}/{self.restart_max_attempts})...")
            time.sleep(self.restart_delay)
            self._consecutive_failures = 0  # 重启前重置失败计数
            self.start()
        else:
            logger.error("已达到最大重启次数或自动重启已禁用")
    
    def _handle_service_unavailable(self) -> None:
        """处理服务不可用情况。"""
        # 若当前管理的进程仍在运行，视为暂时繁忙，仅重置计数，避免执行耗时的 netstat/tasklist
        if self._process is not None and self._process.poll() is None:
            logger.info("Ollama 进程仍在运行，视为暂时繁忙，重置失败计数")
            self._consecutive_failures = 0
            return
        # 检查端口是否被占用
        if self.is_port_in_use():
            # 端口被占用，检查是否是 Ollama 进程本身
            process_info = self._find_process_by_port()
            if process_info:
                # 验证占用端口的进程是否是 Ollama 本身
                if self._process is not None and process_info['pid'] == self._process.pid:
                    # 是 Ollama 进程本身，可能是服务暂时繁忙或网络波动
                    logger.info(f"端口被 Ollama 自身占用 (PID: {process_info['pid']})，服务可能正在启动或繁忙，重置失败计数")
                    self._consecutive_failures = 0  # 重置失败计数
                    return
                elif process_info['name'].lower() in ['ollama', 'ollama.exe']:
                    # 进程名是 ollama，但 PID 不匹配，可能是之前启动的残留进程
                    logger.warning(f"端口被 Ollama 进程占用 (PID: {process_info['pid']})，但不是当前管理的进程，重置失败计数")
                    self._consecutive_failures = 0  # 重置失败计数
                    return
                else:
                    # 确实是其他进程占用
                    logger.warning(f"端口被其他进程占用：{process_info}")
                    self.set_status(OllamaStatus.ERROR, f"端口 {self.port} 被进程 {process_info['name']} (PID: {process_info['pid']}) 占用")
            else:
                # 无法获取进程信息
                logger.warning(f"端口 {self.port} 被占用，但无法获取进程信息，重置失败计数")
                self._consecutive_failures = 0  # 重置失败计数
        else:
            # 端口未被占用，服务可能已崩溃
            if self.auto_restart:
                logger.warning("Ollama 服务崩溃，尝试重启...")
                self.restart()
            else:
                self.set_status(OllamaStatus.ERROR, "Ollama 服务不可用")
    
    def _schedule_model_loading(self) -> None:
        """安排模型加载任务。"""
        threading.Thread(
            target=self._load_models_thread,
            daemon=True,
            name="OllamaModelLoader",
        ).start()
    
    def _load_models_thread(self) -> None:
        """后台线程加载模型。"""
        time.sleep(2)  # 等待服务完全就绪
        
        if self._shutdown_event.is_set():
            return
        
        for model in self.models:
            if self._shutdown_event.is_set():
                break
            try:
                list_result = subprocess.run(
                    [self.ollama_path, "list"],
                    capture_output=True,
                    timeout=30,
                    text=True,
                )
                if list_result.returncode == 0 and list_result.stdout and model in list_result.stdout:
                    logger.info(f"模型已存在，跳过拉取: {model}")
                    if self._on_model_loaded:
                        try:
                            self._on_model_loaded(model)
                        except Exception as e:
                            logger.error(f"模型加载回调执行失败: {e}")
                    continue
                logger.info(f"正在加载模型: {model}")
                self.set_status(OllamaStatus.LOADING_MODEL)
                result = subprocess.run(
                    [self.ollama_path, "pull", model],
                    capture_output=True,
                    timeout=600,
                )
                if result.returncode == 0:
                    logger.info(f"模型加载成功: {model}")
                    if self._on_model_loaded:
                        try:
                            self._on_model_loaded(model)
                        except Exception as e:
                            logger.error(f"模型加载回调执行失败: {e}")
                else:
                    stderr_text = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
                    logger.warning(f"模型加载失败: {model}，错误: {stderr_text[:200]}")
                    
            except subprocess.TimeoutExpired:
                logger.warning(f"模型加载超时: {model}")
            except Exception as e:
                logger.error(f"加载模型时出错: {model}，{e}")
        
        self.set_status(OllamaStatus.RUNNING)
        logger.info("所有模型加载任务完成")
    
    async def start_async(self, timeout: int = 60) -> bool:
        """
        异步启动 Ollama 引擎。
        
        参数:
            timeout: 启动超时时间（秒）
            
        返回:
            bool: 启动成功返回 True
        """
        return await asyncio.get_event_loop().run_in_executor(
            None, self.start, timeout
        )
    
    async def stop_async(self, timeout: int = 10) -> bool:
        """
        异步停止 Ollama 引擎。
        
        参数:
            timeout: 停止超时时间（秒）
            
        返回:
            bool: 停止成功返回 True
        """
        return await asyncio.get_event_loop().run_in_executor(
            None, self.stop, timeout
        )
    
    def get_status_info(self, include_models: bool = False) -> Dict[str, Any]:
        """
        获取详细状态信息。
        
        无论 Ollama 是否由本管理器启动，都会检测 HTTP 服务是否可用；
        若外部已启动 Ollama（如用户手动或图片解析在用），也会正确报告 service_available=True。
        
        参数:
            include_models: 是否包含已加载的模型列表（避免额外 HTTP 调用）
        
        返回:
            dict: 包含完整状态信息的字典
        """
        with self._status_lock:
            service_available = False
            loaded_models: List[Dict[str, Any]] = []
            port_in_use = self.is_port_in_use()

            if self.is_running:
                if include_models:
                    import httpx
                    try:
                        response = httpx.get(
                            f"http://{self.host}:{self.port}/api/tags",
                            timeout=2.0,
                        )
                        if response.status_code == 200:
                            data = response.json()
                            loaded_models = data.get("models", [])
                            service_available = True
                    except Exception as e:
                        logger.debug(f"Ollama 服务不可用: {e}")
                    if not service_available and port_in_use:
                        service_available = True
                else:
                    if port_in_use:
                        service_available = True
            else:
                # Ollama 可能由用户或外部进程启动，仅根据 is_running 会误报为“未连接”
                # 通过实际 HTTP 探测，与前端显示一致
                if self.check_service_available():
                    service_available = True
                    if include_models:
                        import httpx
                        try:
                            response = httpx.get(
                                f"http://{self.host}:{self.port}/api/tags",
                                timeout=2.0,
                            )
                            if response.status_code == 200:
                                data = response.json()
                                loaded_models = data.get("models", [])

                        except Exception as e:
                            logger.debug(f"获取 Ollama 模型列表: {e}")

            # 对外显示：只要 HTTP 可用就视为 running，便于前端显示“已连接”
            status_value = self._status.value
            if service_available and status_value == OllamaStatus.STOPPED.value:
                status_value = OllamaStatus.RUNNING.value

            return {
                "status": status_value,
                "is_running": self.is_running,
                "host": self.host,
                "port": self.port,
                "uptime": self.uptime,
                "restart_count": self._restart_count,
                "models": self.models,
                "auto_restart": self.auto_restart,
                "process_pid": self._process.pid if self._process else None,
                "error": self._error_message,
                "port_in_use": port_in_use,
                "service_available": service_available,
                "loaded_models": loaded_models,
            }
    
    def get_loaded_models(self) -> List[Dict[str, Any]]:
        """
        获取已加载的模型列表。
        
        返回:
            list: 模型列表
        """
        if not self.check_service_available():
            return []
        
        import httpx
        
        try:
            response = httpx.get(
                f"http://{self.host}:{self.port}/api/tags",
                timeout=5.0,
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("models", [])
        except Exception as e:
            logger.error(f"获取模型列表失败: {e}")
        
        return []
    
    def __enter__(self) -> "OllamaManager":
        """上下文管理器入口。"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器退出。"""
        self.stop()
    
    def __del__(self) -> None:
        """析构函数，确保进程被正确停止。"""
        try:
            self.stop()
        except Exception:
            pass


# 全局单例
_ollama_manager: Optional[OllamaManager] = None


def get_ollama_manager(
    ollama_path: Optional[str] = None,
    host: str = "localhost",
    port: int = 11434,
    models: Optional[List[str]] = None,
    auto_restart: bool = True,
) -> OllamaManager:
    """
    获取 OllamaManager 单例实例。
    
    参数:
        ollama_path: Ollama 可执行文件路径
        host: 服务监听地址
        port: 服务监听端口
        models: 需要自动加载的模型列表
        auto_restart: 是否启用自动重启
        
    返回:
        OllamaManager: 单例实例
    """
    global _ollama_manager
    if _ollama_manager is None:
        _ollama_manager = OllamaManager(
            ollama_path=ollama_path,
            host=host,
            port=port,
            models=models,
            auto_restart=auto_restart,
        )
    return _ollama_manager


def shutdown_ollama_manager() -> None:
    """关闭 OllamaManager 全局实例。"""
    global _ollama_manager
    if _ollama_manager:
        _ollama_manager.stop()
        _ollama_manager = None
