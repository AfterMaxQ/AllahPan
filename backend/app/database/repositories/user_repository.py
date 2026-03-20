"""
用户仓库模块。

本模块提供UserRepository类，作为用户相关操作的抽象层，
在服务层和SQLite数据库之间提供接口抽象。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-19
"""

from typing import List, Optional

from app.models.user import User
from app.database.sqlite import SQLite

import logging

logger = logging.getLogger(__name__)


class UserRepository:
    """
    用户数据操作仓库类。
    
    该类提供用户相关数据库操作的干净接口，抽象掉直接的SQL查询。
    作为服务层和数据库层之间的中间层，提高代码的可维护性和可测试性。
    
    属性:
        sqlite: 用于用户操作的SQLite数据库实例
    """

    def __init__(self, sqlite_db: Optional[SQLite] = None):
        """
        初始化UserRepository。
        
        参数:
            sqlite_db: 可选的SQLite实例，未提供时创建新实例
        """
        self.sqlite = sqlite_db or SQLite()

    def create_user(self, user: User) -> User:
        """
        在数据库中创建新用户。
        
        参数:
            user: 要创建的User实例
        
        返回:
            User: 创建的User实例，包含分配的ID
        """
        logger.info(f"开始创建用户，用户名: {user.username}")
        user_id = self.sqlite.add_user(user)
        user.id = user_id
        logger.info(f"用户创建成功，用户ID: {user.id}")
        return user

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        根据ID检索用户。
        
        参数:
            user_id: 要检索的用户UUID字符串
        
        返回:
            Optional[User]: 找到的User实例，未找到返回None
        """
        logger.debug(f"根据ID检索用户: {user_id}")
        return self.sqlite.get_user_by_id(user_id)

    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        根据用户名检索用户。
        
        参数:
            username: 要检索的用户名
        
        返回:
            Optional[User]: 找到的User实例，未找到返回None
        """
        logger.debug(f"根据用户名检索用户: {username}")
        return self.sqlite.get_user_by_username(username)

    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        根据邮箱检索用户。
        
        参数:
            email: 要检索的邮箱地址
        
        返回:
            Optional[User]: 找到的User实例，未找到返回None
        """
        logger.debug(f"根据邮箱检索用户: {email}")
        return self.sqlite.get_user_by_email(email)

    def update_user(self, user: User) -> bool:
        """
        更新现有用户信息。
        
        参数:
            user: 包含更新数据的User实例（必须设置id）
        
        返回:
            bool: 更新成功返回True，否则返回False
        """
        logger.info(f"开始更新用户信息，用户ID: {user.id}")
        success = self.sqlite.update_user(user)
        if success:
            logger.info(f"用户信息更新成功，用户ID: {user.id}")
        else:
            logger.warning(f"用户信息更新失败，未找到用户: {user.id}")
        return success

    def delete_user(self, user_id: str) -> bool:
        """
        根据ID删除用户。
        
        参数:
            user_id: 要删除的用户UUID字符串
        
        返回:
            bool: 删除成功返回True，否则返回False
        """
        logger.info(f"开始删除用户，用户ID: {user_id}")
        success = self.sqlite.delete_user(user_id)
        if success:
            logger.info(f"用户删除成功，用户ID: {user_id}")
        else:
            logger.warning(f"用户删除失败，未找到用户: {user_id}")
        return success

    def get_all_users(self) -> List[User]:
        """
        获取所有用户。
        
        返回:
            List[User]: 所有User实例列表
        """
        logger.debug("获取所有用户")
        users = self.sqlite.get_all_users()
        logger.debug(f"共获取 {len(users)} 个用户")
        return users

    def username_exists(self, username: str) -> bool:
        """
        检查用户名是否已被占用。
        
        参数:
            username: 要检查的用户名
        
        返回:
            bool: 用户名存在返回True，否则返回False
        """
        logger.debug(f"检查用户名是否存在: {username}")
        exists = self.sqlite.get_user_by_username(username) is not None
        if exists:
            logger.debug(f"用户名已存在: {username}")
        else:
            logger.debug(f"用户名可用: {username}")
        return exists

    def email_exists(self, email: str) -> bool:
        """
        检查邮箱是否已被注册。
        
        参数:
            email: 要检查的邮箱地址
        
        返回:
            bool: 邮箱存在返回True，否则返回False
        """
        logger.debug(f"检查邮箱是否存在: {email}")
        exists = self.sqlite.get_user_by_email(email) is not None
        if exists:
            logger.debug(f"邮箱已存在: {email}")
        else:
            logger.debug(f"邮箱可用: {email}")
        return exists

    def close(self) -> None:
        """关闭数据库连接。"""
        logger.info("关闭UserRepository数据库连接")
        self.sqlite.close()
