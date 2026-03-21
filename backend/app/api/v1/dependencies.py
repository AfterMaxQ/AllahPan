"""
FastAPI依赖注入模块。

本模块定义了项目中使用的各种依赖注入函数，包括数据库连接、用户仓库、
密码验证、JWT令牌创建和验证。这些依赖用于简化API路由的代码并提高可测试性。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-19
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
try:
    from jose.jwt import JWTError, jwt
except ImportError:
    from jose import JWTError, jwt
from pydantic import BaseModel

import bcrypt

from app.database.sqlite import SQLite, as_sql_text_param
from app.database.repositories.user_repository import UserRepository
from app.models.user import User
from ollama.ollama_client import OllamaClient

import logging

logger = logging.getLogger(__name__)


security = HTTPBearer()

# JWT 配置
# 从 config 导入，确保与全局配置一致
from app.config import JWT_SECRET_KEY, JWT_ALGORITHM


_db_instance: Optional["SQLite"] = None
_user_repo_instance: Optional["UserRepository"] = None
_ollama_client: Optional["OllamaClient"] = None
_chroma_db_instance: Optional["ChromaDB"] = None
_file_repo_instance: Optional["FileRepository"] = None

if TYPE_CHECKING:
    from app.database.sqlite import SQLite
    from app.database.repositories.user_repository import UserRepository
    from app.database.repositories.file_repository import FileRepository
    from app.database.repositories.vector_repository import VectorRepository
    from app.database.chroma import ChromaDB
    from ollama.ollama_client import OllamaClient


class TokenData(BaseModel):
    """JWT令牌数据模型，包含用户身份信息。"""
    user_id: str
    username: str
    exp: Optional[datetime] = None


class AuthUser(BaseModel):
    """
    认证用户信息模型。
    
    该模型用于在API响应中返回用户的基本信息，
    不包含敏感的密码字段。
    
    属性:
        id: 用户唯一标识符（UUID）
        username: 用户名
        email: 用户邮箱
    """
    id: str
    username: str
    email: str


def create_access_token(data: dict) -> str:
    """
    创建JWT访问令牌（无过期时间，长期有效）。
    
    参数:
        data: 包含用户信息的字典，至少包含 user_id 和 username
    
    返回:
        str: 编码后的JWT令牌字符串
    """
    to_encode = data.copy()
    if "user_id" in to_encode and to_encode["user_id"] is not None:
        to_encode["user_id"] = as_sql_text_param(to_encode["user_id"])
    encoded_jwt: str = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_access_token(token: str) -> TokenData:
    """
    验证JWT令牌并提取用户数据（不校验过期时间）。
    
    参数:
        token: JWT令牌字符串
    
    返回:
        TokenData: 令牌中包含的用户数据
    
    异常:
        HTTPException: 当令牌无效时抛出401错误
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload: dict = jwt.decode(
            token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM],
            options={"verify_exp": False},
        )
        user_id = as_sql_text_param(payload.get("user_id", ""))
        username = as_sql_text_param(payload.get("username", ""))
        if not user_id or not username:
            logger.warning(f"JWT令牌缺少必需字段: user_id={user_id}, username={username}")
            raise credentials_exception
        return TokenData(user_id=user_id, username=username)
    except JWTError as e:
        logger.warning(f"JWT验证失败: {e}")
        raise credentials_exception


def get_db() -> SQLite:
    """
    获取SQLite数据库实例的依赖函数。
    
    该函数实现单例模式，确保整个应用生命周期内只创建一个数据库连接。
    首次调用时创建新的连接，后续调用返回已存在的实例。
    
    返回:
        SQLite: SQLite数据库连接实例
    """
    global _db_instance
    if _db_instance is None:
        from app.config import get_db_path
        _db_instance = SQLite(db_path=str(get_db_path()))
    return _db_instance


def get_user_repo() -> UserRepository:
    """
    获取用户仓库实例的依赖函数。
    
    该函数实现单例模式，确保整个应用生命周期内只创建一个用户仓库。
    自动注入数据库连接实例。
    
    返回:
        UserRepository: 用户仓库实例
    """
    global _user_repo_instance
    if _user_repo_instance is None:
        _user_repo_instance = UserRepository(sqlite_db=get_db())
    return _user_repo_instance


def get_password_hash(password: str) -> str:
    """
    对密码进行 bcrypt 加密哈希。
    
    该函数使用 bcrypt 算法对明文密码进行加密，生成安全的哈希值。
    每次调用都会生成不同的哈希值（因为使用随机盐值），确保安全性。
    
    参数:
        password: 明文密码字符串
    
    返回:
        str: bcrypt 加密后的哈希字符串
    """
    logger.debug("开始加密密码")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码与哈希密码是否匹配。
    
    该函数使用 bcrypt 算法比较明文密码和存储的哈希值，
    返回匹配结果。用于用户登录时的密码验证。
    
    参数:
        plain_password: 用户输入的明文密码
        hashed_password: 数据库中存储的哈希密码
    
    返回:
        bool: 密码匹配返回 True，否则返回 False
    """
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """
    获取当前认证用户的依赖函数。
    
    该函数从HTTP请求的Authorization头中提取Bearer令牌，
    验证JWT令牌有效性，然后从数据库查询用户信息。
    用于保护需要认证的API接口。
    
    参数:
        credentials: HTTP授权凭证（通过FastAPI自动解析）
    
    返回:
        User: 当前认证的用户对象
    
    异常:
        HTTPException: 当认证凭证无效时抛出401未授权错误
    """
    logger.debug("开始认证用户")
    token_data = verify_access_token(credentials.credentials)
    user_id = as_sql_text_param(token_data.user_id)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_repo = get_user_repo()
    user = user_repo.get_user_by_id(user_id)
    if user is None:
        logger.warning(f"认证失败，用户不存在: user_id={user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.debug(f"用户认证成功，用户名: {user.username}")
    return user


def get_auth_user(user: User = Depends(get_current_user)) -> AuthUser:
    """
    将User对象转换为AuthUser模型的依赖函数。
    
    该函数用于在API端点中获取格式化的用户信息，
    便于序列化为JSON响应。
    
    参数:
        user: 当前认证用户（通过get_current_user依赖获取）
    
    返回:
        AuthUser: 格式化的认证用户信息对象
    """
    return AuthUser(
        id=user.id,
        username=user.username,
        email=user.email,
    )


def get_ollama() -> OllamaClient:
    """
    获取Ollama客户端实例的依赖函数。
    
    该函数实现单例模式，确保整个应用生命周期内只创建一个Ollama客户端。
    使用异步HTTP客户端，支持高效的AI推理请求。
    
    返回:
        OllamaClient: Ollama客户端实例
    """
    global _ollama_client
    if _ollama_client is None:
        from app.config import OLLAMA_BASE_URL, OLLAMA_EMBEDDING_MODEL, OLLAMA_VISION_MODEL, OLLAMA_TIMEOUT
        _ollama_client = OllamaClient(
            base_url=OLLAMA_BASE_URL,
            embedding_model=OLLAMA_EMBEDDING_MODEL,
            vision_model=OLLAMA_VISION_MODEL,
            timeout=OLLAMA_TIMEOUT,
        )
    return _ollama_client


def get_file_repo() -> "FileRepository":
    """
    获取文件仓库实例的依赖函数。
    
    该函数实现单例模式，确保整个应用生命周期内只创建一个文件仓库实例，
    共享同一个SQLite和ChromaDB连接，避免重复创建数据库连接。
    
    返回:
        FileRepository: 文件仓库实例
    """
    global _file_repo_instance
    if _file_repo_instance is None:
        from app.database.repositories.file_repository import FileRepository
        _file_repo_instance = FileRepository(sqlite_db=get_db(), chroma_db=get_chroma_db())
    return _file_repo_instance


def get_vector_repo() -> "VectorRepository":
    """
    获取向量仓库实例的依赖函数。
    
    该函数实现单例模式，确保整个应用生命周期内只创建一个向量仓库实例，
    共享同一个ChromaDB连接。
    
    返回:
        VectorRepository: 向量仓库实例
    """
    from app.database.repositories.vector_repository import VectorRepository
    return VectorRepository(chroma_db=get_chroma_db())


def get_chroma_db() -> "ChromaDB":
    """
    获取ChromaDB实例的依赖函数。

    该函数实现单例模式，确保整个应用生命周期内只创建一个ChromaDB客户端。

    返回:
        ChromaDB: ChromaDB向量数据库实例
    """
    global _chroma_db_instance
    if _chroma_db_instance is None:
        from app.config import get_chroma_path, OLLAMA_BASE_URL, SIMILARITY_THRESHOLD
        from app.database.chroma import ChromaDB
        _chroma_db_instance = ChromaDB(
            persist_path=str(get_chroma_path()),
            ollama_base_url=OLLAMA_BASE_URL,
            similarity_threshold=SIMILARITY_THRESHOLD,
        )
    return _chroma_db_instance
