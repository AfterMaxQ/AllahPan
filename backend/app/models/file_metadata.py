"""
文件元数据模型模块。

本模块定义FileMetadata类，表示AllahPan系统中文件的元数据信息。
该类存储文件的描述性信息，但不存储实际文件内容。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-19
"""

import uuid
from datetime import datetime
from typing import Optional


class FileMetadata:
    """
    文件元数据类。
    
    该类存储上传文件的元数据信息，但不存储实际文件内容。
    实际文件存储在本地文件系统中，该模型跟踪文件的元数据。
    
    属性:
        file_id: 文件唯一标识符（UUID字符串）
        filename: 上传文件的原始名称
        filepath: 文件在磁盘上的存储路径
        size: 文件大小（字节）
        filetype: 文件MIME类型（例如: 'image/jpeg'）
        userid: 所属用户ID
        is_ai_parsed: 文件是否已进行AI解析（用于图片）
                      如果为False，AI将自动解析并生成向量
        upload_time: 文件上传时间戳
    """

    def __init__(
        self,
        filename: str,
        filepath: str,
        size: int,
        filetype: str,
        userid: str,
        is_ai_parsed: bool = False,
        file_id: Optional[str] = None,
        upload_time: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """
        初始化FileMetadata实例。
        
        参数:
            filename: 上传文件的原始名称
            filepath: 文件在本地文件系统中的存储路径
            size: 文件大小（字节）
            filetype: 文件MIME类型
            userid: 所属用户的ID（UUID字符串）
            is_ai_parsed: 文件是否已进行AI解析（默认: False）
            file_id: 可选的文件ID（UUID字符串，未提供时自动生成）
            upload_time: 可选的上传时间戳（未提供时使用当前时间）
        """
        self.file_id = file_id or str(uuid.uuid4())
        self.filename = filename
        self.filepath = filepath
        self.size = size
        self.filetype = filetype
        self.userid = userid
        self.is_ai_parsed = is_ai_parsed
        self.upload_time = upload_time or datetime.now().isoformat()
        self.description = description

    def to_dict(self) -> dict:
        """
        将FileMetadata实例转换为字典。
        
        返回:
            dict: 包含所有文件元数据属性的字典
        """
        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "filepath": self.filepath,
            "size": self.size,
            "filetype": self.filetype,
            "userid": self.userid,
            "is_ai_parsed": self.is_ai_parsed,
            "upload_time": self.upload_time,
            "description": self.description,
        }

    @staticmethod
    def from_dict(data: dict) -> "FileMetadata":
        """
        从字典创建FileMetadata实例。
        
        参数:
            data: 包含文件元数据的字典
        
        返回:
            FileMetadata: 从字典数据创建的FileMetadata实例
        """
        file_id = data.get("file_id") or data.get("id")
        raw_parsed = data.get("is_ai_parsed", False)
        is_ai_parsed = bool(raw_parsed) if raw_parsed is not None else False
        return FileMetadata(
            file_id=file_id,
            filename=data["filename"],
            filepath=data["filepath"],
            size=data["size"],
            filetype=data["filetype"],
            userid=data["userid"],
            is_ai_parsed=is_ai_parsed,
            upload_time=data.get("upload_time"),
            description=data.get("description"),
        )
