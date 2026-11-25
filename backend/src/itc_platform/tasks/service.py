"""任务台服务（FR-196 / FR-197）。

**派活链路**（D-16）：人写目标并发布 → 系统判复杂度 → 协调型入军师池择优，执行型进执行层认领。
军师择优（D-17）：``综合得分 = 能力匹配度 × 0.5 + 空闲度 × 0.2 + 历史成功率 × 0.3``，
界面须展示三项分项得分（可解释性）。

本模块**不直接触发引擎执行**（执行仍走对话/定时链路）；它负责任务的登记、路由、分配与状态流转。
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Engine
from sqlmodel import Session, select

from itc_platform.db import ensure_itc_schema, get_engine
from itc_platform.models import ItcTask

# 复杂度规则：命中「需多岗位协作」的语义 → 协调型（D-16，先做规则，后续可引入模型判定）
_COORDINATED_HINTS = re.compile(r"协作|跨|多岗|团队|协调|组织|联合|拆解|编排|组队|多部门")


def infer_kind(title: str, description: str = "") -> str:
    """按任务所需岗位判定复杂度：命中协作语义 → coordinated，否则 execution。"""
    return "coordinated" if _COORDINATED_HINTS.search(f"{title} {description}") else "execution"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_dict(t: ItcTask) -> dict[str, Any]:
    return {
        "id": str(t.id),
        "title": t.title,
        "description": t.description,
        "kind": t.kind,
        "status": t.status,
        "assignee": t.assignee_agent_id,
        "assign_detail": t.assign_detail,
        "source": t.source,
        "token": t.token_used,
        "created_by": t.created_by,
        "attempt_no": t.attempt_no or 0,
        "escalated": bool(t.escalated),
        "resolution_log": t.resolution_log or [],
        "createdAt": t.created_at.isoformat() if t.created_at else "",
        "updatedAt": t.updated_at.isoformat() if t.updated_at else "",
    }


# ── 军师池择优（D-17）────────────────────────────────────────

def _capability_match(need_tags: list[str], expert_tags: list[str]) -> float:
    if not need_tags:
        return 0.5
    need = {s.strip().lower() for s in need_tags if s and s.strip()}
    have = {s.strip().lower() for s in expert_tags if s and s.strip()}
    if not need:
        return 0.5
    return len(need & have) / len(need)


def score_strategists(
    *,
    tenant_id: str,
    need_tags: list[str],
    incumbent_load: dict[str, int],
    engines: Optional[Engine] = None,
) -> list[dict[str, Any]]:
    """对军师池打分（D-17）。返回按综合得分降序的候选（含三项分项得分）。

    军师 = 协调层员工（``metadata.org_level == 'strategist'``，或岗位名含「军师/协调」）。
    样本不足（成功率历史 <5）取池均值；本实现用稳定近似（成功率缺省 0.8）。
    """
    eng = engines or get_engine()
    ensure_itc_schema(eng)
    from app.db.models import AgentProfile

    with Session(eng) as session:
        agents = session.exec(select(AgentProfile).where(AgentProfile.tenant_id == tenant_id)).all()

    strategists = []
    for a in agents:
        meta = a.metadata_json or {}
        role = str(meta.get("role_name") or "")
        level = str(meta.get("org_level") or "")
        is_strategist = level == "strategist" or bool(re.search(r"军师|协调|幕僚", f"{role} {a.name}"))
        if a.status != "active" or not is_strategist:
            continue
        strategists.append(a)

    rows: list[dict[str, Any]] = []
    for a in strategists:
        meta = a.metadata_json or {}
        expert = meta.get("expertise_tags") or []
        capability = _capability_match(need_tags, list(expert) if isinstance(expert, list) else [])
        load_n = incumbent_load.get(a.id, 0)
        concurrency = 5
        idleness = max(0.0, 1 - load_n / concurrency)
        success = 0.8  # 历史成功率缺省（样本不足取池均值）；后续接任务历史
        score = capability * 0.5 + idleness * 0.2 + success * 0.3
        rows.append(
            {
                "agent_id": a.id,
                "name": a.name,
                "capability": round(capability, 4),
                "idleness": round(idleness, 4),
                "success": round(success, 4),
                "score": round(score, 6),
            }
        )
    rows.sort(key=lambda r: (-r["score"], r["agent_id"]))  # 并列按工号，保证可复现（D-17）
    return rows


def _open_load(tenant_id: str, session: Session) -> dict[str, int]:
    """各员工当前未完成（assigned/running）任务数，用于算空闲度。"""
    rows = session.exec(
        select(ItcTask)
        .where(ItcTask.tenant_id == tenant_id)
        .where(ItcTask.status.in_(("assigned", "running")))
    ).all()
    load: dict[str, int] = {}
    for t in rows:
        if t.assignee_agent_id:
            load[t.assignee_agent_id] = load.get(t.assignee_agent_id, 0) + 1
    return load


# ── CRUD + 路由 ──────────────────────────────────────────────

def publish_task(
    *,
    tenant_id: str,
    title: str,
    description: str = "",
    created_by: Optional[str] = None,
    source: str = "任务台",
    engine: Optional[Engine] = None,
) -> dict[str, Any]:
    """发布任务并按复杂度自动分配（D-16）。返回任务 dict（含分配结果）。"""
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    kind = infer_kind(title, description)
    now = _now()
    with Session(eng) as session:
        task = ItcTask(
            tenant_id=tenant_id, title=title[:500], description=description[:4000],
            kind=kind, status="pending", created_by=created_by, source=source,
            created_at=now, updated_at=now,
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        if kind == "coordinated":
            load = _open_load(tenant_id, session)
            candidates = score_strategists(tenant_id=tenant_id, need_tags=[], incumbent_load=load, engines=eng)
            if candidates:
                top = candidates[0]
                task.assignee_agent_id = top["agent_id"]
                task.assign_detail = {"source": "军师池择优（D-17）", "candidates": candidates[:5], "chosen": top["agent_id"]}
                task.status = "assigned"
            else:
                task.assign_detail = {"source": "军师池择优（D-17）", "candidates": [], "note": "军师池无在岗军师，任务暂存待分配"}
            task.updated_at = _now()
            session.add(task)
            session.commit()
            session.refresh(task)
            # 协调型已分配军师 → 自动触发执行
            if task.assignee_agent_id and engine is None:
                execute_task(tenant_id=tenant_id, task_id=int(task.id))
        return _to_dict(task)


def list_tasks(tenant_id: str, *, status: Optional[str] = None, engine: Optional[Engine] = None) -> list[dict[str, Any]]:
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as session:
        stmt = select(ItcTask).where(ItcTask.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(ItcTask.status == status)
        rows = session.exec(stmt.order_by(ItcTask.created_at.desc())).all()
    return [_to_dict(t) for t in rows]


def get_task(tenant_id: str, task_id: int, *, engine: Optional[Engine] = None) -> Optional[dict[str, Any]]:
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as session:
        t = session.get(ItcTask, task_id)
        return _to_dict(t) if t and t.tenant_id == tenant_id else None


def strategist_pool(tenant_id: str, *, engine: Optional[Engine] = None) -> list[dict[str, Any]]:
    """军师池 + 各军师当前负载（供任务台展示与择优依据核对）。"""
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as session:
        load = _open_load(tenant_id, session)
    cands = score_strategists(tenant_id=tenant_id, need_tags=[], incumbent_load=load, engines=eng)
    for c in cands:
        c["load"] = load.get(c["agent_id"], 0)
    return cands


def claim_task(*, tenant_id: str, task_id: int, agent_id: str, engine: Optional[Engine] = None) -> int:
    """执行层自主认领（仅 execution 型、pending）→ 认领后**自动触发执行**。"""
    n = _transition(
        tenant_id=tenant_id, task_id=task_id, engine=engine,
        expect_status=("pending",), require_kind="execution",
        patch={"assignee_agent_id": agent_id, "status": "assigned",
               "assign_detail": {"source": "执行层自主认领"}},
    )
    if n and engine is None:
        execute_task(tenant_id=tenant_id, task_id=task_id)
    return n


def assign_task(*, tenant_id: str, task_id: int, agent_id: str, by: Optional[str] = None, engine: Optional[Engine] = None) -> int:
    """人工指定/改派员工（D-16 人干预权）→ 指定后**自动触发执行**。"""
    n = _transition(
        tenant_id=tenant_id, task_id=task_id, engine=engine,
        expect_status=("pending", "assigned", "running"),
        patch={"assignee_agent_id": agent_id, "status": "assigned",
               "assign_detail": {"source": "人工指定", "by": by}},
    )
    if n and engine is None:
        execute_task(tenant_id=tenant_id, task_id=task_id)
    return n


def recall_task(*, tenant_id: str, task_id: int, engine: Optional[Engine] = None) -> int:
    """收回任务（回到待分配）。"""
    return _transition(
        tenant_id=tenant_id, task_id=task_id, engine=engine,
        expect_status=("pending", "assigned", "running"),
        patch={"assignee_agent_id": None, "status": "pending", "assign_detail": {"source": "人工收回"}},
    )


def update_status(*, tenant_id: str, task_id: int, status: str, engine: Optional[Engine] = None) -> int:
    return _transition(tenant_id=tenant_id, task_id=task_id, engine=engine, expect_status=None, patch={"status": status})


_MAX_ATTEMPTS = 3  # 初次 + 重试 2 次（FR-194）


def _append_log(task: "ItcTask", action: str, note: str) -> None:
    """处置留痕（FR-194 全程留痕）。"""
    log = list(task.resolution_log or [])
    log.append({"at": _now().isoformat(), "action": action, "note": note})
    task.resolution_log = log


def _execute_task_core(tenant_id: str, task_id: int) -> None:
    """后台线程内执行任务；失败时按 FR-194 **自动重试 2 次 → 转军师全权处置**。"""
    from app.core.agent_loop import AgentLoop
    from app.db import engine as app_engine
    from app.db.models import ChatSession, new_id
    from app.session.session_schema import ChatTurnRequest
    from staffdeck_harness.runtime.session_binding import bind_session

    with Session(app_engine) as db:
        task = db.get(ItcTask, task_id)
        if task is None or task.tenant_id != tenant_id or not task.assignee_agent_id:
            return
        task.status = "running"
        task.attempt_no = (task.attempt_no or 0) + 1
        task.updated_at = _now()
        db.add(task)
        db.commit()

        user_id = task.created_by or "distribution-admin"
        from staffdeck_harness.runtime.control_auth import provider as _ctrl_provider
        from staffdeck_harness.runtime.actors import bind_actor

        if _ctrl_provider() is not None:
            from staffdeck_harness.runtime.identity_directory import require_internal_member

            bind_actor(db, require_internal_member(db, tenant_id, user_id, materialize=True))
        else:
            db.info["staffdeck_actor_id"] = user_id

        session = ChatSession(
            id=new_id("session"), tenant_id=tenant_id, user_id=user_id,
            agent_id=task.assignee_agent_id, title=f"任务台：{task.title[:40]}", status="active",
        )
        try:
            bind_session(db, session, created=True)
        except Exception:
            pass
        db.add(session)
        db.commit()
        db.refresh(session)
        task.session_id = session.id
        db.add(task)
        db.commit()

        request = ChatTurnRequest(
            tenant_id=tenant_id, session_id=session.id, agent_id=task.assignee_agent_id,
            user_id=user_id, message=f"{task.title}\n\n{task.description}".strip(),
            channel="web", interaction_mode="normal",
        )
        reply = ""
        token_used = 0
        failed = False
        err = ""
        try:
            for item in AgentLoop(db).handle_turn_stream(request):
                data = item.get("data") if isinstance(item, dict) else None
                if isinstance(data, dict):
                    if data.get("reply"):
                        reply = str(data["reply"])
                    if data.get("runtime_error_code"):
                        failed = True
                        err = str(data.get("reply") or data["runtime_error_code"])
                    usage = data.get("usage") or data.get("token_usage")
                    if isinstance(usage, dict):
                        token_used = int(usage.get("total_tokens") or token_used)
        except Exception as exc:
            failed = True
            err = str(exc)
        if not reply.strip():
            failed = True
            err = err or "空回复"

        task.token_used = token_used
        task.updated_at = _now()
        if not failed:
            task.status = "done"
            task.description = (task.description + f"\n\n【执行结果】{reply[:1500]}").strip()
            _append_log(task, "succeeded", f"第 {task.attempt_no} 次尝试成功")
        else:
            _append_log(task, "attempt_failed", f"第 {task.attempt_no} 次失败：{err[:200]}")
            if task.attempt_no < _MAX_ATTEMPTS:
                task.status = "assigned"  # 自动重试
            else:
                task.status = "failed"
                task.assign_detail = {**(task.assign_detail or {}), "error": err[:500]}
        db.add(task)
        db.commit()

    # 失败且重试用尽 → 转军师处置（在 session 外做，避免长事务）
    if failed:
        with Session(app_engine) as db2:
            t2 = db2.get(ItcTask, task_id)
            if t2 is not None and t2.status == "assigned":  # 还有重试机会
                from staffdeck_harness.runtime.jobs import enqueue_runtime_job

                enqueue_runtime_job(f"itc-task-{task_id}-r{t2.attempt_no}", _execute_task_core, tenant_id, task_id)
            elif t2 is not None and t2.status == "failed" and not t2.escalated:
                escalate_to_strategist(tenant_id=tenant_id, task_id=task_id)


def escalate_to_strategist(*, tenant_id: str, task_id: int, engine: Optional[Engine] = None) -> int:
    """军师全权处置（FR-194 / D-08）：重试用尽后——
    ① 换一个军师/执行员工重跑（自动）；② 军师池无人则转人工接管（status=pending）。
    全程写入 ``resolution_log``。
    """
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as s:
        task = s.get(ItcTask, task_id)
        if task is None or task.tenant_id != tenant_id:
            return 0
        task.escalated = True
        load = _open_load(tenant_id, s)
        # 优先另一位军师（协调层），其次任一在岗员工
        cands = [c for c in score_strategists(tenant_id=tenant_id, need_tags=[], incumbent_load=load, engines=eng)
                 if c["agent_id"] != task.assignee_agent_id]
        if not cands:
            from app.db.models import AgentProfile
            from sqlmodel import select as _sel

            others = s.exec(_sel(AgentProfile).where(AgentProfile.tenant_id == tenant_id, AgentProfile.status == "active")).all()
            cands = [{"agent_id": a.id, "name": a.name} for a in others if a.id != task.assignee_agent_id]
        if cands:
            chosen = cands[0]
            prev = task.assignee_agent_id
            task.assignee_agent_id = chosen["agent_id"]
            task.status = "assigned"
            task.attempt_no = 0  # 新员工重新计尝试
            _append_log(task, "escalate_reassign", f"军师处置：改派 {prev} → {chosen['agent_id']}（{chosen.get('name','')}）重跑")
            task.updated_at = _now()
            s.add(task)
            s.commit()
            from staffdeck_harness.runtime.jobs import enqueue_runtime_job

            enqueue_runtime_job(f"itc-task-{task_id}-esc", _execute_task_core, tenant_id, task_id)
            return 1
        # 无人可换 → 转人工接管（人在任务台重新派活）
        _append_log(task, "escalate_human", "军师处置：无可改派员工 → 转人工接管")
        task.status = "pending"
        task.assignee_agent_id = None
        task.updated_at = _now()
        s.add(task)
        s.commit()
        return 1


def execute_task(*, tenant_id: str, task_id: int, engine: Optional[Engine] = None) -> dict[str, Any]:
    """**异步触发任务执行**（FR-196 派活→执行）。

    入队到 StaffDeck 的后台任务队列（``enqueue_runtime_job``，与定时任务同款），立即返回、不阻塞。
    需任务已 assignee；无承接人则拒绝。``engine`` 注入时为离线模式（跳过真实执行）。
    """
    if engine is not None:
        return {"queued": False, "note": "engine 注入模式：跳过真实执行"}

    eng = get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as session:
        t = session.get(ItcTask, task_id)
        if t is None or t.tenant_id != tenant_id:
            return {"queued": False, "error": "任务不存在"}
        if not t.assignee_agent_id:
            return {"queued": False, "error": "任务尚未分配员工"}
        t.status = "running"
        t.updated_at = _now()
        session.add(t)
        session.commit()

    from staffdeck_harness.runtime.jobs import enqueue_runtime_job

    try:
        enqueue_runtime_job(f"itc-task-{task_id}", _execute_task_core, tenant_id, task_id)
    except Exception as exc:
        with Session(eng) as session:
            t = session.get(ItcTask, task_id)
            if t is not None:
                t.status = "failed"
                t.assign_detail = {**(t.assign_detail or {}), "error": f"入队失败：{exc}"}
                session.add(t)
                session.commit()
        return {"queued": False, "error": str(exc)}
    return {"queued": True, "task_id": task_id, "status": "running"}


def _transition(
    *,
    tenant_id: str,
    task_id: int,
    engine: Optional[Engine],
    expect_status: Optional[tuple[str, ...]],
    patch: dict[str, Any],
    require_kind: Optional[str] = None,
) -> int:
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as session:
        t = session.get(ItcTask, task_id)
        if t is None or t.tenant_id != tenant_id:
            return 0
        if expect_status is not None and t.status not in expect_status:
            return 0
        if require_kind is not None and t.kind != require_kind:
            return 0
        for k, v in patch.items():
            setattr(t, k, v)
        t.updated_at = _now()
        session.add(t)
        session.commit()
        return 1
