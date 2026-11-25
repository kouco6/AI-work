"""审计存储（FR-224）。

* ``write_audit``：脱敏后**入队**（非阻塞），经共享 ``BatchWriter`` 落 ``itc_audit_logs``；
* ``purge_old``：删除超期审计（默认 180 天）；
* ``start_retention`` / ``stop_retention``：后台守护线程按周期滚动删除，由 observer 模块的
  ``start_module`` / ``stop_module`` 驱动（不改 StaffDeck 源码）。

脱敏对齐 StaffDeck 的 ``_redact_sensitive_values`` 思路并扩充。
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

from sqlalchemy import delete
from sqlmodel import Session

from itc_platform.batch import BatchWriter
from itc_platform.db import ensure_itc_schema, get_engine
from itc_platform.models import AuditLog

logger = logging.getLogger("itc.audit")

RETENTION_DAYS = 180
_RETENTION_INTERVAL_SECONDS = 24 * 3600  # 每 24 小时扫一次

# 脱敏白名单：命中即替换（对齐 StaffDeck 的 _redact_sensitive_values 思路，并扩充）
_REDACT_KEYS = {
    "api_key", "apikey", "authorization", "token", "access_token", "refresh_token",
    "secret", "password", "passwd", "id_card", "phone", "mobile",
}

_writer = BatchWriter(
    "itc-audit-writer",
    engine_getter=lambda: get_engine(),
    on_first_batch=ensure_itc_schema,
)

_retention_thread: Optional[threading.Thread] = None
_retention_stop = threading.Event()
_retention_lock = threading.Lock()


# ── 脱敏 ────────────────────────────────────────────────────────
def redact(payload: Mapping[str, Any]) -> dict[str, Any]:
    """对字典做浅层脱敏（键名命中白名单即替换）。"""
    return {
        k: ("[redacted]" if str(k).lower() in _REDACT_KEYS else v)
        for k, v in payload.items()
    }


# ── 写入 ────────────────────────────────────────────────────────
def write_audit(
    *,
    tenant_id: Optional[str],
    session_id: Optional[str] = None,
    event_type: str = "",
    payload: Optional[Mapping[str, Any]] = None,
    actor: Optional[str] = None,
    ip: Optional[str] = None,
) -> None:
    """入队一行审计（非阻塞）。写库前对 payload 脱敏。"""
    safe = redact(payload or {})
    _writer.enqueue(
        AuditLog(
            tenant_id=tenant_id,
            actor=actor,
            action=event_type,
            target=session_id,
            payload_json=safe,
            ip=ip,
        )
    )


def flush_now() -> int:
    """同步落库（测试 / 关机时用）。"""
    return _writer.flush_now()


# ── 留存（180 天滚动删除）───────────────────────────────────────
def purge_old(days: int = RETENTION_DAYS, engine=None) -> int:
    """删除早于 ``days`` 天的审计，返回删除行数。"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with Session(engine or get_engine()) as session:
        result = session.exec(delete(AuditLog).where(AuditLog.created_at < cutoff))
        session.commit()
        return int(result.rowcount or 0)


def start_retention(interval_seconds: int = _RETENTION_INTERVAL_SECONDS) -> None:
    """启动后台留存清理线程（幂等）。"""
    global _retention_thread
    with _retention_lock:
        if _retention_thread is not None and _retention_thread.is_alive():
            return
        _retention_stop.clear()
        _retention_thread = threading.Thread(
            target=_retention_loop, args=(interval_seconds,), name="itc-audit-retention", daemon=True
        )
        _retention_thread.start()


def stop_retention(timeout: float = 5.0) -> None:
    _retention_stop.set()
    if _retention_thread is not None:
        _retention_thread.join(timeout=timeout)


def _retention_loop(interval_seconds: int) -> None:
    # 首轮先等一个周期，避免与启动争资源
    while not _retention_stop.wait(interval_seconds):
        try:
            removed = purge_old()
            if removed:
                logger.info("审计留存：清理 %d 条超 %d 天记录", removed, RETENTION_DAYS)
        except Exception:
            logger.exception("审计留存清理失败（已忽略）")
