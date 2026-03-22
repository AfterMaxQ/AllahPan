"""
Cloudflare Tunnel 管理器模块。

本模块负责管理 Cloudflare Tunnel（cloudflared）的进程生命周期，包括：
- 隧道连接启动/停止/重启
- Token 配置和管理
- 域名绑定管理
- 状态监控和连接信息
- 自动重连机制

适用于一体化打包场景，提供远程访问功能的自动化管理。

作者: AllahPan团队
创建日期: 2026-03-20
"""

import asyncio
import json
import logging
import os
import platform
import queue
import re
import socket
import subprocess
import sys
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

from app.user_dirs import get_allahpan_user_root

logger = logging.getLogger(__name__)


def _tunnel_config_file() -> Path:
    return get_allahpan_user_root() / "tunnel_config.json"


class TunnelStatus(Enum):
    """Tunnel 状态枚举。"""
    STOPPED = "stopped"           # 已停止
    STARTING = "starting"          # 正在启动
    RUNNING = "running"           # 运行中
    ERROR = "error"               # 错误状态
    RECONNECTING = "reconnecting" # 正在重连
    UNKNOWN = "unknown"           # 未知状态


class TunnelManager:
    """
    Cloudflare Tunnel 管理器类。
    
    负责 cloudflared 进程的完整生命周期管理，支持：
    - 隧道启动/停止/重启
    - Token 配置和验证
    - 域名信息获取
    - 状态监控和事件回调
    - 自动重连机制
    
    属性:
        cloudflared_path: cloudflared 可执行文件路径
        tunnel_token: Cloudflare Tunnel Token
        domain: 绑定的域名
        auto_reconnect: 是否启用自动重连
        reconnect_delay: 重连延迟时间（秒）
    """
    
    DEFAULT_CLOUDFLARED_PORT = 7844
    DEFAULT_METRICS_PORT = 9080
    
    def __init__(
        self,
        cloudflared_path: Optional[str] = None,
        tunnel_token: Optional[str] = None,
        domain: Optional[str] = None,
        auto_reconnect: bool = True,
        reconnect_delay: int = 10,
        reconnect_max_attempts: int = 5,
    ):
        """
        初始化 Tunnel 管理器。
        
        参数:
            cloudflared_path: cloudflared 可执行文件路径，默认自动检测
            tunnel_token: Cloudflare Tunnel Token
            domain: 绑定的域名
            auto_reconnect: 是否启用自动重连
            reconnect_delay: 重连延迟时间（秒）
            reconnect_max_attempts: 最大重连尝试次数
        """
        self.cloudflared_path = cloudflared_path or self._detect_cloudflared_path()
        self.tunnel_token = tunnel_token or self._load_saved_token()
        self.domain = domain or self._load_saved_domain()
        self.auto_reconnect = auto_reconnect
        self.reconnect_delay = reconnect_delay
        self.reconnect_max_attempts = reconnect_max_attempts
        
        # 内部状态
        self._process: Optional[subprocess.Popen] = None
        self._status = TunnelStatus.STOPPED
        self._status_lock = threading.RLock()
        self._start_time: Optional[float] = None
        self._reconnect_count = 0
        self._error_message: Optional[str] = None
        self._connection_info: Dict[str, Any] = {}
        self._shutdown_event = threading.Event()
        self._watchdog_thread: Optional[threading.Thread] = None
        
        # 事件回调
        self._on_status_change: Optional[Callable[[TunnelStatus, Optional[str]], None]] = None
        self._on_connected: Optional[Callable[[Dict], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None
        
        logger.info(
            f"TunnelManager 初始化完成: "
            f"路径={self.cloudflared_path}, "
            f"Token={'已配置' if self.tunnel_token else '未配置'}, "
            f"域名={self.domain or '未绑定'}, "
            f"自动重连={auto_reconnect}"
        )
    
    def _detect_cloudflared_path(self) -> str:
        """
        自动检测 cloudflared 可执行文件路径。
        
        检测顺序：
        1. 环境变量 CLOUDFLARED_PATH
        2. 系统 PATH 中的 cloudflared 命令
        3. 常见安装路径（macOS/Linux/Windows）
        
        返回:
            str: cloudflared 可执行文件路径
        """
        # 优先检查环境变量
        env_path = os.environ.get("CLOUDFLARED_PATH")
        if env_path and Path(env_path).exists():
            logger.info(f"从环境变量检测到 cloudflared 路径: {env_path}")
            return env_path
        
        system = platform.system()
        
        if system == "Darwin":  # macOS
            common_paths = [
                "/usr/local/bin/cloudflared",
                "/opt/homebrew/bin/cloudflared",
                str(Path.home() / ".cloudflared" / "cloudflared"),
            ]
        elif system == "Linux":
            common_paths = [
                "/usr/local/bin/cloudflared",
                "/usr/bin/cloudflared",
                str(Path.home() / ".cloudflared" / "cloudflared"),
            ]
        elif system == "Windows":
            common_paths = [
                str(Path(os.environ.get("LOCALAPPDATA", "")) / "Cloudflared" / "cloudflared.exe"),
                str(Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Cloudflared" / "cloudflared.exe"),
                "cloudflared.exe",  # PATH 中
            ]
        else:
            common_paths = ["cloudflared"]  # 假设在 PATH 中
        
        for path in common_paths:
            if Path(path).exists():
                logger.info(f"自动检测到 cloudflared 路径: {path}")
                return path
        
        # 尝试从 PATH 获取
        try:
            result = subprocess.run(
                ["which", "cloudflared"] if system != "Windows" else ["where", "cloudflared"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                found_path = result.stdout.strip().split("\n")[0]
                logger.info(f"从 PATH 检测到 cloudflared: {found_path}")
                return found_path
        except Exception as e:
            logger.debug(f"从 PATH 检测 cloudflared 失败: {e}")
        
        logger.warning("未检测到 cloudflared，使用默认路径 'cloudflared'（需要确保在 PATH 中）")
        return "cloudflared"
    
    def _load_saved_config(self) -> Dict[str, Any]:
        """从配置文件加载保存的设置。"""
        if _tunnel_config_file().exists():
            try:
                with open(_tunnel_config_file(), "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载 Tunnel 配置文件失败: {e}")
        return {}
    
    def _load_saved_token(self) -> Optional[str]:
        """从配置文件加载保存的 Token。"""
        config = self._load_saved_config()
        return config.get("token")
    
    def _load_saved_domain(self) -> Optional[str]:
        """从配置文件加载保存的域名。"""
        config = self._load_saved_config()
        return config.get("domain")
    
    def save_config(self, token: Optional[str] = None, domain: Optional[str] = None) -> bool:
        """
        保存配置到文件。
        
        参数:
            token: Tunnel Token
            domain: 域名
            
        返回:
            bool: 保存成功返回 True
        """
        try:
            _tunnel_config_file().parent.mkdir(parents=True, exist_ok=True)
            config = {
                "token": token or self.tunnel_token,
                "domain": domain or self.domain,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(_tunnel_config_file(), "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info("Tunnel 配置已保存")
            return True
        except Exception as e:
            logger.error(f"保存 Tunnel 配置失败: {e}")
            return False
    
    @property
    def status(self) -> TunnelStatus:
        """获取当前状态。"""
        with self._status_lock:
            return self._status
    
    @property
    def is_running(self) -> bool:
        """检查 Tunnel 是否正在运行。"""
        return self.status == TunnelStatus.RUNNING
    
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
    
    @property
    def connection_url(self) -> Optional[str]:
        """获取连接 URL。"""
        return self._connection_info.get("url")
    
    @property
    def connection_domain(self) -> Optional[str]:
        """获取连接域名。"""
        return self._connection_info.get("domain") or self.domain
    
    def set_status(self, status: TunnelStatus, error: Optional[str] = None) -> None:
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
            
            if status == TunnelStatus.ERROR:
                logger.error(f"Tunnel 状态变为 ERROR: {error}")
            elif old_status != status:
                logger.info(f"Tunnel 状态变化: {old_status.value} -> {status.value}")
        
        # 触发回调
        if self._on_status_change:
            try:
                self._on_status_change(status, error)
            except Exception as e:
                logger.error(f"状态变化回调执行失败: {e}")
    
    def set_on_status_change(self, callback: Callable[[TunnelStatus, Optional[str]], None]) -> None:
        """设置状态变化回调。"""
        self._on_status_change = callback
    
    def set_on_connected(self, callback: Callable[[Dict], None]) -> None:
        """设置连接成功回调。"""
        self._on_connected = callback
    
    def set_on_error(self, callback: Callable[[str], None]) -> None:
        """设置错误回调。"""
        self._on_error = callback
    
    def configure(self, token: str, domain: Optional[str] = None) -> bool:
        """
        配置 Tunnel。
        
        参数:
            token: Cloudflare Tunnel Token
            domain: 绑定的域名（可选）
            
        返回:
            bool: 配置成功返回 True
        """
        if not token:
            logger.error("Token 不能为空")
            return False
        
        self.tunnel_token = token
        if domain:
            self.domain = domain
        
        # 保存配置
        return self.save_config(token, domain)
    
    def start(self, timeout: int = 30) -> bool:
        """
        启动 Tunnel。
        
        参数:
            timeout: 启动超时时间（秒）
            
        返回:
            bool: 启动成功返回 True
        """
        if self.is_running:
            logger.info("Tunnel 已在运行中，无需重复启动")
            return True
        
        if not self.tunnel_token:
            self.set_status(TunnelStatus.ERROR, "未配置 Tunnel Token")
            return False
        
        self.set_status(TunnelStatus.STARTING)
        self._shutdown_event.clear()
        self._reconnect_count = 0
        
        try:
            logger.info(f"正在启动 Cloudflare Tunnel...")
            
            # 构建命令
            cmd = [
                self.cloudflared_path,
                "tunnel",
                "--no-autoupdate",
                "run",
                "--token", self.tunnel_token,
            ]
            
            # 添加 URL 参数指向本地服务
            # 注意：cloudflared 直接使用 token 运行时会从环境变量或配置文件读取服务 URL
            
            # 设置环境变量
            env = os.environ.copy()
            env["TUNNEL_HOST_IPV6"] = "false"
            
            # 启动进程
            self._process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            
            # 非阻塞读取 stdout：用独立线程写入队列，主循环从队列取
            output_queue: queue.Queue = queue.Queue()
            def read_stdout():
                try:
                    if self._process and self._process.stdout:
                        for line in iter(self._process.stdout.readline, ""):
                            if self._shutdown_event.is_set():
                                break
                            output_queue.put(line)
                except Exception as e:
                    logger.debug(f"Tunnel stdout 读取结束: {e}")
                output_queue.put(None)

            reader = threading.Thread(target=read_stdout, daemon=True, name="TunnelStdoutReader")
            reader.start()

            start_time = time.time()
            connected = False
            while time.time() - start_time < timeout:
                if self._shutdown_event.is_set():
                    break
                if self._process.poll() is not None:
                    stderr = self._process.stderr.read() if self._process.stderr else ""
                    error_msg = f"Tunnel 进程异常退出: {stderr[:200]}"
                    logger.error(error_msg)
                    self.set_status(TunnelStatus.ERROR, error_msg)
                    return False
                try:
                    line = output_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                if line is None:
                    break
                logger.debug(f"Tunnel 输出: {line.strip()}")
                connection_info = self._parse_output(line)
                if connection_info:
                    self._connection_info = connection_info
                    connected = True
                    break
            
            if connected or self._process.poll() is None:
                logger.info("Cloudflare Tunnel 启动成功")
                self._start_time = time.time()
                self.set_status(TunnelStatus.RUNNING)
                self._start_watchdog()
                
                # 触发连接回调
                if self._on_connected:
                    try:
                        self._on_connected(self._connection_info)
                    except Exception as e:
                        logger.error(f"连接回调执行失败: {e}")
                
                return True
            else:
                error_msg = "Tunnel 启动超时"
                logger.error(error_msg)
                self.set_status(TunnelStatus.ERROR, error_msg)
                return False
                
        except FileNotFoundError:
            error_msg = f"cloudflared 可执行文件未找到: {self.cloudflared_path}"
            logger.error(error_msg)
            self.set_status(TunnelStatus.ERROR, error_msg)
            return False
        except PermissionError:
            error_msg = f"没有权限启动 cloudflared: {self.cloudflared_path}"
            logger.error(error_msg)
            self.set_status(TunnelStatus.ERROR, error_msg)
            return False
        except Exception as e:
            error_msg = f"启动 Tunnel 失败: {str(e)}"
            logger.error(error_msg)
            self.set_status(TunnelStatus.ERROR, error_msg)
            return False
    
    def _parse_output(self, line: str) -> Optional[Dict[str, Any]]:
        """
        解析 cloudflared 输出，提取连接信息。
        
        参数:
            line: 输出行
            
        返回:
            dict: 连接信息字典
        """
        # 匹配类似 "Your tunnel <uuid> is running on <url>" 的格式
        tunnel_match = re.search(r"Your tunnel (\S+) is running on (\S+)", line)
        if tunnel_match:
            return {
                "tunnel_id": tunnel_match.group(1),
                "url": tunnel_match.group(2),
                "domain": self.domain,
            }
        
        # 匹配类似 "Connected to https://your-domain.example.com" 的格式
        connected_match = re.search(r"Connected to (https?://\S+)", line)
        if connected_match:
            url = connected_match.group(1)
            return {
                "url": url,
                "domain": url.replace("https://", "").replace("http://", ""),
            }
        
        # 匹配类似 "registered at https://tunnel.cloudflare.com with id <uuid>" 的格式
        registered_match = re.search(r"registered at \S+ with id (\S+)", line)
        if registered_match:
            return {
                "tunnel_id": registered_match.group(1),
                "domain": self.domain,
            }
        
        return None
    
    def stop(self, timeout: int = 10) -> bool:
        """
        停止 Tunnel。
        
        参数:
            timeout: 停止超时时间（秒）
            
        返回:
            bool: 停止成功返回 True
        """
        logger.info("正在停止 Cloudflare Tunnel...")
        self._shutdown_event.set()
        self._stop_watchdog()
        
        if self._process is None:
            logger.info("Tunnel 进程不存在，已停止")
            self.set_status(TunnelStatus.STOPPED)
            return True
        
        try:
            system = platform.system()
            
            if system == "Windows":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self._process.pid)],
                    capture_output=True,
                    timeout=timeout,
                )
            else:
                self._process.terminate()
                try:
                    self._process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait()
            
            logger.info("Cloudflare Tunnel 已停止")
            self._process = None
            self._start_time = None
            self._connection_info = {}
            self.set_status(TunnelStatus.STOPPED)
            return True
            
        except Exception as e:
            logger.error(f"停止 Tunnel 失败: {e}")
            try:
                if self._process:
                    self._process.kill()
            except Exception:
                pass
            self._process = None
            self.set_status(TunnelStatus.STOPPED)
            return False
    
    def restart(self, timeout: int = 30) -> bool:
        """
        重启 Tunnel。
        
        参数:
            timeout: 启动超时时间（秒）
            
        返回:
            bool: 重启成功返回 True
        """
        logger.info("正在重启 Cloudflare Tunnel...")
        self.stop()
        time.sleep(2)
        return self.start(timeout)
    
    def _start_watchdog(self) -> None:
        """启动看门狗线程。"""
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name="TunnelWatchdog",
        )
        self._watchdog_thread.start()
        logger.debug("Tunnel 看门狗线程已启动")

    def _stop_watchdog(self) -> None:
        """停止看门狗线程并等待其结束。"""
        thread = self._watchdog_thread
        self._watchdog_thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=8)
            if thread.is_alive():
                logger.warning("Tunnel 看门狗线程未在超时内结束")
    
    def _watchdog_loop(self) -> None:
        """看门狗循环，监控 Tunnel 状态。"""
        check_interval = 5
        
        while not self._shutdown_event.is_set():
            try:
                if self._shutdown_event.wait(timeout=check_interval):
                    break
                
                # 检查进程状态
                if self._process is not None:
                    poll_result = self._process.poll()
                    if poll_result is not None:
                        stderr = self._process.stderr.read() if self._process.stderr else ""
                        error_msg = f"Tunnel 进程异常退出，退出码: {poll_result}"
                        if stderr:
                            error_msg += f"，错误: {stderr[:100]}"
                        logger.error(error_msg)
                        self._handle_process_exit(error_msg)
                        break
                    
                    # 读取并解析输出：非阻塞从 stdout 读一行（select 在 Windows 上不可用于 pipe）
                    try:
                        import select as _select_module
                        _system = platform.system()
                        if _system != "Windows" and self._process.stdout:
                            if _select_module.select([self._process.stdout], [], [], 0)[0]:
                                line = self._process.stdout.readline()
                                if line:
                                    info = self._parse_output(line)
                                    if info:
                                        self._connection_info.update(info)
                        # Windows: 不在此处读 stdout，避免 kbhit 误用；连接信息已在 start() 中获取
                    except Exception:
                        pass
            
            except Exception as e:
                logger.error(f"Tunnel 看门狗检查失败: {e}")
    
    def _handle_process_exit(self, error_msg: str) -> None:
        """处理进程异常退出。"""
        self.set_status(TunnelStatus.ERROR, error_msg)
        
        if self.auto_reconnect and self._reconnect_count < self.reconnect_max_attempts:
            self._reconnect_count += 1
            self.set_status(TunnelStatus.RECONNECTING)
            logger.info(f"尝试自动重连 Tunnel ({self._reconnect_count}/{self.reconnect_max_attempts})...")
            time.sleep(self.reconnect_delay)
            self.start()
        else:
            logger.error("已达到最大重连次数或自动重连已禁用")
    
    def _is_cloudflared_process_running(self) -> bool:
        """
        检测系统中是否有 cloudflared 进程在运行（可能由本管理器外的进程启动，如桌面端或手动）。
        用于在内部状态为 stopped 时仍能正确报告「运行中」。
        """
        try:
            system = platform.system()
            if system == "Windows":
                out = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq cloudflared.exe", "/NH"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    encoding="utf-8",
                    errors="replace",
                )
                return out.returncode == 0 and "cloudflared.exe" in (out.stdout or "")
            # macOS / Linux：先尝试 pgrep，再回退到 ps
            out = subprocess.run(
                ["pgrep", "-x", "cloudflared"],
                capture_output=True,
                timeout=5,
            )
            if out.returncode == 0:
                return True
            out = subprocess.run(
                ["ps", "-A", "-o", "comm="],
                capture_output=True,
                text=True,
                timeout=5,
                encoding="utf-8",
                errors="replace",
            )
            return "cloudflared" in (out.stdout or "")
        except Exception as e:
            logger.debug(f"检测 cloudflared 进程时出错: {e}")
            return False

    def get_status_info(self) -> Dict[str, Any]:
        """
        获取详细状态信息。
        若本管理器未启动进程但检测到系统中有 cloudflared 在运行（如由桌面端或手动启动），
        则返回 status=running，避免前端误显示为 stopped。
        """
        with self._status_lock:
            info = {
                "status": self._status.value,
                "is_running": self.is_running,
                "uptime": self.uptime,
                "reconnect_count": self._reconnect_count,
                "domain": self.connection_domain,
                "connection_url": self.connection_url,
                "tunnel_id": self._connection_info.get("tunnel_id"),
                "token_configured": bool(self.tunnel_token),
                "auto_reconnect": self.auto_reconnect,
                "process_pid": self._process.pid if self._process else None,
                "error": self._error_message,
            }
        # 未持有锁时检测外部进程，避免 subprocess 阻塞
        if info["status"] == "stopped" and info["token_configured"] and self._is_cloudflared_process_running():
            logger.info("检测到 cloudflared 进程在运行，将状态报告为 running")
            info["status"] = "running"
            info["is_running"] = True
            if not info.get("connection_url") and (self.domain or info.get("domain")):
                d = info.get("domain") or self.domain
                info["connection_url"] = f"https://{d}" if d else None
                info["domain"] = d
        return info
    
    def get_connection_info(self) -> Dict[str, Any]:
        """
        获取连接信息。
        若本管理器未启动进程但检测到系统中有 cloudflared 在运行，则返回 status=running 及基于域名的 url。
        """
        status = self.status.value
        domain = self.connection_domain
        url = self.connection_url
        if status == "stopped" and self.tunnel_token and self._is_cloudflared_process_running():
            status = "running"
            if not url and domain:
                url = f"https://{domain}"
        return {
            "domain": domain,
            "url": url,
            "status": status,
            "uptime": self.uptime,
        }
    
    async def start_async(self, timeout: int = 30) -> bool:
        """
        异步启动 Tunnel。
        
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
        异步停止 Tunnel。
        
        参数:
            timeout: 停止超时时间（秒）
            
        返回:
            bool: 停止成功返回 True
        """
        return await asyncio.get_event_loop().run_in_executor(
            None, self.stop, timeout
        )
    
    def __enter__(self) -> "TunnelManager":
        """上下文管理器入口。"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器退出。"""
        self.stop()
    
    def __del__(self) -> None:
        """析构函数。"""
        try:
            self.stop()
        except Exception:
            pass


# 全局单例
_tunnel_manager: Optional[TunnelManager] = None


def get_tunnel_manager(
    cloudflared_path: Optional[str] = None,
    tunnel_token: Optional[str] = None,
    domain: Optional[str] = None,
    auto_reconnect: bool = True,
) -> TunnelManager:
    """
    获取 TunnelManager 单例实例。
    
    参数:
        cloudflared_path: cloudflared 可执行文件路径
        tunnel_token: Tunnel Token
        domain: 域名
        auto_reconnect: 是否启用自动重连
        
    返回:
        TunnelManager: 单例实例
    """
    global _tunnel_manager
    if _tunnel_manager is None:
        _tunnel_manager = TunnelManager(
            cloudflared_path=cloudflared_path,
            tunnel_token=tunnel_token,
            domain=domain,
            auto_reconnect=auto_reconnect,
        )
    return _tunnel_manager


def shutdown_tunnel_manager() -> None:
    """关闭 TunnelManager 全局实例。"""
    global _tunnel_manager
    if _tunnel_manager:
        _tunnel_manager.stop()
        _tunnel_manager = None
