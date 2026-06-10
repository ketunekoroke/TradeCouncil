"""ブローカーアダプタ共通インターフェース(FR-8.2 / 基本設計書 §2.5)。

全モデルは instrument_id ベース。資産クラス固有の知識(シンボル変換・証拠金計算)は
各アダプタ実装に閉じ込める。Phase 0 の実装は PaperCryptoAdapter のみだが、
インターフェースは多資産(IBKR・国内株)を見越して固定する。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class Ticker(BaseModel):
    instrument_id: str
    bid: float
    ask: float
    last: float
    ts: datetime

    @property
    def spread_bps(self) -> float:
        mid = (self.bid + self.ask) / 2
        if mid <= 0:
            return 0.0
        return (self.ask - self.bid) / mid * 10_000


class Bar(BaseModel):
    instrument_id: str
    timeframe: str
    ts: datetime
    o: float
    h: float
    l: float  # noqa: E741
    c: float
    v: float = 0.0


class OrderRequest(BaseModel):
    """アダプタへの発注要求。executor が RiskApprovedOrder から組み立てる。"""

    instrument_id: str
    side: str  # buy / sell
    qty: float
    order_type: str = "market"
    limit_price: float | None = None
    idempotency_key: str | None = None


class FillInfo(BaseModel):
    qty: float
    price: float
    fee: float
    ts: datetime


class OrderResult(BaseModel):
    broker_order_id: str
    status: str  # filled / submitted / rejected
    fills: list[FillInfo] = []
    reject_reason: str | None = None


class Balance(BaseModel):
    broker: str
    currency: str
    balance: float
    margin_used: float = 0.0


class BrokerPosition(BaseModel):
    instrument_id: str
    qty: float
    avg_price: float


class BrokerAdapter(ABC):
    """発注・残高・建玉・約定照合の共通IF。"""

    broker_name: str

    @abstractmethod
    async def submit_order(self, req: OrderRequest) -> OrderResult: ...

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> None: ...

    @abstractmethod
    async def fetch_balances(self) -> list[Balance]: ...

    @abstractmethod
    async def fetch_positions(self) -> list[BrokerPosition]: ...

    @abstractmethod
    async def fetch_ticker(self, instrument_id: str) -> Ticker: ...
