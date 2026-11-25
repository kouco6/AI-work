"""模型单价存储（FR-152 成本归属配套）。

StaffDeck 的 ``ModelConfig`` **没有单价字段**，故由此表承载；
按 ``model_name`` 精确匹配，找不到则用 ``"*"`` 兜底行，再没有按 0 计。
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Engine
from sqlmodel import Session, select

from itc_platform.db import ensure_itc_schema, get_engine
from itc_platform.models import ModelPrice

FALLBACK_MODEL = "*"


def upsert_price(
    model_name: str,
    *,
    input_per_million: float = 0.0,
    output_per_million: float = 0.0,
    cached_input_per_million: float = 0.0,
    currency: str = "CNY",
    engine: Optional[Engine] = None,
) -> None:
    """写入/更新一个模型的单价（每百万 token）。"""
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as session:
        row = session.get(ModelPrice, model_name)
        if row is None:
            row = ModelPrice(model_name=model_name)
            session.add(row)
        row.currency = currency
        row.input_per_million = input_per_million
        row.output_per_million = output_per_million
        row.cached_input_per_million = cached_input_per_million
        session.commit()


def lookup_prices(engine: Optional[Engine] = None) -> dict[str, ModelPrice]:
    """一次性取全表，供批量计算时在内存里查价（避免逐条查库）。"""
    eng = engine or get_engine()
    ensure_itc_schema(eng)
    with Session(eng) as session:
        return {r.model_name: r for r in session.exec(select(ModelPrice)).all()}


def resolve_price(prices: dict[str, ModelPrice], model_name: Optional[str]) -> Optional[ModelPrice]:
    if model_name and model_name in prices:
        return prices[model_name]
    return prices.get(FALLBACK_MODEL)
