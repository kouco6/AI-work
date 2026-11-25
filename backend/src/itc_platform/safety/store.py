"""itc 内容安全存储（FR-234）。

敏感词从 ``itc_sensitive_words`` 加载（带 TTL 缓存），支持：
* ``load_words()``  —— 热加载词表（DB 为空则用内置占位词）；
* ``scan(text)``     —— 返回命中的敏感词；
* ``check_payload(payload)`` —— **递归**遍历 payload 里的所有字符串，返回 (是否命中, 命中词)。

> ⚠️ 内置 ``DEFAULT_WORDS`` 仅为**演示占位**，生产须由合规部门在后台维护真实词表。
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Mapping, Optional

from sqlalchemy import Engine
from sqlmodel import Session, select

from itc_platform.models import SensitiveWord

logger = logging.getLogger("itc.safety")

# ⚠️ 演示占位词，生产必须替换为合规部门维护的真实词表
DEFAULT_WORDS = {"涉密", "绝密", "内部机密", "违规示例词"}

_CACHE_TTL_SECONDS = 60


def ensure_default_words(engine: Optional[Engine] = None) -> int:
    """若词表为空，写入演示占位词。返回写入条数。"""
    from itc_platform.db import ensure_itc_schema, get_engine

    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as session:
        existing = session.exec(select(SensitiveWord)).first()
        if existing is not None:
            return 0
        for word in sorted(DEFAULT_WORDS):
            session.add(SensitiveWord(word=word, category="demo", enabled=True))
        session.commit()
        return len(DEFAULT_WORDS)


class _WordCache:
    def __init__(self) -> None:
        self._words: set[str] = set()
        self._loaded_at = 0.0
        self._lock = threading.Lock()

    def get(self) -> set[str]:
        now = time.monotonic()
        with self._lock:
            if self._words and (now - self._loaded_at) < _CACHE_TTL_SECONDS:
                return self._words
            try:
                from itc_platform.db import get_engine

                with Session(get_engine()) as session:
                    rows = session.exec(select(SensitiveWord).where(SensitiveWord.enabled == True)).all()  # noqa: E712
                words = {r.word for r in rows if r.word}
                self._words = words or set(DEFAULT_WORDS)
            except Exception:
                logger.exception("敏感词加载失败，回退内置占位词")
                self._words = set(DEFAULT_WORDS)
            self._loaded_at = now
            return self._words


_cache = _WordCache()


def load_words() -> set[str]:
    return _cache.get()


def scan(text: str) -> list[str]:
    """返回 ``text`` 中命中的敏感词。"""
    if not text:
        return []
    lowered = text.lower()
    return [w for w in load_words() if w.lower() in lowered]


def _iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _iter_strings(v)


def check_payload(payload: Optional[Mapping[str, Any]]) -> tuple[bool, list[str]]:
    """递归扫描 payload 里所有字符串，返回 (是否命中, 命中词去重列表)。"""
    hits: list[str] = []
    for s in _iter_strings(payload or {}):
        hits.extend(scan(s))
    # 去重保序
    seen: set[str] = set()
    uniq = [w for w in hits if not (w in seen or seen.add(w))]
    return bool(uniq), uniq
