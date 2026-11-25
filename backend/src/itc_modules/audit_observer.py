"""审计留存 observer（FR-224）。

落点：``event.observer`` 插槽。
职责：监听全事件流写 ``itc_audit_logs``（脱敏后，非阻塞批量）。
保留期：模块 ``start_module`` 自起后台线程做 180 天滚动删除，``stop_module`` 停掉
        （registry 会调用，见 ``staffdeck_harness/modules/registry.py:256-291``），**不改源码**。

装配（.env）::

    STAFFDECK_HARNESS_MODULES=itc_modules.audit_observer:register
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from staffdeck_harness.contracts.manifest import ModuleKind, SlotName
from staffdeck_harness.modules.registry import ModuleRegistry, manifest

logger = logging.getLogger("itc.audit_observer")

RETENTION_DAYS = 180


class AuditObserver:
    name = "observer.audit"

    def on_event(
        self,
        tenant_id: str,
        session_id: str,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> None:
        try:
            from itc_platform.audit.store import write_audit

            write_audit(
                tenant_id=tenant_id,
                session_id=session_id,
                event_type=event_type,
                payload=payload,
            )
        except Exception:  # 观测旁路：绝不影响主 turn
            logger.exception("audit_observer 落库失败（已忽略）")

    # ── 生命周期（由 registry 调用）────────────────────────────
    def start_module(self, _config: Mapping[str, Any] | None = None) -> None:
        try:
            from itc_platform.audit.store import start_retention

            start_retention()
        except Exception:
            logger.exception("审计留存线程启动失败（已忽略）")

    def stop_module(self) -> None:
        try:
            from itc_platform.audit.store import stop_retention

            stop_retention()
        except Exception:
            logger.exception("审计留存线程停止失败（已忽略）")


def register(registry: ModuleRegistry, ctx: Mapping[str, Any]) -> None:
    registry.install(
        manifest(
            "audit.observer",
            "审计留存",
            summary="把全链路操作事件留痕，保留 ≥180 天，可追溯可审计。",
            kind=ModuleKind.TRUSTED,
            slots=[SlotName.EVENT_OBSERVER],
            provides=["event.observe/v1"],
        ),
        AuditObserver(),
        slot=SlotName.EVENT_OBSERVER,
    )
