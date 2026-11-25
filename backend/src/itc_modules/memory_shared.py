"""共享记忆 provider（FR-201 四层记忆：L1 全局 / L2 岗位）。

**落点**：``runtime.memory`` 插槽（single-provider）。本 provider **替换**内置
``memory.default``，但把原生 per-user 记忆留给 ``context.call_local()`` 处理
（facade 用 ``MemoryService`` 现算），仅在 **recall** 时把共享层追加其后。

**为什么这是无侵入的**：
* 原生 ``app/memory/service.py``、``MemoryRecord`` 表、API **一行不改**；
* 通过 ``harness_module_selections``/禁用 ``memory.default`` 选择本 provider 即生效；
* 卸载本模块（不装它）→ 完全退回原生行为。

**优先级**（需求 §4.3）：L4 > L3 > L2 > L1。故合并顺序 = 原生个人记忆（L3/L4）在前、
L2 岗位次之、L1 全局在后。capture/list/clear 一律透传到原生。

装配（.env）::

    STAFFDECK_HARNESS_DISABLED_MODULES=memory.default
    STAFFDECK_HARNESS_MODULES=...,itc_modules.memory_shared:register
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from staffdeck_harness.contracts.manifest import ModuleKind, SlotName
from staffdeck_harness.modules.registry import ModuleRegistry, manifest

logger = logging.getLogger("itc.memory_shared")


class SharedMemoryProvider:
    """在原生 per-user 记忆之上叠加共享层（recall 时合并）。"""

    module_id = "memory.shared"
    name = "memory.shared"

    def invoke(self, context: Any, call: Any) -> Any:
        native = context.call_local()
        if call.operation != "recall":
            return native
        try:
            from itc_platform.memory.store import list_shared

            shared = list_shared(
                tenant_id=call.tenant_id,
                agent_id=call.agent_id,
                limit=call.limit or 20,
            )
        except Exception:
            logger.exception("共享记忆读取失败，退回原生记忆（fail-open）")
            return native
        return list(native or []) + shared


def register(registry: ModuleRegistry, ctx: Mapping[str, Any]) -> None:
    registry.install(
        manifest(
            "memory.shared",
            "共享记忆（L1/L2）",
            summary="在原生个人记忆之上叠加全局/岗位共享记忆，recall 时合并；其余操作透传原生。",
            kind=ModuleKind.TRUSTED,
            slots=[SlotName.RUNTIME_MEMORY],
            provides=["memory.read/v1", "memory.write/v1"],
            policy_actions=["memory.read/v1", "memory.write/v1"],
            metadata={"switchable": True},
        ),
        SharedMemoryProvider(),
        slot=SlotName.RUNTIME_MEMORY,
    )
