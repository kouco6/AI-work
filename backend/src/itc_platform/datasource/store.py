"""数据源存储（FR-178/182）。

* ``create_source`` / ``list_sources`` / ``update_source`` / ``delete_source``
* ``list_logs`` —— 爬取日志（FR-182）

数据源为**平台级配置**（管理员维护，FR-178），与原生无任何耦合。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Engine
from sqlmodel import Session, select

from itc_platform.db import ensure_itc_schema, get_engine
from itc_platform.models import CrawlLog, DataSource


def list_sources(tenant_id: str, *, engine: Optional[Engine] = None) -> list[dict[str, Any]]:
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as session:
        rows = session.exec(
            select(DataSource).where(DataSource.tenant_id == tenant_id).order_by(DataSource.id)
        ).all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "url": r.url,
            "frequency": r.frequency,
            "selector": r.selector,
            "tags": r.tags or {},
            "enabled": r.enabled,
            "status": r.status,
            "lastRun": r.last_run.isoformat() if r.last_run else "",
        }
        for r in rows
    ]


def create_source(
    *,
    tenant_id: str,
    name: str,
    url: str,
    frequency: str = "每日",
    selector: str = "",
    tags: Optional[dict] = None,
    engine: Optional[Engine] = None,
) -> int:
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    now = datetime.now(timezone.utc)
    with Session(eng) as session:
        row = DataSource(
            tenant_id=tenant_id, name=name[:200], url=url, frequency=frequency[:64],
            selector=selector[:512], tags=tags or {}, status="正常",
            created_at=now, updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return int(row.id or 0)


def update_source(*, tenant_id: str, source_id: int, patch: dict, engine: Optional[Engine] = None) -> int:
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as session:
        row = session.get(DataSource, source_id)
        if row is None or row.tenant_id != tenant_id:
            return 0
        for field in ("name", "url", "frequency", "selector", "status"):
            if field in patch and patch[field] is not None:
                setattr(row, field, str(patch[field])[:512])
        if "tags" in patch and isinstance(patch["tags"], dict):
            row.tags = patch["tags"]
        if "enabled" in patch:
            row.enabled = bool(patch["enabled"])
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        session.commit()
        return 1


def delete_source(*, tenant_id: str, source_id: int, engine: Optional[Engine] = None) -> int:
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as session:
        row = session.get(DataSource, source_id)
        if row is None or row.tenant_id != tenant_id:
            return 0
        session.delete(row)
        session.commit()
        return 1


def list_logs(tenant_id: str, *, limit: int = 100, engine: Optional[Engine] = None) -> list[dict[str, Any]]:
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as session:
        rows = session.exec(
            select(CrawlLog)
            .where(CrawlLog.tenant_id == tenant_id)
            .order_by(CrawlLog.created_at.desc())
            .limit(limit)
        ).all()
    return [
        {
            "id": str(r.id),
            "time": r.created_at.isoformat() if r.created_at else "",
            "source": r.source_name,
            "count": r.count,
            "ok": r.ok,
            "failed": r.failed,
            "reason": r.reason,
        }
        for r in rows
    ]
