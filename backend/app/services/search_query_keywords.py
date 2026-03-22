"""
从用户搜索词中提取关键词，并生成安全的 SQL LIKE 通配模式。

不引入分词库，避免打包体积与依赖变化；对中文按单字、英文按词切分。
"""

from __future__ import annotations

import re
from typing import List

_MAX_KEYWORDS = 24


def escape_sql_like_literal(fragment: str) -> str:
    """转义 LIKE 特殊字符，配合 ESCAPE '\\' 使用。"""
    return (
        fragment.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def extract_search_keywords(query: str) -> List[str]:
    """
    从查询串提取去重后的关键词列表（小写拉丁词；中文单字）。
    过滤空白与过短英文（长度 < 2）。
    """
    q = (query or "").strip()
    if not q:
        return []
    seen: set[str] = set()
    out: List[str] = []
    for m in re.finditer(r"[a-zA-Z0-9]{2,}", q):
        w = m.group().lower()
        if w not in seen:
            seen.add(w)
            out.append(w)
            if len(out) >= _MAX_KEYWORDS:
                return out
    for m in re.finditer(r"[\u4e00-\u9fff]", q):
        c = m.group()
        if c not in seen:
            seen.add(c)
            out.append(c)
            if len(out) >= _MAX_KEYWORDS:
                break
    return out


def keywords_to_like_patterns(keywords: List[str]) -> List[str]:
    """为每个关键词生成 %keyword% 模式（已转义）。"""
    patterns: List[str] = []
    for kw in keywords:
        if not kw or not str(kw).strip():
            continue
        patterns.append(f"%{escape_sql_like_literal(str(kw).strip())}%")
        if len(patterns) >= _MAX_KEYWORDS:
            break
    return patterns


def description_keyword_match_score(description: str, keywords: List[str]) -> int:
    """描述中命中多少个关键词（casefold 比较，适合中英文混合）。"""
    if not description or not keywords:
        return 0
    d = description.casefold()
    return sum(1 for kw in keywords if kw and kw.casefold() in d)
