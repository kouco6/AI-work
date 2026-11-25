"""itc 新表的 DB 接入。

策略：
* **复用** StaffDeck 的全局 engine（``app.db.engine``，见 ``backend/app/db/__init__.py:1``），
  不为 itc 另开连接池；
* 只建/管 **``itc_`` 前缀**的表，绝不触碰 StaffDeck 原有表；
* StaffDeck 的 ``init_db`` 走 ``SQLModel.metadata.create_all``——只要 ``itc_platform.models``
  已被 import，itc 表就在同一 metadata 里，会被一并建出；``ensure_itc_schema`` 是显式兜底。

> 延迟导入 ``app.db``：便于单元自测时用独立 engine，不强依赖 StaffDeck 全环境。
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Engine
from sqlmodel import SQLModel

ITC_TABLE_PREFIX = "itc_"


def get_engine() -> Engine:
    """复用 StaffDeck 的全局 engine。"""
    from app.db import engine  # noqa: PLC0415 - 延迟导入，见模块 docstring

    return engine


def itc_tables() -> list:
    """当前 metadata 里 ``itc_`` 前缀的表对象。"""
    import itc_platform.models  # noqa: F401  确保模型已登记进 metadata

    return [t for name, t in SQLModel.metadata.tables.items() if name.startswith(ITC_TABLE_PREFIX)]


def ensure_itc_schema(engine: Optional[Engine] = None) -> None:
    """只建 itc 表（不碰 StaffDeck 表）。幂等，可重复调用。"""
    tables = itc_tables()
    if not tables:
        return
    SQLModel.metadata.create_all(engine or get_engine(), tables=tables)
