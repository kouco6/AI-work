"""内容安全 hook（FR-234）。

落点：``staff.interaction`` 的 ``HookContribution``。
契约（``staffdeck_harness/contracts/hooks.py``）：
    Handler = Callable[[HookContext, PipelineState], HookDecision]
    HookDecision.passthrough() / .deny(reason)

* ``pre_step``      输入侧：扫描 ``ctx.payload``（含 requirement）里的字符串；
* ``turn_stopping`` 输出侧：扫描 ``ctx.payload["final_text"]``。

命中敏感词 → ``HookDecision.deny(...)``（拦下该步/不输出）。
匹配引擎故障 → **fail-open**（passthrough + 记日志），避免拖垮业务可用性；
合规要求 fail-closed 时再改。

装配（.env）::

    STAFFDECK_HARNESS_MODULES=itc_modules.content_safety:register
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from staffdeck_harness.contracts.manifest import HookContribution, ModuleKind, SlotName
from staffdeck_harness.modules.registry import ModuleRegistry, manifest

logger = logging.getLogger("itc.content_safety")


def _deny_or_pass(payload: Mapping[str, Any]):
    """扫描 payload；命中则 deny。任何异常一律 fail-open（passthrough）。"""
    from staffdeck_harness.contracts.hooks import HookDecision

    try:
        from itc_platform.safety.store import check_payload

        hit, words = check_payload(payload)
        if hit:
            logger.warning("内容安全命中敏感词：%s", words)
            return HookDecision.deny(f"内容包含敏感信息，已拦截（命中：{'、'.join(words)}）")
    except Exception:
        logger.exception("内容安全检测失败，按 fail-open 放行")
    return HookDecision.passthrough()


class ContentSafety:
    """向 staff.interaction 贡献 input/output 两个 handler。"""

    module_id = "safety.content"

    @property
    def handlers(self) -> Mapping[str, Any]:
        return {
            "itc.content_safety.pre_step": self._check_input,
            "itc.content_safety.turn_stopping": self._check_output,
        }

    def _check_input(self, ctx: Any, _state: Any):
        return _deny_or_pass(getattr(ctx, "payload", {}) or {})

    def _check_output(self, ctx: Any, _state: Any):
        payload = getattr(ctx, "payload", {}) or {}
        final_text = payload.get("final_text") if isinstance(payload, Mapping) else None
        return _deny_or_pass({"final_text": final_text} if final_text else {})


def register(registry: ModuleRegistry, ctx: Mapping[str, Any]) -> None:
    registry.install(
        manifest(
            "content.safety",
            "内容安全",
            summary="对输入输出做敏感词检测，命中即拦截（fail-open 保可用）。",
            kind=ModuleKind.CODE,
            slots=[SlotName.STAFF_INTERACTION],
            provides=["hook.contribute/v1"],
            hooks=[
                HookContribution(point="pre_step", handler="itc.content_safety.pre_step", order=10, critical=False),
                HookContribution(
                    point="turn_stopping",
                    handler="itc.content_safety.turn_stopping",
                    order=10,
                    critical=False,
                ),
            ],
        ),
        ContentSafety(),
        slot=SlotName.STAFF_INTERACTION,
    )
