"""executor のテスト(冪等性・decision_id 必須・約定記録・突合)。"""

from __future__ import annotations

import pytest

from core.config import PaperConfig, RandomWalkConfig
from core.db.models import Fill, Order, PnlDaily, Position, TradeDecision
from core.exchange.feeds import RandomWalkFeed
from core.exchange.paper_crypto import PaperCryptoAdapter
from core.execution.decisions import record_trade_decision
from core.execution.executor import Executor
from core.risk.guard import _APPROVAL_TOKEN, RiskApprovedOrder

INSTRUMENT = "paper.btc_jpy.spot"


def _approved(decision_id: str, side: str = "buy", qty: float = 0.001) -> RiskApprovedOrder:
    # テストでは正規トークンを使って承認済み注文を作る(risk_guard 相当)
    return RiskApprovedOrder(
        _approval_token=_APPROVAL_TOKEN,
        bot_id="dummy_rw",
        decision_id=decision_id,
        instrument_id=INSTRUMENT,
        side=side,
        qty=qty,
        price=10_000_000.0,
        order_type="market",
    )


@pytest.fixture
def feed() -> RandomWalkFeed:
    return RandomWalkFeed(INSTRUMENT, RandomWalkConfig(seed=42))


@pytest.fixture
def adapter(feed) -> PaperCryptoAdapter:
    return PaperCryptoAdapter(
        ticker_provider=lambda _iid: feed.current_ticker(),
        config=PaperConfig(fee_bps=10.0, slippage_bps=5.0, initial_balance_jpy=1_000_000.0),
    )


@pytest.fixture
def executor(adapter, db_session_factory) -> Executor:
    return Executor(adapter, db_session_factory)


@pytest.fixture
def decision_id(db_session_factory) -> str:
    return record_trade_decision(
        db_session_factory,
        bot_id="dummy_rw",
        source_type="strategy_rule",
        rationale={"rule": "test", "bar_close": 10_000_000.0},
    )


class TestIdempotency:
    async def test_same_decision_submits_once(self, executor, decision_id, db_session_factory):
        o1 = await executor.submit(_approved(decision_id))
        o2 = await executor.submit(_approved(decision_id))
        assert o1.order_id == o2.order_id
        with db_session_factory() as s:
            assert s.query(Order).count() == 1
            assert s.query(Fill).count() == 1

    async def test_different_decisions_submit_separately(
        self, executor, db_session_factory
    ):
        d1 = record_trade_decision(db_session_factory, "dummy_rw", "strategy_rule", {"n": 1})
        d2 = record_trade_decision(db_session_factory, "dummy_rw", "strategy_rule", {"n": 2})
        await executor.submit(_approved(d1))
        await executor.submit(_approved(d2))
        with db_session_factory() as s:
            assert s.query(Order).count() == 2


class TestPathEnforcement:
    async def test_non_approved_type_raises(self, executor):
        with pytest.raises(TypeError, match="RiskApprovedOrder"):
            await executor.submit({"side": "buy"})  # type: ignore[arg-type]

    def test_approved_order_requires_guard_token(self):
        with pytest.raises(PermissionError):
            RiskApprovedOrder(
                bot_id="x",
                decision_id="TD-x",
                instrument_id=INSTRUMENT,
                side="buy",
                qty=0.001,
                price=1.0,
                order_type="market",
            )


class TestRecording:
    async def test_fill_position_pnl_recorded(self, executor, decision_id, db_session_factory):
        await executor.submit(_approved(decision_id))
        with db_session_factory() as s:
            order = s.query(Order).one()
            assert order.status == "filled"
            assert order.decision_id == decision_id
            assert order.exchange_order_id is not None
            fill = s.query(Fill).one()
            assert fill.fee > 0
            pos = s.get(Position, ("dummy_rw", INSTRUMENT))
            assert pos is not None and pos.qty == pytest.approx(0.001)
            pnl = s.query(PnlDaily).one()
            assert pnl.fees == pytest.approx(fill.fee)

    async def test_round_trip_realizes_pnl(self, executor, db_session_factory):
        d_buy = record_trade_decision(db_session_factory, "dummy_rw", "strategy_rule", {"n": 1})
        d_sell = record_trade_decision(db_session_factory, "dummy_rw", "strategy_rule", {"n": 2})
        await executor.submit(_approved(d_buy, side="buy"))
        await executor.submit(_approved(d_sell, side="sell"))
        with db_session_factory() as s:
            assert s.get(Position, ("dummy_rw", INSTRUMENT)) is None  # 全量決済
            pnl = s.query(PnlDaily).one()
            # 同価格往復ならスリッページ+スプレッド分だけ実現損
            assert pnl.realized < 0
            assert pnl.fees > 0

    async def test_traceability_chain(self, executor, decision_id, db_session_factory):
        """order → trade_decision → 根拠(rationale)まで遡及できる(FR-4.4)。"""
        await executor.submit(_approved(decision_id))
        with db_session_factory() as s:
            order = s.query(Order).one()
            td = s.get(TradeDecision, order.decision_id)
            assert td is not None
            assert td.source_type == "strategy_rule"
            assert td.rationale_json["rule"] == "test"


class TestBrokerRejection:
    async def test_insufficient_funds_recorded_as_failed(
        self, feed, db_session_factory
    ):
        poor_adapter = PaperCryptoAdapter(
            ticker_provider=lambda _iid: feed.current_ticker(),
            config=PaperConfig(initial_balance_jpy=100.0),
        )
        executor = Executor(poor_adapter, db_session_factory)
        d = record_trade_decision(db_session_factory, "dummy_rw", "strategy_rule", {})
        order = await executor.submit(_approved(d))
        assert order.status == "failed"
        assert order.reject_reason == "INSUFFICIENT_FUNDS"


class TestReconcile:
    async def test_reconcile_detects_mismatch(self, executor, adapter, db_session_factory):
        d = record_trade_decision(db_session_factory, "dummy_rw", "strategy_rule", {})
        await executor.submit(_approved(d))
        assert await executor.reconcile("dummy_rw") == []
        # DB側の建玉を壊して不一致を検出
        with db_session_factory() as s:
            pos = s.get(Position, ("dummy_rw", INSTRUMENT))
            pos.qty = 999.0
            s.commit()
        mismatches = await executor.reconcile("dummy_rw")
        assert len(mismatches) == 1
        assert "数量不一致" in mismatches[0]


class TestFeedDeterminism:
    def test_same_seed_same_bars(self):
        f1 = RandomWalkFeed(INSTRUMENT, RandomWalkConfig(seed=7))
        f2 = RandomWalkFeed(INSTRUMENT, RandomWalkConfig(seed=7))
        bars1 = [f1.next_bar().c for _ in range(10)]
        bars2 = [f2.next_bar().c for _ in range(10)]
        assert bars1 == bars2

    def test_paper_fill_includes_slippage_and_fee(self, feed):
        import asyncio

        adapter = PaperCryptoAdapter(
            ticker_provider=lambda _iid: feed.current_ticker(),
            config=PaperConfig(fee_bps=10.0, slippage_bps=5.0, initial_balance_jpy=10**9),
        )
        from core.exchange.base import OrderRequest

        ticker = feed.current_ticker()
        result = asyncio.run(
            adapter.submit_order(
                OrderRequest(instrument_id=INSTRUMENT, side="buy", qty=0.001)
            )
        )
        fill = result.fills[0]
        assert fill.price > ticker.ask  # 不利方向スリッページ
        assert fill.fee == pytest.approx(0.001 * fill.price * 10 / 10_000)
