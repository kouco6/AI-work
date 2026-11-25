"""itc 模块 · 真实装配路径自测（等价于运行时按 env 装载）。

运行::

    backend/.venv-itc/Scripts/python.exe backend/tests_itc/smoke_discovery.py

与 smoke_observer 的区别：这里**不走手工 register**，而是调 StaffDeck 真实的
``discover_and_install``（由 ``build_registry`` 驱动）——即运行时读
``harness_modules`` / ``STAFFDECK_HARNESS_MODULES`` 时的同一段代码
（``modules/registry.py:507-516``）。
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SRC = BACKEND / "src"
# 与 launch.py:7 一致：backend/ 与 backend/src/ 都进 sys.path（builtin 会 import app.*）
sys.path[:0] = [str(BACKEND), str(SRC)]

# 隔离环境：不读真 .env、不落数据、不要求 harness-engine 构建
_TMP = tempfile.mkdtemp(prefix="itc-smoke-")
os.environ["ULTRARAG_DOTENV"] = str(Path(_TMP) / ".env-none")
os.environ["ULTRARAG_DATA_DIR"] = str(Path(_TMP) / "data")
os.environ["HARNESS_V3_ENABLED"] = "false"

from staffdeck_harness.contracts.manifest import SlotName  # noqa: E402
from staffdeck_harness.modules.registry import build_registry  # noqa: E402


class _Settings:
    """最小 settings，字段与 tests_harness/modules/conftest.py 的 FakeSettings 对齐。"""

    security_profile = "OSS_LOCAL"
    harness_v3_enabled = False
    harness_disabled_modules = ""
    # ↓ 本次要害：装作 .env 里配了 our modules（等价 STAFFDECK_HARNESS_MODULES）
    harness_modules = (
        "itc_modules.usage_meter:register,"
        "itc_modules.audit_observer:register,"
        "itc_modules.content_safety:register"
    )
    harness_v3_root = ""
    harness_v3_home = ""
    harness_module_selections: dict = {}
    harness_module_configs: dict = {}
    harness_enabled_modules = ""
    harness_operator_tenants = ""
    base_authz_url = ""
    base_authz_decision_token = ""
    base_authz_control_token = ""
    base_authz_timeout_seconds = 3.0
    base_authz_pending_timeout_seconds = 3.0
    base_identity_internal_url = ""
    base_identity_runtime_client_id = ""
    base_identity_runtime_client_secret = ""
    base_workload_identity_audience = "staffdeck-gateway"


def main() -> int:
    reg = build_registry(_Settings())  # ← 真实发现 + 装载 + seal

    by_id = {it.manifest.module_id: it for it in reg.installed()}
    total = len(by_id)
    print(f"装配完成：共 {total} 个模块")

    expected = {
        "usage.meter": SlotName.EVENT_OBSERVER,
        "audit.observer": SlotName.EVENT_OBSERVER,
        "content.safety": SlotName.STAFF_INTERACTION,
    }
    for mid, slot in expected.items():
        assert mid in by_id, f"缺少模块 {mid}"
        installed_slot = by_id[mid].slot
        assert installed_slot == slot, f"{mid} 落在 {installed_slot}，预期 {slot}"
        print(f"  ✓ {mid:16s} → {installed_slot}")

    observers = [it.manifest.module_id for it in reg.providers(SlotName.EVENT_OBSERVER)]
    print("  event.observer 槽全部:", observers)
    assert "usage.meter" in observers and "audit.observer" in observers
    # 原生 observer 仍在（我们追加而非替换）
    assert "observer.trace" in observers, "原生 observer.trace 被顶掉——不应发生"

    print("\n✅ 真实装配路径通过：discover_and_install 按 harness_modules 装入了 3 个 itc 模块，"
          "且与原生 observer 并存")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
