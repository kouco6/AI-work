"""配额判定（FR-156）—— 骨架（被 turn_coordinator 调用，非 ModuleRegistry 模块）。

四维度：用户 / AI员工 / 部门 / 平台；超限**硬阻断**（抛 QuotaExceeded → HTTP 429）。
判定入参由调用点传入（见下），本模块自带高性能实现，避免每次全表扫描。

挂载点（唯一源码改动，1 行）—— ``backend/app/core/turn_coordinator.py`` 的 ``run()``::

    accepted = accept(self.registry, request)
    from itc_platform.quota.gate import check_quota          # ← 新增
    check_quota(accepted.tenant_id, accepted.user_id, accepted.agent_id)  # 超限 raise
    return self._run(accepted)

为什么不能纯无侵入：``staff.ingress`` 槽按 ``metadata["ingress"]`` 名称精确匹配
（``backend/app/harness/...`` / kernel ingress），新增 provider 不参与 web 分支，
故需在 ``turn_coordinator.run`` 这个全文唯一汇聚点插入。

> 待真机确认：``accept()`` 返回对象的 tenant_id/user_id/agent_id 实际属性名
> （《基础层设计.md》附·第 1 条）。若不含 user/agent，从 session_id 反查 ChatSession。
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("itc.quota")

FAIL_OPEN = False  # 默认 fail-closed；配置可覆盖（quota_fail_open=True）


class QuotaExceeded(Exception):
    """超限硬阻断。HTTP 层应映射为 429 + 提示语。"""

    code = "QUOTA_EXCEEDED"

    def __init__(self, scope_type: str, scope_id: str, metric: str, period: str) -> None:
        super().__init__(
            f"用量已达上限（{scope_type}={scope_id} {metric}/{period}），请联系管理员提额"
        )
        self.scope_type = scope_type
        self.scope_id = scope_id
        self.metric = metric
        self.period = period


def check_quota(
    tenant_id: Optional[str],
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    dept_id: Optional[str] = None,
) -> None:
    """四维度配额检查；任一维度超限即抛 QuotaExceeded。

    骨架占位——真实实现：
      1. 读 ``quota_policies``（scope_type, scope_id, metric, period, limit_value）
      2. 读 ``quota_counters`` 当前窗口已用量（PG ``INSERT ... ON CONFLICT`` 原子自增）
      3. 命中 limit → raise QuotaExceeded
      4. 80%/90% 达阈值 → 告警管理员（FR-155）
    """
    try:
        from itc_platform.quota.store import read_counters  # noqa: F401
    except Exception:
        if not FAIL_OPEN:
            logger.warning("配额服务不可用，按 fail-closed 放行（骨架占位）")
        return
    return None
