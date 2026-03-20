"""
用户认证API模块。

本模块提供用户注册、登录和身份验证相关的RESTful API接口。
使用bcrypt进行密码加密存储，支持JWT令牌认证机制。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-19
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.api.v1.dependencies import (
    get_user_repo,
    verify_password,
    get_password_hash,
    get_current_user,
    create_access_token,
    AuthUser,
)
from app.database.repositories.user_repository import UserRepository
from app.models.user import User

import logging

logger = logging.getLogger(__name__)


router = APIRouter()


class RegisterRequest(BaseModel):
    """
    用户注册请求模型。
    
    属性:
        username: 用户名，必须唯一
        password: 密码，将进行bcrypt加密存储
        email: 用户邮箱，用于账户验证和找回密码
    """
    username: str
    password: str
    email: EmailStr


class LoginRequest(BaseModel):
    """
    用户登录请求模型。
    
    属性:
        username: 用户名
        password: 密码
    """
    username: str
    password: str


class TokenResponse(BaseModel):
    """
    认证令牌响应模型。
    
    属性:
        access_token: 访问令牌（当前实现为用户名）
        token_type: 令牌类型，默认为bearer
        user: 认证用户信息
    """
    access_token: str
    token_type: str = "bearer"
    user: AuthUser


class UserResponse(BaseModel):
    """
    用户信息响应模型。
    
    属性:
        id: 用户唯一标识符（UUID）
        username: 用户名
        email: 用户邮箱
    """
    id: str
    username: str
    email: str


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, user_repo: UserRepository = Depends(get_user_repo)):
    """
    用户注册接口。
    
    该接口接收用户注册信息，验证用户名唯一性后创建新用户。
    密码会使用bcrypt算法进行加密存储，确保安全。
    
    参数:
        request: 注册请求，包含用户名、密码和邮箱
        user_repo: 用户仓库依赖，提供数据库操作
    
    返回:
        UserResponse: 创建的用户信息（不含密码）
    
    异常:
        HTTPException: 当用户名已存在时抛出400错误
    """
    logger.info(f"用户注册请求，用户名: {request.username}")
    if user_repo.username_exists(request.username):
        logger.warning(f"注册失败，用户名已存在: {request.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )
    user = User(
        username=request.username,
        password=get_password_hash(request.password),
        email=request.email,
    )
    created_user = user_repo.create_user(user)
    logger.info(f"用户注册成功，用户名: {created_user.username}")
    return UserResponse(
        id=created_user.id,
        username=created_user.username,
        email=created_user.email,
    )


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, user_repo: UserRepository = Depends(get_user_repo)):
    """
    用户登录接口。
    
    该接口验证用户凭据，成功后返回JWT访问令牌。
    使用bcrypt验证密码哈希值，确保安全性。
    令牌包含用户ID和用户名，24小时有效。
    
    参数:
        request: 登录请求，包含用户名和密码
        user_repo: 用户仓库依赖，提供数据库操作
    
    返回:
        TokenResponse: 包含JWT令牌和用户信息的响应对象
    
    异常:
        HTTPException: 当用户名不存在或密码错误时抛出401错误
    """
    logger.info(f"用户登录请求，用户名: {request.username}")
    user = user_repo.get_user_by_username(request.username)
    if user is None:
        logger.warning(f"登录失败，用户不存在: {request.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if not verify_password(request.password, user.password):
        logger.warning(f"登录失败，密码错误，用户名: {request.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    access_token = create_access_token(
        data={"user_id": user.id, "username": user.username}
    )
    logger.info(f"用户登录成功，用户名: {request.username}")
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=AuthUser(
            id=user.id,
            username=user.username,
            email=user.email,
        ),
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: AuthUser = Depends(get_current_user)):
    """
    获取当前用户信息接口。
    
    该接口返回当前已认证用户的详细信息，用于显示用户个人资料。
    
    参数:
        current_user: 当前认证用户（通过依赖注入自动获取）
    
    返回:
        UserResponse: 包含用户ID、用户名和邮箱的响应对象
    """
    logger.debug(f"获取当前用户信息，用户名: {current_user.username}")
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
    )
