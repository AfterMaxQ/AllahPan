"""
目录监听与同步模块。

本模块提供文件系统监听功能，用于检测用户手动删除文件事件，
并自动清理SQLite数据库中的元数据记录和ChromaDB向量数据库中的向量索引。

核心价值：
- 实现"无系统级文件删除"的核心约束
- 当用户在Finder中删除文件时，自动同步清理数据库
- 保证数据库与实际文件系统的一致性

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-19
"""

from app.watcher.watcher import DirectoryWatcher
from app.watcher.handler import FileDeletionEventHandler

__all__ = ["DirectoryWatcher", "FileDeletionEventHandler"]
