"""戦略基底クラス。

重要(原則2: 権限分離): bots/ は core.exchange / core.execution を import しない。
戦略は BarData を受け取り StrategyIntent(意図)を返すだけ。
発注経路(根拠起票 → risk_guard → executor)は bot_runner が握る。
この分離は tests/risk/test_limits.py::TestNoBotExchangeImport で検査される。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BarData(BaseModel):
    """戦略に渡すバー(bot_runner が exchange の Bar から変換する)。"""

    ts: datetime
    o: float
    h: float
    l: float  # noqa: E741
    c: float
    v: float = 0.0


class StrategyIntent(BaseModel):
    """戦略が返す注文意図。"""

    side: str  # buy / sell
    qty: float
    est_max_loss_jpy: float | None = None
    reduces_position: bool = False
    rationale: dict[str, Any] = Field(default_factory=dict)


class Strategy(ABC):
    """バー駆動型戦略の基底(FR-9.1a)。スケジュール駆動型は Phase 1 以降。"""

    def __init__(self, bot_id: str, params: dict[str, Any]) -> None:
        self.bot_id = bot_id
        self.params = params

    @abstractmethod
    def on_bar(self, bar: BarData, position_qty: float) -> list[StrategyIntent]:
        """バー確定ごとに呼ばれ、注文意図のリストを返す(空リスト可)。"""
