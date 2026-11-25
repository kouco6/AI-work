"""配额与限流存储（FR-156）。

四维度计数：用户 / AI员工 / 部门 / 平台。
窗口自增在 PG 用 ``INSERT ... ON CONFLICT ... DO UPDATE`` 原子完成，**不引 Redis**。
"""

from __future__ import annotations

from typing import Optional


def read_counters(
    *,
    tenant_id: Optional[str],
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    dept_id: Optional[str] = None,
    metric: str = "calls",
    period: str = "day",
) -> dict[str, int]:
    """读四维度当前窗口已用量。骨架占位，返回空 dict。"""
    return {}


def incr_counter(*, scope_type: str, scope_id: str, metric: str, window_start: str) -> None:
    """窗口自增（PG ON CONFLICT）。骨架占位。"""
    return None
