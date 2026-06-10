"""ペーパー(模擬)暗号資産アダプタ — Phase 0 の唯一のアダプタ実装。

約定モデル: ticker 価格にスリッページ bps を不利方向へ加算し、手数料 bps を徴収する
(config/system.yaml の paper セクション = 技術設定)。
取引所側の口座状態(残高・建玉)をメモリに保持し、fetch_* で返す
(再起動時のDB突合テストに使う)。
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from core.config import PaperConfig
from core.exchange.base import (
    Balance,
    BrokerAdapter,
    BrokerPosition,
    FillInfo,
    OrderRequest,
    OrderResult,
    Ticker,
)


class PaperCryptoAdapter(BrokerAdapter):
    broker_name = "paper"

    def __init__(
        self,
        ticker_provider: Callable[[str], Ticker],
        config: PaperConfig | None = None,
        currency: str = "JPY",
    ) -> None:
        self._ticker_provider = ticker_provider
        self._config = config or PaperConfig()
        self._currency = currency
        self._cash: float = self._config.initial_balance_jpy
        self._positions: dict[str, BrokerPosition] = {}

    async def submit_order(self, req: OrderRequest) -> OrderResult:
        ticker = self._ticker_provider(req.instrument_id)
        slip = self._config.slippage_bps / 10_000
        if req.side == "buy":
            price = ticker.ask * (1 + slip)
        else:
            price = ticker.bid * (1 - slip)
        notional = req.qty * price
        fee = notional * self._config.fee_bps / 10_000

        if req.side == "buy" and notional + fee > self._cash:
            return OrderResult(
                broker_order_id=f"PB-{uuid.uuid4().hex[:10]}",
                status="rejected",
                reject_reason="INSUFFICIENT_FUNDS",
            )
        pos = self._positions.get(req.instrument_id)
        if req.side == "sell" and (pos is None or pos.qty < req.qty):
            return OrderResult(
                broker_order_id=f"PB-{uuid.uuid4().hex[:10]}",
                status="rejected",
                reject_reason="INSUFFICIENT_POSITION",
            )

        # 約定処理(現物・全量即時約定)
        if req.side == "buy":
            self._cash -= notional + fee
            if pos is None:
                self._positions[req.instrument_id] = BrokerPosition(
                    instrument_id=req.instrument_id, qty=req.qty, avg_price=price
                )
            else:
                total_qty = pos.qty + req.qty
                avg = (pos.qty * pos.avg_price + req.qty * price) / total_qty
                self._positions[req.instrument_id] = BrokerPosition(
                    instrument_id=req.instrument_id, qty=total_qty, avg_price=avg
                )
        else:
            self._cash += notional - fee
            assert pos is not None
            remaining = pos.qty - req.qty
            if remaining <= 0:
                self._positions.pop(req.instrument_id, None)
            else:
                self._positions[req.instrument_id] = BrokerPosition(
                    instrument_id=req.instrument_id, qty=remaining, avg_price=pos.avg_price
                )

        return OrderResult(
            broker_order_id=f"PB-{uuid.uuid4().hex[:10]}",
            status="filled",
            fills=[FillInfo(qty=req.qty, price=price, fee=fee, ts=datetime.now(UTC))],
        )

    async def cancel_order(self, broker_order_id: str) -> None:
        # 即時約定モデルのためキャンセル対象は存在しない
        return None

    async def fetch_balances(self) -> list[Balance]:
        return [Balance(broker=self.broker_name, currency=self._currency, balance=self._cash)]

    async def fetch_positions(self) -> list[BrokerPosition]:
        return list(self._positions.values())

    async def fetch_ticker(self, instrument_id: str) -> Ticker:
        return self._ticker_provider(instrument_id)
