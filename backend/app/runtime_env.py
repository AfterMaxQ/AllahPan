"""
进程级运行环境修正。

部分环境（外置盘路径、失效的 TMPDIR、打包后 cwd 异常）会导致 SQLite 使用无效临时目录，
表现为 [Errno 2] No such file or directory。在首次打开数据库前调用 ensure_sqlite_temp_environment()。
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from app.user_dirs import get_allahpan_user_root

logger = logging.getLogger(__name__)

_applied = False


def _fallback_temp_dir() -> Path:
    try:
        return Path(tempfile.gettempdir()).resolve()
    except Exception:
        return Path("/tmp")


def ensure_sqlite_temp_environment() -> None:
    """清除无效的 TMP* 变量，并为 SQLite 指定可写的 SQLITE_TMPDIR。"""
    global _applied
    if _applied:
        return
    _applied = True

    local_tmp: Path | None = None
    try:
        candidate = get_allahpan_user_root() / "tmp"
        candidate.mkdir(parents=True, exist_ok=True)
        local_tmp = candidate
    except OSError as e:
        logger.warning("无法创建用户临时目录，改用系统临时目录: %s", e)
        try:
            fb = _fallback_temp_dir()
            if fb.is_dir():
                local_tmp = fb
        except OSError:
            local_tmp = None

    for key in ("TMPDIR", "TEMP", "TMP", "SQLITE_TMPDIR"):
        raw = os.environ.get(key)
        if raw is None or not str(raw).strip():
            continue
        p = Path(raw).expanduser()
        if not p.is_dir():
            logger.warning("环境变量 %s=%r 不是有效目录，已移除，避免 SQLite 报 Errno 2", key, raw)
            del os.environ[key]

    if local_tmp is not None and local_tmp.is_dir():
        cur = os.environ.get("SQLITE_TMPDIR")
        if not cur or not Path(cur).expanduser().is_dir():
            os.environ["SQLITE_TMPDIR"] = str(local_tmp)
