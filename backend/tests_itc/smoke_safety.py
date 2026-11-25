"""itc 内容安全 · 真机自测（FR-234）。

运行::

    backend/.venv-itc/Scripts/python.exe backend/tests_itc/smoke_safety.py

验证：
1. 词表种子（幂等） + ``scan`` 命中/不命中；
2. ``check_payload`` **递归**扫嵌套 dict/list；
3. 模块注册进 ``staff.interaction``，handler 可取出；
4. 敏感输入 → ``HookDecision.deny``；干净输入 → ``pass``；输出侧同理。
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BACKEND), str(BACKEND / "src")]

from sqlmodel import create_engine  # noqa: E402


def _ctx(point: str, payload: dict):
    from staffdeck_harness.contracts.hooks import HookContext

    return HookContext(
        point=point, tenant_id="t", agent_id="a", session_id="s",
        turn_id="tu", step=1, snapshot_id="snap", payload=payload,
    )


def main() -> int:
    engine = create_engine("sqlite://")
    import itc_platform.db as db

    db.get_engine = lambda: engine  # type: ignore[assignment]

    import itc_platform.safety.store as safety

    # 1) 词表种子（幂等）
    n = safety.ensure_default_words(engine)
    print(f"1) 首次种子写入 {n} 条（占位词 {len(safety.DEFAULT_WORDS)} 个）")
    assert n == len(safety.DEFAULT_WORDS)
    assert safety.ensure_default_words(engine) == 0, "重复种子应幂等"
    assert safety.scan("这里提到了涉密内容") == ["涉密"]
    assert safety.scan("这是一段普通文本") == []

    # 2) 递归扫描
    hit, words = safety.check_payload(
        {"requirement": {"text": "xx 绝密 yy"}, "list": ["ok", "内部机密"]}
    )
    print(f"2) 递归扫描命中：{words}")
    assert hit and set(words) == {"绝密", "内部机密"}

    # 3) 模块注册 + handler 取出
    from staffdeck_harness.modules.registry import ModuleRegistry

    import itc_modules.content_safety as cs

    reg = ModuleRegistry()
    cs.register(reg, {})
    handlers = reg.hook_handlers()
    print(f"3) 注册的 handler：{sorted(handlers)}")
    assert "itc.content_safety.pre_step" in handlers
    assert "itc.content_safety.turn_stopping" in handlers

    # 4) 输入侧：敏感 → deny；干净 → pass
    d_deny = handlers["itc.content_safety.pre_step"](
        _ctx("pre_step", {"requirement": {"text": "请外发这份涉密资料"}}), None
    )
    d_pass = handlers["itc.content_safety.pre_step"](
        _ctx("pre_step", {"requirement": {"text": "帮我查一下天气"}}), None
    )
    print(f"4) 输入侧：敏感→{d_deny.kind}（{d_deny.reason}）；干净→{d_pass.kind}")
    assert d_deny.kind == "deny" and "涉密" in (d_deny.reason or "")
    assert d_pass.kind == "pass"

    # 输出侧
    d_out = handlers["itc.content_safety.turn_stopping"](
        _ctx("turn_stopping", {"final_text": "输出里带了绝密字样"}), None
    )
    d_out_ok = handlers["itc.content_safety.turn_stopping"](
        _ctx("turn_stopping", {"final_text": "输出正常"}), None
    )
    print(f"   输出侧：敏感→{d_out.kind}；干净→{d_out_ok.kind}")
    assert d_out.kind == "deny" and d_out_ok.kind == "pass"

    print("\n✅ 内容安全通过：词表 / 递归扫描 / 模块注册 / 输入输出拦截")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
