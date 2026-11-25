"""成本聚合服务（FR-151/152/154）。

吃已落库的 ``itc_usage_records``，按时间窗聚合：

* ``summary()``   —— 总量（成本 / token / 调用次数 / 未计量条数）
* ``by_model()``  —— 按模型维度（FR-145 模型使用统计）
* ``by_agent()``  —— 按 AI 员工维度（FR-152 用量归属）
* ``by_user()``   —— 按用户维度（FR-154 用户用量排行）

D-13 口径：**未返回值 usage 的调用记 NULL**（费用按 0 计），报表单列「未计量」条数。
价格按 ``itc_model_prices`` 匹配，缺失回退 ``"*"`` 兜底行，再无则按 0 计。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Engine
from sqlmodel import Session, select

from itc_platform.cost.store import lookup_prices, resolve_price
from itc_platform.db import get_engine
from itc_platform.models import UsageRecord


def month_start(now: Optional[datetime] = None) -> datetime:
    """当月起点（UTC）。"""
    now = now or datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """把 API 传入的 ISO 字符串解析为 datetime；None/空 → None（由调用方取默认）。"""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


@dataclass
class CostBucket:
    key: str
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    unmetered_calls: int = 0  # usage 缺失的调用数（D-13）

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost": round(self.cost, 6),
            "unmetered_calls": self.unmetered_calls,
        }


def _cost_of(record: UsageRecord, price) -> float:
    if price is None:
        return 0.0
    inp = record.input_tokens or 0
    out = record.output_tokens or 0
    cached = record.cached_tokens or 0
    # 缓存命中的输入按 cached 单价，其余输入按 input 单价
    billable_input = max(0, inp - cached)
    return (
        billable_input * price.input_per_million
        + cached * price.cached_input_per_million
        + out * price.output_per_million
    ) / 1_000_000


def _fetch(since: datetime, until: datetime, engine: Optional[Engine]) -> list[UsageRecord]:
    with Session(engine or get_engine()) as session:
        stmt = (
            select(UsageRecord)
            .where(UsageRecord.created_at >= since)
            .where(UsageRecord.created_at < until)
        )
        return list(session.exec(stmt).all())


def _aggregate(rows: list[UsageRecord], key_fn, prices) -> dict[str, CostBucket]:
    buckets: dict[str, CostBucket] = {}
    for r in rows:
        key = key_fn(r) or "(未归属)"
        b = buckets.setdefault(key, CostBucket(key=key))
        b.calls += 1
        if r.total_tokens is None and r.input_tokens is None and r.output_tokens is None:
            b.unmetered_calls += 1
        b.input_tokens += r.input_tokens or 0
        b.output_tokens += r.output_tokens or 0
        b.total_tokens += r.total_tokens or 0
        b.cost += _cost_of(r, resolve_price(prices, r.model_name))
    return buckets


def summary(since: Optional[datetime] = None, until: Optional[datetime] = None, *, engine: Optional[Engine] = None) -> dict:
    since = since or month_start()
    until = until or datetime.now(timezone.utc)
    rows = _fetch(since, until, engine)
    prices = lookup_prices(engine)
    agg = _aggregate(rows, lambda r: "__all__", prices)
    b = agg.get("__all__", CostBucket("__all__"))
    out = b.as_dict()
    out["since"] = since.isoformat()
    out["until"] = until.isoformat()
    return out


def by_model(since=None, until=None, *, engine=None) -> list[dict]:
    return _group(by="model", since=since, until=until, engine=engine)


def by_agent(since=None, until=None, *, engine=None) -> list[dict]:
    return _group(by="agent", since=since, until=until, engine=engine)


def by_user(since=None, until=None, *, engine=None) -> list[dict]:
    return _group(by="user", since=since, until=until, engine=engine)


def by_day(since=None, until=None, *, engine=None) -> list[dict]:
    """按天聚合（时间序列，供折线图 FR-154）。返回 [{label, input, output, total, cost, calls}]。"""
    since = since or month_start()
    until = until or datetime.now(timezone.utc)
    rows = _fetch(since, until, engine)
    prices = lookup_prices(engine)
    buckets: dict[str, CostBucket] = {}
    order: list[str] = []
    for r in rows:
        label = (r.created_at or until).strftime("%m-%d")
        if label not in buckets:
            buckets[label] = CostBucket(key=label)
            order.append(label)
        b = buckets[label]
        b.calls += 1
        b.input_tokens += r.input_tokens or 0
        b.output_tokens += r.output_tokens or 0
        b.total_tokens += r.total_tokens or 0
        b.cost += _cost_of(r, resolve_price(prices, r.model_name))
    order.sort()
    return [
        {
            "label": b.key,
            "input": buckets[b.key].input_tokens,
            "output": buckets[b.key].output_tokens,
            "total": buckets[b.key].total_tokens,
            "cost": round(buckets[b.key].cost, 6),
            "calls": buckets[b.key].calls,
        }
        for b in [buckets[k] for k in order]
    ]


_KEY_FN = {
    "model": lambda r: r.model_name or "(未知模型)",
    "agent": lambda r: r.agent_id,
    "user": lambda r: r.user_id,
    "source": lambda r: r.source_type,
}


def _group(*, by: str, since=None, until=None, engine=None) -> list[dict]:
    since = since or month_start()
    until = until or datetime.now(timezone.utc)
    rows = _fetch(since, until, engine)
    prices = lookup_prices(engine)
    buckets = _aggregate(rows, _KEY_FN[by], prices)
    ranked = sorted(buckets.values(), key=lambda b: b.cost, reverse=True)
    return [b.as_dict() for b in ranked]
