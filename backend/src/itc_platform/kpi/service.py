"""AI 员工 KPI 统计（FR-128 / FR-130 / FR-153）。

数据来源（**复用原生，不新表**）：
* **用量**（调用/token/成本/未计量）← ``itc_usage_records``（itc 计量层，经 cost.by_agent）
* **准确率 / 满意度** ← 原生 ``message_feedback``（rating: ``up``/``down``），按 session→agent 归属
* **平均响应时长** ← 原生 ``harness_runs``（``finished_at - started_at``），按 session→agent 归属

KPI 等级：按**完成量 + 准确率**两项加权算综合分 → S/A/B/C/D（阈值见 ``_grade``）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Engine
from sqlmodel import Session, select

from itc_platform.cost.service import by_agent
from itc_platform.db import get_engine


def _grade(score: float) -> str:
    """综合分 → KPI 等级（S/A/B/C/D）。"""
    if score >= 0.9:
        return "S"
    if score >= 0.8:
        return "A"
    if score >= 0.65:
        return "B"
    if score >= 0.5:
        return "C"
    return "D"


def _session_to_agent(engine: Engine) -> dict[str, str]:
    """session_id → agent_id（汇总反馈/耗时用）。"""
    from app.db.models import ChatSession

    with Session(engine) as s:
        rows = s.exec(select(ChatSession.id, ChatSession.agent_id)).all()
    return {sid: aid for sid, aid in rows if aid}


def _feedback_by_agent(engine: Engine, since: Optional[datetime]) -> dict[str, dict]:
    """按 agent 统计点赞/点踩（准确率、满意度）。"""
    from app.db.models import MessageFeedback

    sess2agent = _session_to_agent(engine)
    agg: dict[str, dict] = {}
    with Session(engine) as s:
        stmt = select(MessageFeedback)
        if since is not None:
            stmt = stmt.where(MessageFeedback.created_at >= since)
        for fb in s.exec(stmt).all():
            aid = sess2agent.get(fb.session_id)
            if not aid:
                continue
            a = agg.setdefault(aid, {"up": 0, "down": 0})
            if fb.rating == "up":
                a["up"] += 1
            elif fb.rating == "down":
                a["down"] += 1
    return agg


def _duration_by_agent(engine: Engine, since: Optional[datetime]) -> dict[str, dict]:
    """按 agent 统计平均响应时长（harness_runs）。"""
    from app.db.models import HarnessRunRecord

    sess2agent = _session_to_agent(engine)
    acc: dict[str, list[float]] = {}
    with Session(engine) as s:
        stmt = select(HarnessRunRecord)
        if since is not None:
            stmt = stmt.where(HarnessRunRecord.started_at >= since)
        for run in s.exec(stmt).all():
            aid = sess2agent.get(run.session_id)
            if not aid or run.started_at is None or run.finished_at is None:
                continue
            ms = (run.finished_at - run.started_at).total_seconds() * 1000
            if ms >= 0:
                acc.setdefault(aid, []).append(ms)
    return {
        aid: {"avg_duration_ms": round(sum(v) / len(v), 1), "runs": len(v)}
        for aid, v in acc.items()
    }


def agent_kpi(since: Optional[datetime] = None, until: Optional[datetime] = None, *, engine: Optional[Engine] = None) -> list[dict]:
    """按 AI 员工返回 KPI（用量 + 准确率 + 响应时长 + 满意度 + 等级）。

    含**所有在岗员工**（无用量者也列出，等级按 0 计），按综合分降序。
    """
    eng = engine or get_engine()
    usage = {r["key"]: r for r in by_agent(since=since, until=until, engine=eng)}
    feedback = _feedback_by_agent(eng, since)
    durations = _duration_by_agent(eng, since)

    from app.db.models import AgentProfile

    with Session(eng) as s:
        agents = s.exec(select(AgentProfile).where(AgentProfile.status == "active")).all()
    agent_meta = {a.id: a.name for a in agents}

    all_ids = set(usage) | set(feedback) | set(durations) | set(agent_meta)
    out: list[dict] = []
    for aid in all_ids:
        u = usage.get(aid, {})
        calls = int(u.get("calls") or 0)
        up = feedback.get(aid, {}).get("up", 0)
        down = feedback.get(aid, {}).get("down", 0)
        rated = up + down
        accuracy = round(up / rated, 4) if rated else None          # 无反馈→null
        satisfaction = round(up / rated * 5, 2) if rated else None  # 5 分制
        dur = durations.get(aid, {})
        avg_duration_ms = dur.get("avg_duration_ms")
        unmetered = int(u.get("unmetered_calls") or 0)

        # 综合分：完成量（calls 归一，20 单封顶）× 0.5 + 准确率（无反馈按 0.8 中性）× 0.5
        volume_score = min(calls / 20.0, 1.0)
        acc_score = accuracy if accuracy is not None else 0.8
        score = round(volume_score * 0.5 + acc_score * 0.5, 4)
        out.append(
            {
                "agent_id": aid,
                "name": agent_meta.get(aid, aid),
                "calls": calls,
                "input_tokens": u.get("input_tokens", 0),
                "output_tokens": u.get("output_tokens", 0),
                "total_tokens": u.get("total_tokens", 0),
                "cost": u.get("cost", 0.0),
                "unmetered_calls": unmetered,
                "unmetered_ratio": round(unmetered / calls, 4) if calls else 0.0,
                "accuracy": accuracy,
                "satisfaction": satisfaction,
                "up": up,
                "down": down,
                "avg_duration_ms": avg_duration_ms,
                "runs": dur.get("runs", 0),
                "score": score,
                "grade": _grade(score),
            }
        )
    out.sort(key=lambda r: (-r["score"], -r["calls"], r["agent_id"]))
    return out
