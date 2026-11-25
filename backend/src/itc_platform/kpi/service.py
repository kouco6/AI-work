"""AI 员工 KPI 统计（FR-153）。

基于已落库的 ``itc_usage_records`` 按 AI 员工维度统计：
调用次数 / token / 成本 / **未计量占比**。

> ⚠️ 需求 FR-153 还要求「准确率 / 平均响应时间 / 用户评分 / KPI 等级(S/A/B/C/D)」——
> 其中**准确率与用户评分依赖反馈数据**（StaffDeck 的 message_feedback）、
> **响应时间**依赖执行记录。这些为后续扩展，本模块先落地**用量侧指标**。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Engine

from itc_platform.cost.service import by_agent


def agent_kpi(since: Optional[datetime] = None, until: Optional[datetime] = None, *, engine: Optional[Engine] = None) -> list[dict]:
    """按 AI 员工返回用量 KPI（按成本降序）。"""
    rows = by_agent(since=since, until=until, engine=engine)
    out: list[dict] = []
    for r in rows:
        calls = r["calls"] or 0
        unmetered = r["unmetered_calls"] or 0
        out.append(
            {
                "agent_id": r["key"],
                "calls": calls,
                "input_tokens": r["input_tokens"],
                "output_tokens": r["output_tokens"],
                "total_tokens": r["total_tokens"],
                "cost": r["cost"],
                "unmetered_calls": unmetered,
                "unmetered_ratio": round(unmetered / calls, 4) if calls else 0.0,
            }
        )
    return out
