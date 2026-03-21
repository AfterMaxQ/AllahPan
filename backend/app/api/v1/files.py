"""
文件管理API模块。

本模块提供文件上传、下载、预览、分片上传和列表查询等文件管理相关的RESTful API接口。
支持异步文件上传、文件元数据管理、断点续传以及文件访问控制。

作者: AllahPan团队
创建日期: 2026-03-19
最后修改: 2026-03-20
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from filelock import FileLock

import re

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Header
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

# 用于判断文件名是否为“UUID 或 UUID.扩展名”，此类名称在下载时替换为友好名
_UUID_FILENAME_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(\.[^.]+)?$"
)


def _download_display_filename(stored_filename: str) -> str:
    """若存储文件名为 UUID（或 UUID.扩展名），返回友好下载名，否则返回原样。"""
    if not (stored_filename or stored_filename.strip()):
        return "下载文件"
    name = stored_filename.strip()
    if _UUID_FILENAME_RE.match(name):
        ext = Path(name).suffix
        return f"下载文件{ext}" if ext else "下载文件"
    return name

from app.api.v1.dependencies import get_current_user, get_file_repo, get_ollama, AuthUser
from app.config import STORAGE_DIR, DATA_DIR
from app.database.repositories.file_repository import FileRepository
from app.models.file_metadata import FileMetadata
from app.services.image_parser import get_image_parser_queue

import logging

logger = logging.getLogger(__name__)


router = APIRouter()

# 断点续传配置
UPLOAD_CHUNK_DIR = DATA_DIR / "upload_chunks"
UPLOAD_PROGRESS_DIR = DATA_DIR / "upload_progress"
CHUNK_SIZE = 5 * 1024 * 1024  # 5MB per chunk

# 确保目录存在
UPLOAD_CHUNK_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_PROGRESS_DIR.mkdir(parents=True, exist_ok=True)


class FileMetadataResponse(BaseModel):
    """
    文件元数据响应模型。
    
    属性:
        file_id: 文件唯一标识符（UUID）
        filename: 原始文件名
        filepath: 文件存储路径
        size: 文件大小（字节）
        filetype: 文件MIME类型
        is_ai_parsed: 是否已进行AI解析
        upload_time: 上传时间
    """
    file_id: str
    filename: str
    filepath: str
    size: int
    filetype: str
    is_ai_parsed: bool
    upload_time: str


class DirectoryEntry(BaseModel):
    """当前层下的目录项（对应磁盘真实子目录）。"""
    name: str
    path: str  # 相对根目录的路径，用于进入该目录时请求 list?path=path


class FileListResponse(BaseModel):
    """
    文件列表响应模型。
    
    属性:
        directories: 当前层下的目录列表（磁盘真实子目录）
        files: 当前层下的文件元数据列表
        total: 文件总数
    """
    directories: List[DirectoryEntry] = []
    files: List[FileMetadataResponse] = []
    total: int = 0


class FileParseRequest(BaseModel):
    """
    文件解析请求模型。
    
    属性:
        force: 是否强制重新解析，即使已解析过
    """
    force: bool = False


# ==================== 断点续传相关模型 ====================

class ChunkUploadInit(BaseModel):
    """分片上传初始化请求。"""
    filename: str
    file_size: int
    chunk_size: int = CHUNK_SIZE
    content_type: str = "application/octet-stream"


class ChunkUploadInitResponse(BaseModel):
    """分片上传初始化响应。"""
    upload_id: str
    chunk_size: int
    total_chunks: int
    file_id: Optional[str] = None


class ChunkUploadRequest(BaseModel):
    """分片上传请求。"""
    upload_id: str
    chunk_index: int


class ChunkUploadResponse(BaseModel):
    """分片上传响应。"""
    upload_id: str
    chunk_index: int
    received: bool
    total_received: int
    total_chunks: int
    progress: float


class UploadProgressResponse(BaseModel):
    """上传进度响应。"""
    upload_id: str
    filename: str
    file_size: int
    chunk_size: int
    total_chunks: int
    received_chunks: List[int]
    progress: float
    is_complete: bool


class UploadCompleteResponse(BaseModel):
    """上传完成响应。"""
    success: bool
    file_id: str
    filename: str
    file_metadata: Optional[FileMetadataResponse] = None
    error: Optional[str] = None


# ==================== 断点续传辅助函数 ====================

def _progress_lock_path(upload_id: str) -> Path:
    """分片进度文件锁路径，用于并发安全读-改-写。"""
    return UPLOAD_PROGRESS_DIR / f"{upload_id}.json.lock"


def _get_upload_progress(upload_id: str) -> Optional[dict]:
    """获取上传进度。"""
    progress_file = UPLOAD_PROGRESS_DIR / f"{upload_id}.json"
    if progress_file.exists():
        try:
            with open(progress_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def _save_upload_progress(upload_id: str, data: dict) -> None:
    """保存上传进度。"""
    progress_file = UPLOAD_PROGRESS_DIR / f"{upload_id}.json"
    with open(progress_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _delete_upload_progress(upload_id: str) -> None:
    """删除上传进度。"""
    progress_file = UPLOAD_PROGRESS_DIR / f"{upload_id}.json"
    if progress_file.exists():
        progress_file.unlink()
    
    chunk_dir = UPLOAD_CHUNK_DIR / upload_id
    if chunk_dir.exists():
        shutil.rmtree(chunk_dir)


def _get_chunk_dir(upload_id: str) -> Path:
    """获取分片存储目录。"""
    chunk_dir = UPLOAD_CHUNK_DIR / upload_id
    chunk_dir.mkdir(parents=True, exist_ok=True)
    return chunk_dir


def _calculate_file_hash(file_path: Path) -> str:
    """计算文件 MD5 哈希。"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


# ==================== 断点续传 API ====================

@router.post("/upload/init", response_model=ChunkUploadInitResponse)
async def init_chunk_upload(
    request: ChunkUploadInit,
    current_user: AuthUser = Depends(get_current_user),
):
    """
    初始化分片上传。
    
    创建上传会话，返回 upload_id 和分片信息。
    
    参数:
        request: 初始化请求
        current_user: 当前认证用户
    
    返回:
        ChunkUploadInitResponse: 上传初始化信息
    """
    logger.info(f"初始化分片上传，用户: {current_user.username}, 文件: {request.filename}")
    
    upload_id = str(uuid.uuid4())
    total_chunks = (request.file_size + request.chunk_size - 1) // request.chunk_size
    
    progress_data = {
        "upload_id": upload_id,
        "filename": request.filename,
        "file_size": request.file_size,
        "chunk_size": request.chunk_size,
        "content_type": request.content_type,
        "total_chunks": total_chunks,
        "received_chunks": [],
        "user_id": current_user.id,
        "created_at": datetime.now().isoformat(),
    }
    _save_upload_progress(upload_id, progress_data)
    
    _get_chunk_dir(upload_id)
    
    logger.info(f"分片上传初始化成功，upload_id: {upload_id}, 总分片数: {total_chunks}")
    
    return ChunkUploadInitResponse(
        upload_id=upload_id,
        chunk_size=request.chunk_size,
        total_chunks=total_chunks,
    )


@router.post("/upload/chunk", response_model=ChunkUploadResponse)
async def upload_chunk(
    upload_id: str,
    chunk_index: int,
    file: UploadFile = File(...),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    上传分片。
    
    接收文件分片，保存到临时目录。
    
    参数:
        upload_id: 上传会话 ID
        chunk_index: 分片索引（从0开始）
        file: 分片文件内容
        current_user: 当前认证用户
    
    返回:
        ChunkUploadResponse: 上传结果
    """
    progress_data = _get_upload_progress(upload_id)
    
    if not progress_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="上传会话不存在或已过期"
        )
    
    if progress_data.get("user_id") != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此上传会话"
        )
    
    if progress_data.get("is_complete"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传已完成"
        )
    
    if chunk_index < 0 or chunk_index >= progress_data["total_chunks"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的分片索引，有效范围: 0-{progress_data['total_chunks'] - 1}"
        )
    
    chunk_dir = _get_chunk_dir(upload_id)
    chunk_path = chunk_dir / f"chunk_{chunk_index:04d}"
    
    with open(chunk_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    with FileLock(_progress_lock_path(upload_id)):
        progress_data = _get_upload_progress(upload_id)
        if not progress_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="上传会话不存在或已过期"
            )
        if chunk_index not in progress_data["received_chunks"]:
            progress_data["received_chunks"].append(chunk_index)
            progress_data["received_chunks"].sort()
        progress_data["last_chunk_at"] = datetime.now().isoformat()
        _save_upload_progress(upload_id, progress_data)
    
    received = len(progress_data["received_chunks"])
    total = progress_data["total_chunks"]
    progress_percent = (received / total) * 100 if total > 0 else 0
    
    logger.info(f"分片上传成功，upload_id: {upload_id}, 分片: {chunk_index + 1}/{total}")
    
    return ChunkUploadResponse(
        upload_id=upload_id,
        chunk_index=chunk_index,
        received=True,
        total_received=received,
        total_chunks=total,
        progress=progress_percent,
    )


@router.get("/upload/progress/{upload_id}", response_model=UploadProgressResponse)
async def get_upload_progress(
    upload_id: str,
    current_user: AuthUser = Depends(get_current_user),
):
    """
    获取上传进度。
    
    查询已接收的分片和上传进度。
    
    参数:
        upload_id: 上传会话 ID
        current_user: 当前认证用户
    
    返回:
        UploadProgressResponse: 上传进度
    """
    progress_data = _get_upload_progress(upload_id)
    
    if not progress_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="上传会话不存在"
        )
    
    if progress_data.get("user_id") != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此上传会话"
        )
    
    received = len(progress_data["received_chunks"])
    total = progress_data["total_chunks"]
    progress_percent = (received / total) * 100 if total > 0 else 0
    
    is_complete = progress_data.get("is_complete", False)
    
    return UploadProgressResponse(
        upload_id=upload_id,
        filename=progress_data["filename"],
        file_size=progress_data["file_size"],
        chunk_size=progress_data["chunk_size"],
        total_chunks=total,
        received_chunks=progress_data["received_chunks"],
        progress=progress_percent,
        is_complete=is_complete,
    )


@router.post("/upload/complete/{upload_id}", response_model=UploadCompleteResponse)
async def complete_upload(
    upload_id: str,
    current_user: AuthUser = Depends(get_current_user),
):
    """
    完成上传。
    
    合并所有分片，生成最终文件，并清理临时文件。
    
    参数:
        upload_id: 上传会话 ID
        current_user: 当前认证用户
    
    返回:
        UploadCompleteResponse: 完成结果
    """
    progress_data = _get_upload_progress(upload_id)
    
    if not progress_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="上传会话不存在"
        )
    
    if progress_data.get("user_id") != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此上传会话"
        )
    
    if progress_data.get("is_complete"):
        return UploadCompleteResponse(
            success=True,
            file_id=progress_data.get("file_id", ""),
            filename=progress_data["filename"],
        )
    
    received = set(progress_data["received_chunks"])
    total = progress_data["total_chunks"]
    expected = set(range(total))
    
    missing = expected - received
    if missing:
        return UploadCompleteResponse(
            success=False,
            file_id="",
            filename=progress_data["filename"],
            error=f"缺少分片: {sorted(missing)}",
        )
    
    file_id = str(uuid.uuid4())
    raw_name = (progress_data.get("filename") or "unknown").strip().replace("\\", "/")
    if "/" in raw_name:
        rel_path, display_name = raw_name.rsplit("/", 1)
        rel_path = rel_path.strip("/")
    else:
        rel_path, display_name = "", raw_name
    if not display_name:
        display_name = "unknown"
    stored_path = (STORAGE_DIR / rel_path / display_name) if rel_path else (STORAGE_DIR / display_name)
    stored_path = stored_path.resolve()
    try:
        stored_path.relative_to(STORAGE_DIR.resolve())
    except ValueError:
        _delete_upload_progress(upload_id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法路径")
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = STORAGE_DIR / f"{file_id}.tmp"
    chunk_dir = _get_chunk_dir(upload_id)

    try:
        with open(temp_path, "wb") as dest:
            for i in range(total):
                chunk_path = chunk_dir / f"chunk_{i:04d}"
                with open(chunk_path, "rb") as src:
                    shutil.copyfileobj(src, dest)
        actual_size = temp_path.stat().st_size
        if actual_size != progress_data["file_size"]:
            logger.warning(
                f"文件大小不匹配，预期: {progress_data['file_size']}, 实际: {actual_size}，upload_id: {upload_id}"
            )
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            _delete_upload_progress(upload_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件大小校验失败，预期 {progress_data['file_size']} 字节，实际 {actual_size} 字节",
            )

        try:
            os.replace(temp_path, stored_path)
        except OSError as e:
            logger.error(f"重命名临时文件失败，upload_id: {upload_id}, 错误: {e}")
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            _delete_upload_progress(upload_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="保存最终文件失败",
            )

        file_metadata = FileMetadata(
            filename=display_name,
            filepath=str(stored_path),
            size=actual_size,
            filetype=progress_data.get("content_type", "application/octet-stream"),
            userid=current_user.id,
            is_ai_parsed=False,
            file_id=file_id,
        )
        file_repo = get_file_repo()
        created = file_repo.create_file_metadata(file_metadata)

        progress_data["is_complete"] = True
        progress_data["file_id"] = file_id
        progress_data["completed_at"] = datetime.now().isoformat()
        with FileLock(_progress_lock_path(upload_id)):
            _save_upload_progress(upload_id, progress_data)
            _delete_upload_progress(upload_id)

        if file_metadata.filetype.startswith("image/"):
            image_parser = get_image_parser_queue()
            if image_parser:
                await image_parser.add_to_queue(file_id)

        logger.info(f"分片上传完成，file_id: {file_id}, 文件: {display_name}")
        return UploadCompleteResponse(
            success=True,
            file_id=file_id,
            filename=display_name,
            file_metadata=FileMetadataResponse(
                file_id=created.file_id,
                filename=created.filename,
                filepath=created.filepath,
                size=created.size,
                filetype=created.filetype,
                is_ai_parsed=created.is_ai_parsed,
                upload_time=created.upload_time,
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"合并分片失败，upload_id: {upload_id}, 错误: {e}")
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        if stored_path.exists():
            try:
                stored_path.unlink()
            except OSError:
                pass
        _delete_upload_progress(upload_id)
        return UploadCompleteResponse(
            success=False,
            file_id="",
            filename=progress_data["filename"],
            error=str(e),
        )


@router.delete("/upload/cancel/{upload_id}")
async def cancel_upload(
    upload_id: str,
    current_user: AuthUser = Depends(get_current_user),
):
    """
    取消上传。
    
    删除已上传的分片和进度记录。
    
    参数:
        upload_id: 上传会话 ID
        current_user: 当前认证用户
    
    返回:
        JSONResponse: 取消结果
    """
    progress_data = _get_upload_progress(upload_id)
    
    if not progress_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="上传会话不存在"
        )
    
    if progress_data.get("user_id") != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此上传会话"
        )
    
    _delete_upload_progress(upload_id)
    
    logger.info(f"上传已取消，upload_id: {upload_id}")
    
    return JSONResponse({"success": True, "message": "上传已取消"})


# ==================== 原有 API（保持不变）====================

@router.post("/upload", response_model=FileMetadataResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    file_repo: "FileRepository" = Depends(get_file_repo),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    上传文件接口。
    
    该接口接收用户上传的文件，将其保存到本地存储目录，
    并在数据库中创建文件元数据记录。
    
    参数:
        file: 上传的文件对象（FastAPI自动解析）
        file_repo: 文件仓库（通过依赖注入获取）
        current_user: 当前认证用户（通过依赖注入获取）
    
    返回:
        FileMetadataResponse: 创建的文件元数据响应对象
    
    异常:
        HTTPException: 当文件保存失败时抛出500错误
    """
    logger.info(f"文件上传请求，文件名: {file.filename}, 用户: {current_user.username}")
    file_id = str(uuid.uuid4())
    raw_name = (file.filename or "unknown").strip().replace("\\", "/")
    if "/" in raw_name:
        rel_path, display_name = raw_name.rsplit("/", 1)
        rel_path = rel_path.strip("/")
    else:
        rel_path, display_name = "", raw_name
    if not display_name:
        display_name = "unknown"
    stored_path = STORAGE_DIR / rel_path / display_name if rel_path else STORAGE_DIR / display_name
    stored_path = stored_path.resolve()
    try:
        stored_path.relative_to(STORAGE_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法路径")
    stored_path.parent.mkdir(parents=True, exist_ok=True)

    with open(stored_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_metadata = FileMetadata(
        filename=display_name,
        filepath=str(stored_path),
        size=stored_path.stat().st_size,
        filetype=file.content_type or "application/octet-stream",
        userid=current_user.id,
        is_ai_parsed=False,
        file_id=file_id,
    )

    created = file_repo.create_file_metadata(file_metadata)
    logger.info(f"文件上传成功，文件 ID: {file_id}")

    # 如果是图片，自动加入解析队列
    if file_metadata.filetype.startswith("image/"):
        image_parser = get_image_parser_queue()
        if image_parser:
            await image_parser.add_to_queue(file_id)
            logger.info(f"图片已自动加入 AI 解析队列：{file_id}")
        else:
            logger.warning("ImageParserQueue 未初始化，无法自动解析图片")

    return FileMetadataResponse(
        file_id=created.file_id,
        filename=created.filename,
        filepath=created.filepath,
        size=created.size,
        filetype=created.filetype,
        is_ai_parsed=created.is_ai_parsed,
        upload_time=created.upload_time,
    )


def _list_directory_from_disk(
    storage_root: Path,
    current_path: str,
    file_repo: "FileRepository",
    current_user: AuthUser,
) -> tuple[list[dict], list[FileMetadata]]:
    """
    扫描磁盘当前层，返回目录列表与文件列表（文件若不在 DB 则惰性入库）。
    current_path: 相对 storage_root 的路径，空字符串表示根目录。
    返回 (directories_dict_list, files_metadata_list)。
    """
    target = (storage_root / current_path).resolve() if current_path else storage_root.resolve()
    root_resolved = storage_root.resolve()
    if not target.is_dir():
        return [], []
    try:
        target.relative_to(root_resolved)
    except ValueError:
        return [], []
    directories: list[dict] = []
    files_meta: list[FileMetadata] = []
    for entry in sorted(target.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            rel = entry.relative_to(root_resolved)
            dir_path = str(rel).replace("\\", "/")
            directories.append({"name": entry.name, "path": dir_path})
            continue
        if not entry.is_file():
            continue
        abs_path = str(entry.resolve())
        existing = file_repo.get_file_metadata_by_filepath(abs_path)
        if existing:
            files_meta.append(existing)
        else:
            try:
                size = entry.stat().st_size
                mt, _ = mimetypes.guess_type(entry.name)
                filetype = mt or "application/octet-stream"
                new_meta = FileMetadata(
                    filename=entry.name,
                    filepath=abs_path,
                    size=size,
                    filetype=filetype,
                    userid=current_user.id,
                    is_ai_parsed=False,
                )
                created = file_repo.create_file_metadata(new_meta)
                files_meta.append(created)
                logger.info(f"惰性入库文件: {entry.name}, file_id={created.file_id}")
            except Exception as e:
                logger.warning(f"惰性入库失败，跳过文件 {abs_path}: {e}")
    return directories, files_meta


@router.get("/list", response_model=FileListResponse)
def list_files(
    path: Optional[str] = "",
    file_repo: "FileRepository" = Depends(get_file_repo),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    获取文件列表接口（以磁盘为事实来源）。
    扫描 STORAGE_DIR 下当前 path 对应的目录，返回该层下的子目录与文件；
    若某文件尚未在 DB 中则惰性入库后返回。
    
    参数:
        path: 相对根目录的当前路径，空表示根目录
        file_repo: 文件仓库
        current_user: 当前认证用户
    
    返回:
        FileListResponse: directories + files + total
    """
    logger.debug(f"获取文件列表，path={path!r}，用户: {current_user.username}")
    norm_path = (path or "").strip().replace("\\", "/").strip("/")
    dirs_list, files_list = _list_directory_from_disk(
        STORAGE_DIR, norm_path, file_repo, current_user
    )
    return FileListResponse(
        directories=[DirectoryEntry(name=d["name"], path=d["path"]) for d in dirs_list],
        files=[
            FileMetadataResponse(
                file_id=f.file_id,
                filename=f.filename,
                filepath=f.filepath,
                size=f.size,
                filetype=f.filetype,
                is_ai_parsed=f.is_ai_parsed,
                upload_time=f.upload_time,
            )
            for f in files_list
        ],
        total=len(files_list),
    )


@router.get("/{file_id}", response_model=FileMetadataResponse)
def get_file(
    file_id: str,
    file_repo: "FileRepository" = Depends(get_file_repo),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    获取文件元数据接口。
    
    该接口根据文件ID返回指定文件的元数据信息，
    不包含文件内容。
    
    参数:
        file_id: 文件唯一标识符
        file_repo: 文件仓库（通过依赖注入获取）
        current_user: 当前认证用户（通过依赖注入获取）
    
    返回:
        FileMetadataResponse: 文件元数据响应对象
    
    异常:
        HTTPException: 当文件不存在时抛出404错误
    """
    logger.debug(f"获取文件元数据，文件ID: {file_id}, 用户: {current_user.username}")
    file_metadata = file_repo.get_file_metadata_by_id(file_id)

    if file_metadata is None:
        logger.warning(f"文件不存在，文件ID: {file_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在",
        )

    logger.debug(f"成功获取文件元数据，文件ID: {file_id}")
    return FileMetadataResponse(
        file_id=file_metadata.file_id,
        filename=file_metadata.filename,
        filepath=file_metadata.filepath,
        size=file_metadata.size,
        filetype=file_metadata.filetype,
        is_ai_parsed=file_metadata.is_ai_parsed,
        upload_time=file_metadata.upload_time,
    )


@router.get("/{file_id}/download")
def download_file(
    file_id: str,
    file_repo: "FileRepository" = Depends(get_file_repo),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    下载文件接口。
    
    该接口根据文件ID返回文件内容，触发浏览器下载。
    使用FileResponse实现高效的文件流传输。
    
    参数:
        file_id: 文件唯一标识符
        file_repo: 文件仓库（通过依赖注入获取）
        current_user: 当前认证用户（通过依赖注入获取）
    
    返回:
        FileResponse: 文件下载响应对象
    
    异常:
        HTTPException: 当文件不存在或已丢失时抛出404错误
    """
    logger.info(f"文件下载请求，文件ID: {file_id}, 用户: {current_user.username}")
    file_metadata = file_repo.get_file_metadata_by_id(file_id)

    if file_metadata is None:
        logger.warning(f"下载失败，文件不存在，文件ID: {file_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在",
        )

    file_path = Path(file_metadata.filepath)
    if not file_path.exists():
        logger.error(f"下载失败，文件已丢失，文件ID: {file_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件已丢失",
        )

    display_name = _download_display_filename(file_metadata.filename)
    logger.info(f"文件下载成功，文件ID: {file_id}, 下载名: {display_name}")
    return FileResponse(
        path=file_path,
        filename=display_name,
        media_type=file_metadata.filetype,
    )


@router.get("/{file_id}/preview")
def preview_file(
    file_id: str,
    file_repo: "FileRepository" = Depends(get_file_repo),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    预览文件接口。
    
    该接口根据文件ID返回文件内容，用于浏览器内预览。
    与下载接口不同，预览接口更注重直接显示文件内容。
    
    参数:
        file_id: 文件唯一标识符
        file_repo: 文件仓库（通过依赖注入获取）
        current_user: 当前认证用户（通过依赖注入获取）
    
    返回:
        FileResponse: 文件预览响应对象
    
    异常:
        HTTPException: 当文件不存在或已丢失时抛出404错误
    """
    logger.info(f"文件预览请求，文件ID: {file_id}, 用户: {current_user.username}")
    file_metadata = file_repo.get_file_metadata_by_id(file_id)

    if file_metadata is None:
        logger.warning(f"预览失败，文件不存在，文件ID: {file_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在",
        )

    file_path = Path(file_metadata.filepath)
    if not file_path.exists():
        logger.error(f"预览失败，文件已丢失，文件ID: {file_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件已丢失",
        )

    display_name = _download_display_filename(file_metadata.filename)
    logger.info(f"文件预览成功，文件ID: {file_id}, 显示名: {display_name}")
    return FileResponse(
        path=file_path,
        filename=display_name,
        media_type=file_metadata.filetype,
    )


class RenameFileRequest(BaseModel):
    """重命名请求体。"""
    filename: str


@router.patch("/{file_id}/rename")
def rename_file(
    file_id: str,
    body: RenameFileRequest,
    file_repo: "FileRepository" = Depends(get_file_repo),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    重命名文件接口。

    仅修改显示文件名及磁盘上的文件名，不改变 file_id。
    新文件名不得包含路径分隔符，且需在存储目录内。
    """
    logger.info(f"文件重命名请求，文件ID: {file_id}, 新名: {body.filename}, 用户: {current_user.username}")
    new_name = (body.filename or "").strip().replace("\\", "/")
    if not new_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件名为空")
    if "/" in new_name or new_name in (".", ".."):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件名不能包含路径")

    file_metadata = file_repo.get_file_metadata_by_id(file_id)
    if file_metadata is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    old_path = Path(file_metadata.filepath)
    if not old_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件已丢失")

    new_path = old_path.parent / new_name
    try:
        new_path.resolve().relative_to(STORAGE_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法路径")
    if new_path.exists() and new_path != old_path:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="目标文件名已存在")

    try:
        old_path.rename(new_path)
    except OSError as e:
        logger.error(f"重命名物理文件失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="重命名失败",
        )

    file_metadata.filename = new_name
    file_metadata.filepath = str(new_path.resolve())
    if not file_repo.update_file_metadata(file_metadata):
        try:
            new_path.rename(old_path)
        except OSError:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新元数据失败",
        )

    logger.info(f"文件重命名成功，file_id: {file_id}, 新名: {new_name}")
    return FileMetadataResponse(
        file_id=file_metadata.file_id,
        filename=file_metadata.filename,
        filepath=file_metadata.filepath,
        size=file_metadata.size,
        filetype=file_metadata.filetype,
        is_ai_parsed=file_metadata.is_ai_parsed,
        upload_time=file_metadata.upload_time,
    )


@router.delete("/{file_id}")
def delete_file(
    file_id: str,
    file_repo: "FileRepository" = Depends(get_file_repo),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    删除文件接口。

    删除指定文件，级联删除文件元数据（SQLite）和语义向量（ChromaDB）。
    文件本身由 DirectoryWatcher 的异步任务在实际存储层删除。

    参数:
        file_id: 要删除的文件唯一标识符
        file_repo: 文件仓库（通过依赖注入获取）
        current_user: 当前认证用户（通过依赖注入获取）

    返回:
        dict: 包含操作结果的响应对象

    异常:
        HTTPException: 当文件不存在时抛出404错误
    """
    logger.info(f"删除文件请求，文件ID: {file_id}")

    file_metadata = file_repo.get_file_metadata_by_id(file_id)
    if file_metadata is None:
        logger.warning(f"文件不存在，文件ID: {file_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在",
        )

    success = file_repo.delete_file_metadata(file_id)

    if not success:
        logger.error(f"文件删除失败，文件ID: {file_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="文件删除失败",
        )

    logger.info(f"文件删除成功，文件ID: {file_id}")
    return {"success": True, "file_id": file_id, "message": "文件删除成功"}
