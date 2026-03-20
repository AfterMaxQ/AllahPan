"""
用户模型模块。

本模块定义User类，表示AllahPan系统中的用户实体。
用户是系统的主要操作者，可以上传和管理文件。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-19
"""

import uuid
from datetime import datetime
from typing import Optional


class User:
    """
    用户实体类。
    
    该类表示系统中的用户，包含用户的基本信息。
    用户是系统的主要操作者，可以上传和管理文件。
    
    属性:
        id: 用户唯一标识符（UUID字符串）
        username: 用户登录名（必须唯一）
        password: 用户密码（生产环境中应为哈希值）
        email: 用户邮箱地址
        create_time: 用户创建时间戳
    """

    def __init__(
        self,
        username: str,
        password: str,
        email: str,
        id: Optional[str] = None,
        create_time: Optional[str] = None
    ):
        """
        初始化User实例。
        
        参数:
            username: 用户的唯一用户名
            password: 用户的密码
            email: 用户的邮箱地址
            id: 可选的用户ID（UUID字符串，未提供时自动生成）
            create_time: 可选的创建时间戳（未提供时使用当前时间）
        """
        self.id = id or str(uuid.uuid4())
        self.username = username
        self.password = password
        self.email = email
        self.create_time = create_time or datetime.now().isoformat()

    def to_dict(self) -> dict:
        """
        将User实例转换为字典。
        
        返回:
            dict: 包含所有用户属性的字典
        """
        return {
            "id": self.id,
            "username": self.username,
            "password": self.password,
            "email": self.email,
            "create_time": self.create_time
        }

    @staticmethod
    def from_dict(data: dict) -> "User":
        """
        从字典创建User实例。
        
        参数:
            data: 包含用户数据的字典
        
        返回:
            User: 从字典数据创建的User实例
        """
        return User(
            id=data.get("id"),
            username=data["username"],
            password=data["password"],
            email=data["email"],
            create_time=data.get("create_time")
        )
