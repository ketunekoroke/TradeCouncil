"""BybitAdapter(core/exchange/bybit.py)のテスト。

実ネットワークには出ない: ccxt クライアントをフェイク注入(DI)して検査する。
設計(ADR-0008):
  - testnet 強制(mainnet 指定は ValueError = 発注経路が存在しない)
  - API キー欠落は構築時に即エラー(fail-closed)
  - 約定は応答内 trades → fetch_order フォールバックで解決し、実手数料を記録
  - 現物の建玉は base 通貨残高から導出(avg_price=0.0、reconcile は qty 比較のみ)
"""

from __future__ import annotations

import pytest

from core.exchange.base import OrderRequest
from core.exchange.bybit import BybitAdapter

SYMBOLS = {"bybit_testnet.btc_usdt.spot": "BTC/USDT"}


class FakeAsyncClient:
    """ccxt async bybit の必要メソッドだけ模したフェイク。"""

    def __init__(self) -> None:
        self.create_order_calls: list[tuple] = []
        self.create_order_result: dict | object = {"id": "EX-1", "status": "closed"}
        self.fetch_order_result: dict = {
            "id": "EX-1",
            "status": "closed",
            "filled": 0.001,
            "average": 50_000.0,
            "fee": {"cost": 0.05, "currency": "USDT"},
            "timestamp": 1_750_000_000_000,
        }
        self.balance: dict = {"total": {"USDT": 1_000.0, "BTC": 0.5, "ETH": 0.0}}
        self.ticker: dict = {
            "bid": 49_990.0,
            "ask": 50_010.0,
            "last": 50_000.0,
            "timestamp": 1_750_000_000_000,
        }
        self.cancel_calls: list[tuple] = []

    async def create_order(self, symbol, order_type, side, amount, params=None):
        self.create_order_calls.append((symbol, order_type, side, amount, params or {}))
        if isinstance(self.create_order_result, Exception):
            raise self.create_order_result
        return self.create_order_result

    async def fetch_order(self, order_id, symbol):
        return self.fetch_order_result

    async def fetch_balance(self):
        return self.balance

    async def fetch_ticker(self, symbol):
        return self.ticker

    async def cancel_order(self, order_id, symbol):
        self.cancel_calls.append((order_id, symbol))


@pytest.fixture
def fake() -> FakeAsyncClient:
    return FakeAsyncClient()


@pytest.fixture
def adapter(fake: FakeAsyncClient) -> BybitAdapter:
    return BybitAdapter(SYMBOLS, client=fake, fill_poll_attempts=2, fill_poll_sec=0.0)


def _req(side: str = "buy", qty: float = 0.001) -> OrderRequest:
    return OrderRequest(
        instrument_id="bybit_testnet.btc_usdt.spot",
        side=side,
        qty=qty,
        order_type="market",
        idempotency_key="IDEM-123",
    )


class TestFailClosed:
    def test_mainnet_is_rejected(self, fake: FakeAsyncClient) -> None:
        """mainnet への発注経路はコード上存在しない(ADR-0008 §2)。"""
        with pytest.raises(ValueError):
            BybitAdapter(SYMBOLS, environment="mainnet", client=fake)

    def test_missing_api_keys_fail_at_construction(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("BYBIT_TESTNET_API_KEY", raising=False)
        monkeypatch.delenv("BYBIT_TESTNET_API_SECRET", raising=False)
        with pytest.raises(RuntimeError, match="BYBIT_TESTNET_API_KEY"):
            BybitAdapter(SYMBOLS)  # client なし → キー必須

    async def test_unknown_instrument_is_rejected(self, adapter: BybitAdapter) -> None:
        req = OrderRequest(instrument_id="unknown.iid", side="buy", qty=1.0)
        with pytest.raises(KeyError):
            await adapter.submit_order(req)


class TestSubmitOrder:
    async def test_market_order_with_trades_in_response(
        self, adapter: BybitAdapter, fake: FakeAsyncClient
    ) -> None:
        fake.create_order_result = {
            "id": "EX-1",
            "status": "closed",
            "trades": [
                {
                    "amount": 0.001,
                    "price": 50_000.0,
                    "fee": {"cost": 0.05, "currency": "USDT"},
                    "timestamp": 1_750_000_000_000,
                }
            ],
        }
        result = await adapter.submit_order(_req())

        assert result.status == "filled"
        assert result.broker_order_id == "EX-1"
        assert len(result.fills) == 1
        assert result.fills[0].qty == 0.001
        assert result.fills[0].price == 50_000.0
        assert result.fills[0].fee == 0.05  # 実手数料(模擬の固定bpsでない)

        symbol, order_type, side, amount, params = fake.create_order_calls[0]
        assert (symbol, order_type, side, amount) == ("BTC/USDT", "market", "buy", 0.001)
        # 冪等性キーを取引所側の orderLinkId にも渡す(取引所側の二重発注防止)
        assert params.get("orderLinkId") == "IDEM-123"

    async def test_fetch_order_fallback_when_no_trades(
        self, adapter: BybitAdapter, fake: FakeAsyncClient
    ) -> None:
        fake.create_order_result = {"id": "EX-1", "status": "closed"}  # trades なし
        result = await adapter.submit_order(_req())
        assert result.status == "filled"
        assert len(result.fills) == 1
        assert result.fills[0].price == 50_000.0
        assert result.fills[0].fee == 0.05

    async def test_partial_fills_are_all_recorded(
        self, adapter: BybitAdapter, fake: FakeAsyncClient
    ) -> None:
        fake.create_order_result = {
            "id": "EX-1",
            "status": "closed",
            "trades": [
                {"amount": 0.0006, "price": 50_000.0, "fee": {"cost": 0.03}, "timestamp": 1_750_000_000_000},
                {"amount": 0.0004, "price": 50_100.0, "fee": {"cost": 0.02}, "timestamp": 1_750_000_001_000},
            ],
        }
        result = await adapter.submit_order(_req(qty=0.001))
        assert result.status == "filled"
        assert [f.qty for f in result.fills] == [0.0006, 0.0004]
        assert sum(f.fee for f in result.fills) == pytest.approx(0.05)

    async def test_exchange_error_returns_rejected(
        self, adapter: BybitAdapter, fake: FakeAsyncClient
    ) -> None:
        """取引所エラーは rejected として記録に乗せる(ループは継続できる)。"""
        fake.create_order_result = RuntimeError("bybit InsufficientFunds")
        result = await adapter.submit_order(_req())
        assert result.status == "rejected"
        assert "InsufficientFunds" in (result.reject_reason or "")

    async def test_unfilled_after_polling_is_submitted(
        self, adapter: BybitAdapter, fake: FakeAsyncClient
    ) -> None:
        fake.create_order_result = {"id": "EX-1", "status": "open"}
        fake.fetch_order_result = {"id": "EX-1", "status": "open", "filled": 0.0}
        result = await adapter.submit_order(_req())
        assert result.status == "submitted"
        assert result.fills == []


class TestAccountState:
    async def test_fetch_balances_skips_zero(self, adapter: BybitAdapter) -> None:
        balances = await adapter.fetch_balances()
        by_ccy = {b.currency: b.balance for b in balances}
        assert by_ccy == {"USDT": 1_000.0, "BTC": 0.5}  # ETH(0)は出ない
        assert all(b.broker == "bybit_testnet" for b in balances)

    async def test_positions_derived_from_base_balance(self, adapter: BybitAdapter) -> None:
        positions = await adapter.fetch_positions()
        assert len(positions) == 1
        pos = positions[0]
        assert pos.instrument_id == "bybit_testnet.btc_usdt.spot"
        assert pos.qty == 0.5
        assert pos.avg_price == 0.0  # 取引所から取得不可(ADR-0008 既知の制約2)

    async def test_no_position_when_base_balance_zero(
        self, adapter: BybitAdapter, fake: FakeAsyncClient
    ) -> None:
        fake.balance = {"total": {"USDT": 1_000.0, "BTC": 0.0}}
        assert await adapter.fetch_positions() == []

    async def test_fetch_ticker(self, adapter: BybitAdapter) -> None:
        ticker = await adapter.fetch_ticker("bybit_testnet.btc_usdt.spot")
        assert ticker.bid == 49_990.0
        assert ticker.ask == 50_010.0
        assert ticker.last == 50_000.0
        assert ticker.spread_bps == pytest.approx(4.0, rel=0.01)  # 実スプレッド

    async def test_cancel_order_passes_symbol(
        self, adapter: BybitAdapter, fake: FakeAsyncClient
    ) -> None:
        await adapter.cancel_order("EX-1")
        assert fake.cancel_calls == [("EX-1", "BTC/USDT")]
