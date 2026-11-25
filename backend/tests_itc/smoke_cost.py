"""itc 成本/KPI · 真机自测（FR-151/152/153/154）。

运行::

    backend/.venv-itc/Scripts/python.exe backend/tests_itc/smoke_cost.py

验证明细计算与各维度聚合。价格口径：每百万 token。
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BACKEND), str(BACKEND / "src")]

from sqlmodel import Session, create_engine  # noqa: E402

from itc_platform.models import UsageRecord  # noqa: E402


def main() -> int:
    engine = create_engine("sqlite://")

    import itc_platform.db as db
    import itc_platform.cost.store as cost_store
    import itc_platform.cost.service as cost
    import itc_platform.kpi.service as kpi

    for mod in (db, cost_store, cost, kpi):
        mod.get_engine = lambda: engine  # type: ignore[assignment]

    # 单价：qwen = 2/8/0.5（input/output/cached 每百万）；"*" 兜底 = 1/1/0
    cost_store.upsert_price("qwen3.6-27b", input_per_million=2.0, output_per_million=8.0, cached_input_per_million=0.5, engine=engine)
    cost_store.upsert_price("*", input_per_million=1.0, output_per_million=1.0, cached_input_per_million=0.0, engine=engine)

    # 用量：3 条（含 1 条未计量、1 条未知模型走兜底价）
    now = datetime.now(timezone.utc)
    with Session(engine) as s:
        s.add(UsageRecord(tenant_id="t", agent_id="AI-001", user_id="u1", model_name="qwen3.6-27b",
                          input_tokens=1000, output_tokens=500, cached_tokens=200, total_tokens=1500, created_at=now))
        s.add(UsageRecord(tenant_id="t", agent_id="AI-001", user_id="u2", model_name="qwen3.6-27b",
                          input_tokens=None, output_tokens=None, total_tokens=None, created_at=now))  # 未计量
        s.add(UsageRecord(tenant_id="t", agent_id="AI-002", user_id="u1", model_name="unknown-model",
                          input_tokens=2000, output_tokens=1000, cached_tokens=0, total_tokens=3000, created_at=now))
        s.commit()

    since, until = now - timedelta(days=1), now + timedelta(days=1)

    # 1) 总量
    s = cost.summary(since, until, engine=engine)
    print(f"1) 总览: calls={s['calls']} cost={s['cost']} unmetered={s['unmetered_calls']} total_tokens={s['total_tokens']}")
    # rec1: (800*2 + 200*0.5 + 500*8)/1e6 = 5700/1e6 = 0.0057；rec2: 0；rec3(兜底): (2000*1+1000*1)/1e6=0.003
    assert s["calls"] == 3
    assert abs(s["cost"] - 0.0087) < 1e-9, s["cost"]
    assert s["unmetered_calls"] == 1

    # 2) 按模型
    models = {r["key"]: r for r in cost.by_model(since, until, engine=engine)}
    print(f"2) 按模型: {[(k, v['calls'], v['cost']) for k, v in models.items()]}")
    assert abs(models["qwen3.6-27b"]["cost"] - 0.0057) < 1e-9
    assert abs(models["unknown-model"]["cost"] - 0.003) < 1e-9

    # 3) 按员工
    agents = {r["key"]: r for r in cost.by_agent(since, until, engine=engine)}
    print(f"3) 按员工: {[(k, v['calls'], v['cost'], v['unmetered_calls']) for k, v in agents.items()]}")
    assert agents["AI-001"]["calls"] == 2 and agents["AI-001"]["unmetered_calls"] == 1
    assert abs(agents["AI-002"]["cost"] - 0.003) < 1e-9

    # 4) 按用户（成本降序）
    users = cost.by_user(since, until, engine=engine)
    print(f"4) 按用户: {[(r['key'], r['calls'], r['cost']) for r in users]}")
    assert users[0]["key"] == "u1" and abs(users[0]["cost"] - 0.0087) < 1e-9
    assert users[0]["calls"] == 2

    # 5) KPI（含未计量占比）
    k = kpi.agent_kpi(since, until, engine=engine)
    print(f"5) KPI: {[(r['agent_id'], r['calls'], r['cost'], r['unmetered_ratio']) for r in k]}")
    ai1 = next(r for r in k if r["agent_id"] == "AI-001")
    assert ai1["unmetered_ratio"] == 0.5

    print("\n✅ 成本/KPI 通过：明细计费 / 未计量单列 / 按模型·员工·用户聚合 / KPI 占比")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
