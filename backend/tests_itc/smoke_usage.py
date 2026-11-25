"""itc 用量计量落库 · 真机自测（独立 SQLite，不依赖 StaffDeck 全环境）。

运行::

    backend/.venv-itc/Scripts/python.exe backend/tests_itc/smoke_usage.py

验证四件事：
1. itc_platform.models 能被导入且 8 张表登记进 metadata；
2. ``ensure_itc_schema`` 只建 ``itc_`` 前缀的表；
3. ``write_usage`` 入队非阻塞 + ``flush_now`` 批量落库；
4. 落库数据可查询、字段与入参一致（含 None 原样保留，即 D-13 口径）。
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from sqlmodel import Session, SQLModel, create_engine, select  # noqa: E402


def main() -> int:
    engine = create_engine("sqlite://")  # 内存库

    import itc_platform.db as db
    import itc_platform.usage.store as store
    from itc_platform.models import UsageRecord

    # 注入测试 engine
    db.get_engine = lambda: engine  # type: ignore[assignment]
    store.get_engine = lambda: engine  # type: ignore[assignment]

    # 1) 模型登记
    names = sorted(t for t in SQLModel.metadata.tables if t.startswith("itc_"))
    print("1) itc 表:", names)
    expected = {
        "itc_usage_records", "itc_audit_logs", "itc_model_prices",
        "itc_roles", "itc_permissions", "itc_role_bindings",
    }
    missing = expected - set(names)
    assert not missing, f"缺少 itc 表: {missing}"

    # 2) 只建 itc 表
    db.ensure_itc_schema(engine)
    from sqlalchemy import inspect

    created = sorted(inspect(engine).get_table_names())
    print("2) 实际建出:", created)
    assert all(t.startswith("itc_") for t in created), "建出了非 itc 表"

    # 3) 入队 + flush
    store.write_usage(
        tenant_id="tenant_demo", session_id="s1", user_id="u1", agent_id="AI-001",
        input_tokens=1200, output_tokens=340, cached_tokens=None, total_tokens=1540,
        model_name="qwen3.6-27b", source_type="对话", span_id="sp1",
    )
    store.write_usage(
        tenant_id="tenant_demo", session_id="s2", user_id="u1",
        input_tokens=None, output_tokens=None,  # 厂商未返回 usage → 记 None（D-13）
        model_name="qwen3.6-27b", source_type="定时",
    )
    written = store.flush_now()
    print(f"3) flush 落库 {written} 行")
    assert written == 2, f"预期 2 行，实际 {written}"

    # 4) 查询校验
    with Session(engine) as s:
        rows = s.exec(select(UsageRecord).order_by(UsageRecord.id)).all()
    print(f"4) 查询到 {len(rows)} 行")
    assert len(rows) == 2
    r0, r1 = rows
    assert (r0.input_tokens, r0.output_tokens, r0.total_tokens) == (1200, 340, 1540)
    assert r0.cached_tokens is None
    assert r1.input_tokens is None and r1.output_tokens is None, "缺失 usage 未原样保留 None"
    assert r0.tenant_id == "tenant_demo" and r0.agent_id == "AI-001"

    print("\n✅ 全部通过：模型登记 / 只建 itc 表 / 入队+批量落库 / 字段原样（含 None）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
