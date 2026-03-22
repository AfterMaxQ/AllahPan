"""
Cloudflare Tunnel API 模块。

提供 Cloudflare Tunnel 的管理接口，包括：
- 隧道启动/停止/重启
- 状态查询
- 配置管理

作者: AllahPan团队
创建日期: 2026-03-20
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.v1.dependencies import get_current_user, AuthUser

logger = logging.getLogger(__name__)

router = APIRouter()

_tunnel_manager_instance = None


def set_tunnel_manager_instance(manager) -> None:
    """设置 Tunnel 管理器实例。"""
    global _tunnel_manager_instance
    _tunnel_manager_instance = manager


def get_tunnel_manager():
    """获取 Tunnel 管理器实例。"""
    global _tunnel_manager_instance
    if _tunnel_manager_instance is None:
        from app.services.tunnel_manager import get_tunnel_manager as _get_manager
        _tunnel_manager_instance = _get_manager()
    return _tunnel_manager_instance


class TunnelStatusResponse(BaseModel):
    """Tunnel 状态响应模型。"""
    status: str
    is_running: bool
    uptime: Optional[float] = None
    reconnect_count: int = 0
    domain: Optional[str] = None
    connection_url: Optional[str] = None
    tunnel_id: Optional[str] = None
    token_configured: bool
    auto_reconnect: bool
    process_pid: Optional[int] = None
    error: Optional[str] = None


class TunnelConnectionResponse(BaseModel):
    """Tunnel 连接信息响应模型。"""
    domain: Optional[str] = None
    url: Optional[str] = None
    status: str
    uptime: Optional[float] = None


class TunnelConfigRequest(BaseModel):
    """Tunnel 配置请求模型。"""
    token: str
    domain: Optional[str] = None


class TunnelConfigResponse(BaseModel):
    """Tunnel 配置响应模型。"""
    success: bool
    message: str
    domain: Optional[str] = None


class TunnelStartResponse(BaseModel):
    """Tunnel 启动响应模型。"""
    success: bool
    message: str
    connection_info: Optional[TunnelConnectionResponse] = None


class TunnelStopResponse(BaseModel):
    """Tunnel 停止响应模型。"""
    success: bool
    message: str


@router.get("/status", response_model=TunnelStatusResponse)
def get_tunnel_status(
    current_user: AuthUser = Depends(get_current_user),
):
    """
    获取 Tunnel 状态。
    
    返回当前 Tunnel 的运行状态、连接信息和配置状态。
    
    参数:
        current_user: 当前认证用户
    
    返回:
        TunnelStatusResponse: Tunnel 状态信息
    """
    logger.debug(f"查询 Tunnel 状态，用户: {current_user.username}")
    
    manager = get_tunnel_manager()
    status_info = manager.get_status_info()
    
    logger.info(f"Tunnel 状态: {status_info['status']}")
    return TunnelStatusResponse(**status_info)


@router.get("/connection", response_model=TunnelConnectionResponse)
def get_connection_info(
    current_user: AuthUser = Depends(get_current_user),
):
    """
    获取 Tunnel 连接信息。
    
    返回当前的连接 URL、域名和运行时间。
    
    参数:
        current_user: 当前认证用户
    
    返回:
        TunnelConnectionResponse: 连接信息
    """
    logger.debug(f"查询 Tunnel 连接信息，用户: {current_user.username}")
    
    manager = get_tunnel_manager()
    connection_info = manager.get_connection_info()
    
    return TunnelConnectionResponse(**connection_info)


@router.post("/start", response_model=TunnelStartResponse)
def start_tunnel(
    current_user: AuthUser = Depends(get_current_user),
):
    """
    启动 Tunnel。
    
    使用已配置的 Token 启动 Cloudflare Tunnel。
    如果 Token 未配置，会返回错误。
    
    参数:
        current_user: 当前认证用户
    
    返回:
        TunnelStartResponse: 启动结果
    """
    logger.info(f"用户请求启动 Tunnel: {current_user.username}")
    
    manager = get_tunnel_manager()
    
    if not manager.tunnel_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tunnel Token 未配置，请先配置 Token"
        )
    
    success = manager.start(timeout=30)
    
    if success:
        connection_info = manager.get_connection_info()
        logger.info(f"Tunnel 启动成功")
        return TunnelStartResponse(
            success=True,
            message="Tunnel 启动成功",
            connection_info=TunnelConnectionResponse(**connection_info)
        )
    else:
        error_msg = manager.error_message or "启动失败"
        logger.error(f"Tunnel 启动失败: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tunnel 启动失败: {error_msg}"
        )


@router.post("/stop", response_model=TunnelStopResponse)
def stop_tunnel(
    current_user: AuthUser = Depends(get_current_user),
):
    """
    停止 Tunnel。
    
    优雅地停止 Cloudflare Tunnel 连接。
    
    参数:
        current_user: 当前认证用户
    
    返回:
        TunnelStopResponse: 停止结果
    """
    logger.info(f"用户请求停止 Tunnel: {current_user.username}")
    
    manager = get_tunnel_manager()
    success = manager.stop(timeout=10)
    
    if success:
        logger.info("Tunnel 停止成功")
        return TunnelStopResponse(
            success=True,
            message="Tunnel 已停止"
        )
    else:
        logger.error("Tunnel 停止失败")
        return TunnelStopResponse(
            success=False,
            message="Tunnel 停止失败"
        )


@router.post("/restart", response_model=TunnelStartResponse)
def restart_tunnel(
    current_user: AuthUser = Depends(get_current_user),
):
    """
    重启 Tunnel。
    
    停止并重新启动 Cloudflare Tunnel。
    
    参数:
        current_user: 当前认证用户
    
    返回:
        TunnelStartResponse: 重启结果
    """
    logger.info(f"用户请求重启 Tunnel: {current_user.username}")
    
    manager = get_tunnel_manager()
    
    if not manager.tunnel_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tunnel Token 未配置"
        )
    
    success = manager.restart(timeout=30)
    
    if success:
        connection_info = manager.get_connection_info()
        logger.info("Tunnel 重启成功")
        return TunnelStartResponse(
            success=True,
            message="Tunnel 重启成功",
            connection_info=TunnelConnectionResponse(**connection_info)
        )
    else:
        error_msg = manager.error_message or "重启失败"
        logger.error(f"Tunnel 重启失败: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tunnel 重启失败: {error_msg}"
        )


@router.post("/config", response_model=TunnelConfigResponse)
def configure_tunnel(
    config: TunnelConfigRequest,
    current_user: AuthUser = Depends(get_current_user),
):
    """
    配置 Tunnel。
    
    保存 Tunnel Token 和域名配置。
    
    参数:
        config: 配置信息
        current_user: 当前认证用户
    
    返回:
        TunnelConfigResponse: 配置结果
    """
    logger.info(f"用户配置 Tunnel: {current_user.username}")
    
    manager = get_tunnel_manager()
    
    success = manager.configure(
        token=config.token,
        domain=config.domain
    )
    
    if success:
        logger.info(f"Tunnel 配置成功，域名: {config.domain or '未指定'}")
        return TunnelConfigResponse(
            success=True,
            message="Tunnel 配置成功",
            domain=config.domain
        )
    else:
        logger.error("Tunnel 配置失败")
        return TunnelConfigResponse(
            success=False,
            message="Tunnel 配置失败"
        )


@router.delete("/config", response_model=TunnelConfigResponse)
def clear_tunnel_config(
    current_user: AuthUser = Depends(get_current_user),
):
    """
    清除 Tunnel 配置。
    
    删除保存的 Token 和域名配置。
    
    参数:
        current_user: 当前认证用户
    
    返回:
        TunnelConfigResponse: 清除结果
    """
    logger.info(f"用户清除 Tunnel 配置: {current_user.username}")
    
    manager = get_tunnel_manager()
    
    # 停止 Tunnel（如果正在运行）
    if manager.is_running:
        manager.stop()
    
    # 清除配置
    try:
        from app.services.tunnel_manager import _tunnel_config_file
        config_file = _tunnel_config_file()
        if config_file.exists():
            config_file.unlink()
        logger.info("Tunnel 配置已清除")
        return TunnelConfigResponse(
            success=True,
            message="配置已清除"
        )
    except Exception as e:
        logger.error(f"清除配置失败: {e}")
        return TunnelConfigResponse(
            success=False,
            message=f"清除配置失败: {str(e)}"
        )
