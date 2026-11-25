"""用量存储（FR-151/152）。

设计要点（对齐《基础层设计.md》§1.1 与 §八·风险 2）：

* observer 的 ``on_event`` 在 relay 线程**同步执行**，写库绝不能拖慢 turn →
  经共享 ``BatchWriter`` 走「内存队列 + 后台批量 flush」，``write_usage`` 只入队即返回。
* 落库复用 StaffDeck 的 ``app.db.engine``（见 ``itc_platform/db.py``）。
* D-13 口径：usage **原样记录，缺失记 None**，不做归一化。
* 任何异常都**不得影响主链路**——全部吞掉并记日志（观测旁路）。

测试可用 ``flush_now()`` 同步落库，不依赖后台线程时序。
"""

from __future__ import annotations

from typing import Optional

from itc_platform.batch import BatchWriter
from itc_platform.db import ensure_itc_schema, get_engine
from itc_platform.models import UsageRecord

_writer = BatchWriter(
    "itc-usage-writer",
    engine_getter=lambda: get_engine(),
    on_first_batch=ensure_itc_schema,
)


def write_usage(
    *,
    tenant_id: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    cached_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    model_name: Optional[str] = None,
    source_type: Optional[str] = None,
    span_id: Optional[str] = None,
) -> None:
    """入队一行用量（非阻塞）。"""
    _writer.enqueue(
        UsageRecord(
            tenant_id=tenant_id,
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            total_tokens=total_tokens,
            model_name=model_name,
            source_type=source_type,
            span_id=span_id,
        )
    )


def flush_now() -> int:
    """同步落库（测试 / 关机时用）。"""
    return _writer.flush_now()


def shutdown() -> None:
    _writer.shutdown()
