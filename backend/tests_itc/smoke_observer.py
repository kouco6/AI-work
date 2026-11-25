"""itc 用量计量 observer · 端到端自测（模拟 llm_call_finished 事件）。

运行::

    backend/.venv-itc/Scripts/python.exe backend/tests_itc/smoke_observer.py

验证：
1. ``usage_meter.register(registry, ctx)`` 能把模块装进真实 ModuleRegistry；
2. observer 收到 ``llm_call_finished`` 事件后，能把 payload 转成一行并落库；
3. 非目标事件（如 ``turn_started``）被忽略。
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from sqlmodel import Session, create_engine, select  # noqa: E402

from staffdeck_harness.contracts.manifest import SlotName  # noqa: E402
from staffdeck_harness.modules.registry import ModuleRegistry  # noqa: E402


def main() -> int:
    engine = create_engine("sqlite://")

    import itc_platform.db as db
    import itc_platform.usage.store as store
    from itc_platform.models import UsageRecord

    db.get_engine = lambda: engine  # type: ignore[assignment]
    store.get_engine = lambda: engine  # type: ignore[assignment]

    import itc_modules.usage_meter as usage_meter

    # 1) 装进真实 registry
    registry = ModuleRegistry()
    usage_meter.register(registry, {"settings": None, "disabled": set()})
    installed = [it.manifest.module_id for it in registry.installed()]
    print("1) 已装模块:", installed)
    assert "usage.meter" in installed, "usage.meter 未装入 registry"
    in_slot = [it.manifest.module_id for it in registry.providers(SlotName.EVENT_OBSERVER)]
    print("   event.observer 槽:", in_slot)
    assert "usage.meter" in in_slot

    # 2) 模拟事件
    observer = usage_meter.UsageMeterObserver()
    observer.on_event(
        "tenant_demo", "s9", "llm_call_finished",
        {"input_tokens": 800, "output_tokens": 200, "cached_input_tokens": 0,
         "total_tokens": 1000, "model_name": "qwen3.6-27b", "span_id": "sp9"},
    )
    observer.on_event("tenant_demo", "s9", "turn_started", {"foo": "bar"})  # 应被忽略
    written = store.flush_now()
    print(f"2) 事件落库 {written} 行（预期 1，turn_started 被忽略）")
    assert written == 1, f"预期 1 行，实际 {written}"

    with Session(engine) as s:
        row = s.exec(select(UsageRecord)).one()
    assert (row.input_tokens, row.output_tokens, row.total_tokens) == (800, 200, 1000)
    assert row.model_name == "qwen3.6-27b" and row.span_id == "sp9"

    print("\n✅ observer 链路通过：注册进 registry → 收 llm_call_finished → 落库；他类事件被忽略")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
