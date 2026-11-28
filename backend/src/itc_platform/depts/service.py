"""部门服务（FR-266）。

* 部门 CRUD + 层级
* 用户 ↔ 部门 归属
* 部门负责人
* 部门统计（成本/KPI 按部门，基于 ``itc_usage_records`` + 成员映射）
* 部门权限（FR-232）：负责人可管本部门。

**非侵入**：不改原生 ``User`` 表，归属存 ``itc_dept_members``。
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import Engine
from sqlmodel import Session, select

from itc_platform.db import ensure_itc_schema, get_engine
from itc_platform.models import Dept, DeptMember


def create_dept(*, tenant_id: str, name: str, parent_id: Optional[int] = None, leader_user_id: Optional[str] = None, engine: Optional[Engine] = None) -> int:
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as s:
        row = Dept(tenant_id=tenant_id, name=name[:128], parent_id=parent_id, leader_user_id=leader_user_id)
        s.add(row)
        s.commit()
        s.refresh(row)
        return int(row.id or 0)


def list_depts(tenant_id: str, *, engine: Optional[Engine] = None) -> list[dict[str, Any]]:
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as s:
        depts = s.exec(select(Dept).where(Dept.tenant_id == tenant_id).order_by(Dept.id)).all()
        members = s.exec(select(DeptMember).where(DeptMember.tenant_id == tenant_id)).all()
    by_dept: dict[int, list[str]] = {}
    for m in members:
        by_dept.setdefault(m.dept_id, []).append(m.user_id)
    return [
        {
            "id": str(d.id),
            "name": d.name,
            "parentId": d.parent_id,
            "leaderUserId": d.leader_user_id,
            "memberCount": len(by_dept.get(d.id, [])),
            "members": by_dept.get(d.id, []),
        }
        for d in depts
    ]


def set_members(*, tenant_id: str, dept_id: int, user_ids: list[str], engine: Optional[Engine] = None) -> int:
    """整体设置部门成员（覆盖式）。"""
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as s:
        dept = s.get(Dept, dept_id)
        if dept is None or dept.tenant_id != tenant_id:
            return 0
        for old in s.exec(select(DeptMember).where(DeptMember.tenant_id == tenant_id, DeptMember.dept_id == dept_id)).all():
            s.delete(old)
        for uid in user_ids:
            s.add(DeptMember(tenant_id=tenant_id, dept_id=dept_id, user_id=uid))
        s.commit()
        return len(user_ids)


def dept_of_user(tenant_id: str, user_id: str, *, engine: Optional[Engine] = None) -> Optional[int]:
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as s:
        m = s.exec(select(DeptMember).where(DeptMember.tenant_id == tenant_id, DeptMember.user_id == user_id)).first()
    return m.dept_id if m else None


def set_user_dept(tenant_id: str, user_id: str, dept_id: Optional[int], *, engine: Optional[Engine] = None) -> int:
    """把某用户归到某部门（None = 移出所有部门）。一个用户只属一个部门。"""
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as s:
        for old in s.exec(select(DeptMember).where(DeptMember.tenant_id == tenant_id, DeptMember.user_id == user_id)).all():
            s.delete(old)
        if dept_id is not None:
            s.add(DeptMember(tenant_id=tenant_id, dept_id=dept_id, user_id=user_id))
        s.commit()
        return 1


def user_dept_map(tenant_id: str, *, engine: Optional[Engine] = None) -> dict[str, str]:
    """用户 id → 部门名（供人员列表展示）。"""
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as s:
        depts = {d.id: d.name for d in s.exec(select(Dept).where(Dept.tenant_id == tenant_id)).all()}
        members = s.exec(select(DeptMember).where(DeptMember.tenant_id == tenant_id)).all()
    return {m.user_id: depts.get(m.dept_id, "") for m in members}


def is_dept_leader(tenant_id: str, dept_id: int, user_id: str, *, engine: Optional[Engine] = None) -> bool:
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as s:
        d = s.get(Dept, dept_id)
    return bool(d and d.tenant_id == tenant_id and d.leader_user_id == user_id)


def delete_dept(*, tenant_id: str, dept_id: int, engine: Optional[Engine] = None) -> int:
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as s:
        d = s.get(Dept, dept_id)
        if d is None or d.tenant_id != tenant_id:
            return 0
        for m in s.exec(select(DeptMember).where(DeptMember.tenant_id == tenant_id, DeptMember.dept_id == dept_id)).all():
            s.delete(m)
        s.delete(d)
        s.commit()
        return 1


def dept_stats(tenant_id: str, dept_id: int, *, engine: Optional[Engine] = None) -> dict[str, Any]:
    """部门统计（FR-131/266）：成员数 + 本部门成员的用量/成本汇总。"""
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as s:
        member_ids = [m.user_id for m in s.exec(select(DeptMember).where(DeptMember.tenant_id == tenant_id, DeptMember.dept_id == dept_id)).all()]
        dept = s.get(Dept, dept_id)
    calls = 0
    tokens = 0
    cost = 0.0
    if member_ids:
        from itc_platform.cost import service as cost_svc
        from itc_platform.models import UsageRecord

        prices = cost_svc.lookup_prices(eng)
        with Session(eng) as s:
            rows = s.exec(select(UsageRecord).where(UsageRecord.tenant_id == tenant_id, UsageRecord.user_id.in_(member_ids))).all()
        for r in rows:
            calls += 1
            tokens += r.total_tokens or 0
            cost += cost_svc._cost_of(r, cost_svc.resolve_price(prices, r.model_name))
    return {
        "deptId": str(dept_id),
        "name": dept.name if dept else "",
        "memberCount": len(member_ids),
        "calls": calls,
        "totalTokens": tokens,
        "cost": round(cost, 6),
    }
