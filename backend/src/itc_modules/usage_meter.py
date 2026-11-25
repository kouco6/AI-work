"""用量计量 observer（FR-151/152）—— 骨架。

落点：``event.observer`` 插槽（multi-provider，未被 ``mark_guarded``）。
真值：``llm_call_finished`` 事件 payload，已含
      ``input_tokens / output_tokens / cached_input_tokens / total_tokens / model_name / span_id``
      （见 ``backend/app/llm/client.py:1259-1287``）。

D-13 口径：usage **原样记录，缺失记 None**，不做归一化。

装配（.env）::

    STAFFDECK_HARNESS_MODULES=itc_modules.usage_meter:register

> 注意：relay 的 ``_fanout`` 同步执行且吞异常（``events/relay.py:59-68``），
> 写库慢会拖慢 turn。生产实现应改为**内存队列 + 后台批量 flush**；当前骨架为直写占位。
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from staffdeck_harness.contracts.manifest import ModuleKind, SlotName
from staffdeck_harness.modules.registry import ModuleRegistry, manifest

logger = logging.getLogger("itc.usage_meter")


class UsageMeterObserver:
    """把 ``llm_call_finished`` 事件落库到 ``usage_records``。"""

    name = "observer.usage_meter"

    def on_event(
        self,
        tenant_id: str,
        session_id: str,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> None:
        if event_type != "llm_call_finished":
            return
        # 骨架占位：真实实现调 itc_platform.usage.store.write_usage(...)
        try:
            from itc_platform.usage.store import write_usage

            write_usage(
                tenant_id=tenant_id,
                session_id=session_id,
                input_tokens=payload.get("input_tokens"),
                output_tokens=payload.get("output_tokens"),
                cached_tokens=payload.get("cached_input_tokens"),
                total_tokens=payload.get("total_tokens"),
                model_name=payload.get("model_name"),
                span_id=payload.get("span_id"),
            )
        except Exception:  # 观测旁路：绝不影响主 turn
            logger.exception("usage_meter 落库失败（已忽略）")


def register(registry: ModuleRegistry, ctx: Mapping[str, Any]) -> None:
    registry.install(
        manifest(
            "usage.meter",
            "用量计量",
            summary="把每次模型调用的 usage 原样落库，供成本统计与配额。",
            kind=ModuleKind.TRUSTED,
            slots=[SlotName.EVENT_OBSERVER],
            provides=["event.observe/v1"],
        ),
        UsageMeterObserver(),
        slot=SlotName.EVENT_OBSERVER,
    )
