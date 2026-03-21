"""
进程内 HTTP 流量统计（按分钟桶），供运维看板展示。

线程安全；默认排除 /health 等高频探测路径，可用环境变量覆盖。
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Any, DefaultDict, Deque, Dict, List

from app.config import METRICS_EXCLUDE_PREFIXES

_lock = threading.Lock()
_buckets: Deque[Dict[str, Any]] = deque(maxlen=120)
_since_start_total: int = 0
_since_start_by: DefaultDict[str, int] = defaultdict(int)


def _classify_path(path: str) -> str:
    if path.startswith("/api/v1/files"):
        return "files"
    if path.startswith("/api/v1/auth"):
        return "auth"
    if path.startswith("/api/v1/ai"):
        return "ai"
    if path.startswith("/api/v1/system"):
        return "system"
    if path.startswith("/api/v1/tunnel"):
        return "tunnel"
    if path.startswith("/api/"):
        return "api_other"
    return "web"


def _should_skip(path: str) -> bool:
    for prefix in METRICS_EXCLUDE_PREFIXES:
        if path.startswith(prefix) or path == prefix:
            return True
    return False


def record_request(path: str, method: str, status_code: int) -> None:
    """记录一次 HTTP 请求（在中间件中调用）。"""
    if _should_skip(path):
        return
    group = _classify_path(path)
    minute = int(time.time() // 60)
    global _since_start_total
    with _lock:
        _since_start_total += 1
        _since_start_by[group] += 1
        if not _buckets or _buckets[-1]["minute"] != minute:
            _buckets.append(
                {
                    "minute": minute,
                    "total": 0,
                    "by_group": defaultdict(int),
                }
            )
        b = _buckets[-1]
        b["total"] += 1
        b["by_group"][group] += 1


def get_traffic_snapshot() -> Dict[str, Any]:
    """返回最近最多 120 个分钟桶及自进程启动以来的累计。"""
    with _lock:
        series: List[Dict[str, Any]] = []
        for b in _buckets:
            by_g = dict(b["by_group"])
            series.append(
                {
                    "minute": b["minute"],
                    "minute_start_unix": b["minute"] * 60,
                    "total": b["total"],
                    "by_group": by_g,
                }
            )
        return {
            "series": series,
            "since_start": {
                "total_requests": _since_start_total,
                "by_group": dict(_since_start_by),
            },
            "groups_order": ["files", "auth", "ai", "system", "tunnel", "api_other", "web"],
        }
