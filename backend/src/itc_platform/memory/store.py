"""共享记忆服务（FR-201 四层记忆 L1 全局 / L2 岗位）。

* 存储：``itc_shared_memories`` 表（与原生 ``memories`` 表**完全独立**）；
* 读写：本模块直接操作该表；
* 消费：``itc_modules.memory_shared`` 的 provider 在 **recall** 时把它们合并到
  原生 per-user 记忆之后（原生行为一行不改，见 D-15「无侵入」要求）。

**优先级**（需求 §4.3）：L4 会话 > L3 用户 > L2 岗位 > L1 全局。
因此合并顺序与排序为：原生个人记忆（L3/L4）在前，L2 岗位次之，L1 全局在后。
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Engine, or_
from sqlmodel import Session, select

from itc_platform.db import ensure_itc_schema, get_engine
from itc_platform.models import SharedMemory

SCOPE_GLOBAL = "global"
SCOPE_ROLE = "role"


def _norm_key(scope: str, owner: Optional[str], kind: str, key: Optional[str], content: str) -> str:
    if key:
        return key.strip().lower().replace(" ", "_")
    digest = hashlib.md5(f"{scope}:{owner}:{kind}:{content}".encode("utf-8")).hexdigest()
    return digest


def upsert_shared(
    *,
    tenant_id: str,
    scope: str,
    content: str,
    owner: Optional[str] = None,
    kind: str = "fact",
    key: Optional[str] = None,
    importance: float = 0.5,
    metadata: Optional[dict] = None,
    engine: Optional[Engine] = None,
) -> int:
    """写入/更新一条共享记忆（同 scope+owner+key 覆盖）。返回其 id。"""
    if scope not in (SCOPE_GLOBAL, SCOPE_ROLE):
        raise ValueError(f"scope 必须是 {SCOPE_GLOBAL}/{SCOPE_ROLE}")
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    nkey = _norm_key(scope, owner, kind, key, content)
    now = datetime.now(timezone.utc)
    with Session(eng) as session:
        existing = session.exec(
            select(SharedMemory)
            .where(SharedMemory.tenant_id == tenant_id)
            .where(SharedMemory.scope == scope)
            .where(SharedMemory.owner == owner)
            .where(SharedMemory.key == nkey)
        ).first()
        if existing is None:
            row = SharedMemory(
                tenant_id=tenant_id, scope=scope, owner=owner, kind=kind, key=nkey,
                content=content[:4000], importance=importance, metadata_json=metadata or {},
                created_at=now, updated_at=now,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return int(row.id or 0)
        existing.content = content[:4000]
        existing.importance = importance
        existing.metadata_json = metadata or existing.metadata_json
        existing.updated_at = now
        session.add(existing)
        session.commit()
        return int(existing.id or 0)


def list_shared(
    *,
    tenant_id: str,
    agent_id: Optional[str] = None,
    include_global: bool = True,
    include_role: bool = True,
    limit: int = 20,
    engine: Optional[Engine] = None,
) -> list[dict[str, Any]]:
    """列出适用的共享记忆（L2 岗位 + L1 全局）。

    返回形状对齐原生 ``memory_read``（可直接被 ``_RowLike`` 消费）。
    """
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    clauses = []
    if include_role and agent_id:
        clauses.append((SharedMemory.scope == SCOPE_ROLE) & (SharedMemory.owner == agent_id))
    if include_global:
        clauses.append(SharedMemory.scope == SCOPE_GLOBAL)
    if not clauses:
        return []
    with Session(eng) as session:
        stmt = (
            select(SharedMemory)
            .where(SharedMemory.tenant_id == tenant_id)
            .where(or_(*clauses))
            .order_by(SharedMemory.updated_at.desc())
            .limit(max(1, limit))
        )
        rows = list(session.exec(stmt).all())
    out: list[dict[str, Any]] = []
    for r in rows:
        meta = dict(r.metadata_json or {})
        meta["scope"] = r.scope
        if r.owner:
            meta["owner"] = r.owner
        meta["shared"] = True
        out.append(
            {
                "id": f"shared-{r.id}",
                "tenant_id": r.tenant_id,
                "user_id": None,          # 共享层不属于任何个人
                "username": None,
                "session_id": None,
                "kind": r.kind,
                "content": r.content,
                "importance": r.importance,
                "metadata": meta,
                "created_at": (r.created_at or datetime.now(timezone.utc)).isoformat(),
                "updated_at": (r.updated_at or datetime.now(timezone.utc)).isoformat(),
            }
        )
    return out


def delete_shared(*, tenant_id: str, memory_id: int, engine: Optional[Engine] = None) -> int:
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as session:
        row = session.get(SharedMemory, memory_id)
        if row is None or row.tenant_id != tenant_id:
            return 0
        session.delete(row)
        session.commit()
        return 1
