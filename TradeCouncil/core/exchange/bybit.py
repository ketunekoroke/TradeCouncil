"""Bybit testnet アダプタ(ADR-0008)。

BrokerAdapter の実装(ccxt async)。**testnet 専用** — mainnet への発注経路は
コード上存在しない(environment は "testnet" のみ受理。絶対ルール3・BL-024 と整合)。

- API キー: BYBIT_TESTNET_API_KEY / BYBIT_TESTNET_API_SECRET(.env 経由)。
  欠落時は構築時に即エラー(fail-closed)
- 約定解決: 応答内 trades → fetch_order ポーリングの順で実約定(実手数料)を取得
- 現物の建玉は base 通貨残高から導出(avg_price は取得不可のため 0.0 —
  executor.reconcile は qty のみ比較。ADR-0008 既知の制約2)
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

from core.exchange.base import (
    Balance,
    BrokerAdapter,
    BrokerPosition,
    FillInfo,
    OrderRequest,
    OrderResult,
    Ticker,
)

_DUST = 1e-9  # 残高ノイズ(手数料端数等)を建玉とみなさない閾値


class BybitAdapter(BrokerAdapter):
    broker_name = "bybit_testnet"

    def __init__(
        self,
        symbol_map: dict[str, str],  # instrument_id → ccxt シンボル(例 "BTC/USDT")
        environment: str = "testnet",
        client: object | None = None,  # テスト用 DI(フェイク注入)
        fill_poll_attempts: int = 5,
        fill_poll_sec: float = 0.5,
    ) -> None:
        if environment != "testnet":
            raise ValueError(
                f"BybitAdapter は testnet 専用: {environment!r} は受理しない"
                "(mainnet への発注経路は存在しない — ADR-0008 §2)"
            )
        self._symbol_map = dict(symbol_map)
        self._fill_poll_attempts = fill_poll_attempts
        self._fill_poll_sec = fill_poll_sec
        if client is None:
            client = self._build_client()
        self._client = client

    @staticmethod
    def _build_client() -> object:
        # キー検査を ccxt import より先に行う(未インストール環境でも fail-closed が先)
        api_key = (os.environ.get("BYBIT_TESTNET_API_KEY") or "").strip()
        api_secret = (os.environ.get("BYBIT_TESTNET_API_SECRET") or "").strip()
        if not api_key or not api_secret:
            raise RuntimeError(
                "BYBIT_TESTNET_API_KEY / BYBIT_TESTNET_API_SECRET が未設定"
                "(.env に設定する — docs/setup/bybit-testnet-setup.md)"
            )
        import ccxt.async_support as ccxt_async  # 遅延 import

        client = ccxt_async.bybit({"apiKey": api_key, "secret": api_secret})
        client.set_sandbox_mode(True)  # testnet 強制(無条件)
        return client

    def _symbol(self, instrument_id: str) -> str:
        symbol = self._symbol_map.get(instrument_id)
        if symbol is None:
            raise KeyError(f"未登録の instrument: {instrument_id}")
        return symbol

    # ------------------------------------------------------------------

    async def submit_order(self, req: OrderRequest) -> OrderResult:
        symbol = self._symbol(req.instrument_id)
        params: dict = {}
        if req.idempotency_key:
            # 取引所側の二重発注防止(Bybit orderLinkId)。DB 側の冪等性と二重の防壁
            params["orderLinkId"] = req.idempotency_key
        try:
            order = await self._client.create_order(
                symbol, req.order_type, req.side, req.qty, params=params
            )
        except Exception as exc:  # 取引所拒否・通信失敗は rejected として監査に乗せる
            return OrderResult(
                broker_order_id="",
                status="rejected",
                reject_reason=f"{type(exc).__name__}: {exc}"[:200],
            )

        order_id = str(order.get("id", ""))
        fills = self._fills_from_trades(order.get("trades"))
        if not fills:
            fills = await self._poll_fills(order_id, symbol)
        return OrderResult(
            broker_order_id=order_id,
            status="filled" if fills else "submitted",
            fills=fills,
        )

    def _fills_from_trades(self, trades: object) -> list[FillInfo]:
        if not isinstance(trades, list):
            return []
        fills: list[FillInfo] = []
        for t in trades:
            qty = float(t.get("amount") or 0.0)
            if qty <= 0:
                continue
            fee = t.get("fee") or {}
            fills.append(
                FillInfo(
                    qty=qty,
                    price=float(t.get("price") or 0.0),
                    fee=float(fee.get("cost") or 0.0),
                    ts=self._ts(t.get("timestamp")),
                )
            )
        return fills

    async def _poll_fills(self, order_id: str, symbol: str) -> list[FillInfo]:
        """応答に約定が無い場合、fetch_order で確定を取りに行く(成行はほぼ即時)。"""
        for attempt in range(self._fill_poll_attempts):
            fetched = await self._client.fetch_order(order_id, symbol)
            filled = float(fetched.get("filled") or 0.0)
            if filled > 0:
                fee = fetched.get("fee") or {}
                return [
                    FillInfo(
                        qty=filled,
                        price=float(fetched.get("average") or fetched.get("price") or 0.0),
                        fee=float(fee.get("cost") or 0.0),
                        ts=self._ts(fetched.get("timestamp")),
                    )
                ]
            if attempt < self._fill_poll_attempts - 1 and self._fill_poll_sec > 0:
                await asyncio.sleep(self._fill_poll_sec)
        return []

    @staticmethod
    def _ts(ts_ms: object) -> datetime:
        if isinstance(ts_ms, (int, float)) and ts_ms > 0:
            return datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
        return datetime.now(UTC)

    # ------------------------------------------------------------------

    async def cancel_order(self, broker_order_id: str) -> None:
        # 現状 instrument 1つ運用のため代表シンボルで取り消す
        symbol = next(iter(self._symbol_map.values()))
        await self._client.cancel_order(broker_order_id, symbol)

    async def fetch_balances(self) -> list[Balance]:
        raw = await self._client.fetch_balance()
        totals: dict = raw.get("total") or {}
        return [
            Balance(broker=self.broker_name, currency=ccy, balance=float(amount))
            for ccy, amount in totals.items()
            if amount and float(amount) > 0
        ]

    async def fetch_positions(self) -> list[BrokerPosition]:
        """現物: symbol_map の base 通貨残高を建玉として導出する。"""
        raw = await self._client.fetch_balance()
        totals: dict = raw.get("total") or {}
        positions: list[BrokerPosition] = []
        for instrument_id, symbol in self._symbol_map.items():
            base = symbol.split("/")[0]
            qty = float(totals.get(base) or 0.0)
            if qty > _DUST:
                positions.append(
                    BrokerPosition(instrument_id=instrument_id, qty=qty, avg_price=0.0)
                )
        return positions

    async def fetch_ticker(self, instrument_id: str) -> Ticker:
        t = await self._client.fetch_ticker(self._symbol(instrument_id))
        ts_ms = t.get("timestamp")
        return Ticker(
            instrument_id=instrument_id,
            bid=float(t["bid"]),
            ask=float(t["ask"]),
            last=float(t["last"]),
            ts=self._ts(ts_ms),
        )
