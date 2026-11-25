"""itc 共享记忆 L1/L2 · 真机自测（FR-201）。

运行::

    backend/.venv-itc/Scripts/python.exe backend/tests_itc/smoke_memory.py

验证：
1. SharedMemory 表登记；
2. upsert/list（全局 + 岗位、按 key 去重）；
3. **provider 合并**：recall = 原生（call_local）在前 + 共享层在后；非 recall 透传原生；
4. provider 装入 runtime.memory 槽。
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BACKEND), str(BACKEND / "src")]

from sqlmodel import SQLModel, create_engine  # noqa: E402


class _Ctx:
    """最小 MemoryContext 替身：call_local() 返回原生记忆。"""

    def __init__(self, native):
        self._native = native

    def call_local(self):
        return self._native


def main() -> int:
    engine = create_engine("sqlite://")
    import itc_platform.db as db
    import itc_platform.memory.store as mem

    db.get_engine = lambda: engine  # type: ignore[assignment]
    mem.get_engine = lambda: engine  # type: ignore[assignment]

    # 1) 表登记
    names = [t for t in SQLModel.metadata.tables if t.startswith("itc_")]
    assert "itc_shared_memories" in names, names
    print("1) itc 表含 itc_shared_memories ✅  （共", len(names), "张）")

    # 2) upsert + list
    mem.upsert_shared(tenant_id="t", scope="global", content="公司统一规则：所有对外内容需合规检测", key="g_rule")
    mem.upsert_shared(tenant_id="t", scope="role", owner="AI-001", content="情报小秘岗位经验：简报按标签筛选", key="r_intel")
    mem.upsert_shared(tenant_id="t", scope="role", owner="AI-002", content="反调官岗位经验：逐条核对来源", key="r_qa")
    # 同 key 覆盖（去重）
    mem.upsert_shared(tenant_id="t", scope="role", owner="AI-001", content="情报小秘岗位经验（V2）", key="r_intel")

    rows = mem.list_shared(tenant_id="t", agent_id="AI-001")
    scopes = sorted((r["metadata"]["scope"], r["content"]) for r in rows)
    print("2) AI-001 适用共享记忆:", scopes)
    assert len(rows) == 2, f"AI-001 应见 全局1+岗位1，实际 {len(rows)}"
    assert any("V2" in r["content"] for r in rows), "同 key 未覆盖去重"
    assert not any("反调官" in r["content"] for r in rows), "串到了别的岗位"

    # 3) provider 合并
    from staffdeck_harness.contracts.memory import MemoryCall

    import itc_modules.memory_shared as ms

    native = [{"id": "native-1", "kind": "preference", "content": "用户偏好：先给结论", "metadata": {}}]
    prov = ms.SharedMemoryProvider()

    recall_call = MemoryCall("recall", "t", "u1", agent_id="AI-001")
    out = prov.invoke(_Ctx(native), recall_call)
    kinds = [(r.get("metadata") or {}).get("shared", False) for r in out]
    print(f"3) recall 合并：{len(out)} 条（native={kinds.count(False)}，shared={kinds.count(True)}）")
    assert out[0]["id"] == "native-1", "原生记忆应排在前（L3/L4 优先级高于 L1/L2）"
    assert sum(1 for k in kinds if k) == 2, "共享层应有 2 条（全局+AI-001岗位）"

    # 非 recall 透传
    cap = prov.invoke(_Ctx(native), MemoryCall("capture", "t", "u1", agent_id="AI-001", payload={}))
    assert cap == native, "capture 应原样透传原生"
    print("   非 recall（capture）透传原生 ✅")

    # 4) 装入 runtime.memory 槽
    from staffdeck_harness.contracts.manifest import SlotName
    from staffdeck_harness.modules.registry import ModuleRegistry

    reg = ModuleRegistry()
    ms.register(reg, {})
    in_slot = [it.manifest.module_id for it in reg.providers(SlotName.RUNTIME_MEMORY)]
    print("4) runtime.memory 槽:", in_slot)
    assert "memory.shared" in in_slot

    print("\n✅ 共享记忆通过：建表 / upsert去重 / 作用域隔离 / recall 合并 / 透传 / 装配")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
