"""产出物服务（FR-211~216，D-10 存平台 + 平台 RBAC）。

* 列表（FR-211/216）：按「视图」过滤——个人产出 / 平台产出 / 按员工 / 版本与归档
* 权限（FR-212）：默认仅**产出者本人**可见；``visibility`` = private/user/dept/all
* 元数据（FR-213）、版本（FR-214）、归档（FR-215）、检索（FR-216）

产出物本体存**平台存储**（``storage_path`` 指向 ITC 数据目录下的 ``artifacts/<年>/<月>/<类型>/``）；
本模块管**登记 + 权限 + 版本 + 归档**，不做公司文件服务器对接（D-10）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Engine
from sqlmodel import Session, select

from itc_platform.db import ensure_itc_schema, get_engine
from itc_platform.models import ItcArtifact


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_dict(a: ItcArtifact) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "name": a.name,
        "type": a.file_type,
        "agentId": a.agent_id,
        "agentName": a.agent_name,
        "producedBy": a.produced_by,
        "source": a.source,
        "version": f"V{a.version}.0",
        "size": a.size,
        "visibility": a.visibility,
        "archived": a.archived,
        "storagePath": a.storage_path,
        "sourceUrl": a.source_url,
        "parentId": a.parent_id,
        "createdAt": a.created_at.isoformat() if a.created_at else "",
    }


def _can_view(a: ItcArtifact, user_id: Optional[str], is_admin: bool) -> bool:
    """FR-212 权限：管理员见全部；否则产出者本人 / 显式分享 / all。"""
    if is_admin:
        return True
    if a.visibility == "all":
        return True
    if a.produced_by and a.produced_by == user_id:
        return True
    if user_id and a.shared_with and user_id in a.shared_with:
        return True
    return False


def register_artifact(
    *,
    tenant_id: str,
    name: str,
    produced_by: Optional[str],
    file_type: str = "",
    agent_id: Optional[str] = None,
    agent_name: str = "",
    source: str = "对话",
    task_id: Optional[str] = None,
    session_id: Optional[str] = None,
    size: int = 0,
    storage_path: str = "",
    source_url: str = "",
    parent_id: Optional[int] = None,
    engine: Optional[Engine] = None,
) -> int:
    """登记一份产出物；若给了 ``parent_id`` 则版本号 +1（FR-214，不覆盖原文件）。"""
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    now = _now()
    version = 1
    if parent_id is not None:
        with Session(eng) as s:
            parent = s.get(ItcArtifact, parent_id)
            if parent is not None:
                version = (parent.version or 1) + 1
    # 目录：年/月/类型（FR-211 命名规范 [日期]-[类型]-[主题].[后缀]）
    if not storage_path:
        storage_path = f"artifacts/{now.year:04d}/{now.month:02d}/{file_type or 'other'}/{name}"
    with Session(eng) as s:
        row = ItcArtifact(
            tenant_id=tenant_id, name=name[:300], file_type=file_type[:32],
            agent_id=agent_id, agent_name=agent_name[:128], produced_by=produced_by,
            source=source, task_id=task_id, session_id=session_id, version=version,
            parent_id=parent_id, size=size, storage_path=storage_path[:512],
            source_url=source_url[:512], created_at=now, updated_at=now,
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        return int(row.id or 0)


def list_artifacts(
    tenant_id: str,
    *,
    user_id: Optional[str] = None,
    is_admin: bool = False,
    view: str = "mine",
    agent_id: Optional[str] = None,
    query: str = "",
    engine: Optional[Engine] = None,
) -> list[dict[str, Any]]:
    """列出产出物（按视图 + RBAC 过滤）。

    view: ``mine`` 个人产出 | ``platform`` 平台产出（管理员看全部，普通用户看自己可见的）|
    ``by-agent`` 按员工（需 agent_id）| ``versions`` 版本与归档
    """
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as s:
        stmt = select(ItcArtifact).where(ItcArtifact.tenant_id == tenant_id)
        if view == "mine":
            stmt = stmt.where(ItcArtifact.produced_by == user_id)
        elif view == "by-agent" and agent_id:
            stmt = stmt.where(ItcArtifact.agent_id == agent_id)
        rows = s.exec(stmt.order_by(ItcArtifact.created_at.desc())).all()
    out = [a for a in rows if _can_view(a, user_id, is_admin)]
    if query:
        q = query.lower()
        out = [a for a in out if q in a.name.lower() or q in a.agent_name.lower() or q in a.file_type.lower()]
    return [_to_dict(a) for a in out]


def share_artifact(
    *, tenant_id: str, artifact_id: int, visibility: str, shared_with: Optional[list] = None,
    engine: Optional[Engine] = None,
) -> int:
    """改分享范围（FR-212）。"""
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as s:
        a = s.get(ItcArtifact, artifact_id)
        if a is None or a.tenant_id != tenant_id:
            return 0
        a.visibility = visibility[:16]
        a.shared_with = shared_with
        a.updated_at = _now()
        s.add(a)
        s.commit()
        return 1


def archive_artifact(*, tenant_id: str, artifact_id: int, archived: bool = True, engine: Optional[Engine] = None) -> int:
    """归档 / 取消归档（FR-215）。"""
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as s:
        a = s.get(ItcArtifact, artifact_id)
        if a is None or a.tenant_id != tenant_id:
            return 0
        a.archived = archived
        a.updated_at = _now()
        s.add(a)
        s.commit()
        return 1


def delete_artifact(*, tenant_id: str, artifact_id: int, engine: Optional[Engine] = None) -> int:
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as s:
        a = s.get(ItcArtifact, artifact_id)
        if a is None or a.tenant_id != tenant_id:
            return 0
        s.delete(a)
        s.commit()
        return 1
