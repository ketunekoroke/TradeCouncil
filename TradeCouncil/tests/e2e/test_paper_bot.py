"""E2E テスト: ペーパーBOTの全経路(Phase 0 DoD の確認)。

① ポリシーなしで N バー回す → 注文はすべて rejected(fail-closed の実機確認)
② 正規の決裁フローでポリシーを active 化 → 全注文が
   order → trade_decision → 根拠 → candle まで遡及可能
③ キルスイッチでループが停止する
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.config import PaperConfig, RandomWalkConfig
from core.db.models import Candle, Fill, Heartbeat, Order, TradeDecision
from core.exchange.feeds import RandomWalkFeed
from core.exchange.paper_crypto import PaperCryptoAdapter
from core.execution.executor import Executor
from core.market.instrument import InstrumentSpec
from core.risk import kill_switch
from core.risk.guard import RiskGuard
from core.runner.bot_runner import BotConfigDoc, BotRunner
from bots.dummy_random_walk import DummyRandomWalk
from tests.conftest import activate_required_policies

INSTRUMENT_ID = "paper.btc_jpy.spot"


def _build_runner(registry, session_factory, kill_flag: Path) -> BotRunner:
    bot_config = BotConfigDoc(
        bot_id="dummy_rw",
        strategy="dummy_random_walk",
        instrument_id=INSTRUMENT_ID,
        params={"order_qty": 0.001, "hold_bars": 3},
    )
    instrument = InstrumentSpec(
        instrument_id=INSTRUMENT_ID,
        asset_class="crypto_spot",
        broker="paper",
        symbol="BTC_JPY",
        currency="JPY",
        tick_size=1,
        lot_size=0.0001,
        session_calendar="always",
        margin_rule="cash",
    )
    feed = RandomWalkFeed(INSTRUMENT_ID, RandomWalkConfig(seed=123))
    adapter = PaperCryptoAdapter(
        ticker_provider=lambda _iid: feed.current_ticker(),
        config=PaperConfig(initial_balance_jpy=1_000_000.0),
    )
    guard = RiskGuard(
        registry=registry, session_factory=session_factory, kill_flag_path=kill_flag
    )
    executor = Executor(adapter, session_factory)
    return BotRunner(
        bot_config=bot_config,
        instrument=instrument,
        strategy=DummyRandomWalk("dummy_rw", bot_config.params),
        feed=feed,
        adapter=adapter,
        guard=guard,
        executor=executor,
        session_factory=session_factory,
        kill_flag_path=kill_flag,
        bar_sleep_sec=None,  # テストはスリープなしで高速実行
    )


@pytest.fixture
def kill_flag(tmp_path: Path) -> Path:
    return tmp_path / "run" / "KILL"


class TestFailClosedEndToEnd:
    async def test_no_policy_no_trade(self, registry, db_session_factory, kill_flag):
        """【DoD】未決裁領域での発注拒否を全経路で確認する。"""
        runner = _build_runner(registry, db_session_factory, kill_flag)
        await runner.run(max_bars=20)

        assert runner.bars_processed == 20
        assert runner.orders_submitted == 0
        assert runner.orders_rejected > 0
        with db_session_factory() as s:
            orders = s.query(Order).all()
            assert len(orders) > 0
            assert all(o.status == "rejected" for o in orders)
            assert all(o.reject_reason.startswith("POLICY_MISSING") for o in orders)
            assert s.query(Fill).count() == 0  # 約定はゼロ


class TestFullChainWithPolicies:
    async def test_orders_traceable_to_rationale(
        self, registry, db_session_factory, kill_flag
    ):
        """決裁後は全注文が decision_id → 根拠 → 一次データへ遡及できる。"""
        activate_required_policies(registry)
        runner = _build_runner(registry, db_session_factory, kill_flag)
        await runner.run(max_bars=30)

        assert runner.orders_submitted > 0
        with db_session_factory() as s:
            filled = s.query(Order).filter(Order.status == "filled").all()
            assert len(filled) == runner.orders_submitted
            for order in filled:
                td = s.get(TradeDecision, order.decision_id)
                assert td is not None, "根拠のない注文が存在する"
                assert td.rationale_json["rule"] == "dummy_fixed_cycle"
                # source_ref から一次データ(candle)へ遡及
                assert td.source_ref.startswith(f"candle:{INSTRUMENT_ID}:")
            assert s.query(Candle).count() == 30  # 全バーが保存されている
            # heartbeat が記録されている(高速ループでは同一時刻はupsertされる)
            assert (
                s.query(Heartbeat).filter(Heartbeat.component == "bot:dummy_rw").count()
                >= 1
            )

    async def test_buy_and_sell_both_executed(self, registry, db_session_factory, kill_flag):
        """固定サイクル戦略で売り買い両経路が通る。"""
        activate_required_policies(registry)
        runner = _build_runner(registry, db_session_factory, kill_flag)
        await runner.run(max_bars=30)
        with db_session_factory() as s:
            sides = {o.side for o in s.query(Order).filter(Order.status == "filled")}
        assert sides == {"buy", "sell"}


class TestKillSwitchStopsLoop:
    async def test_kill_flag_stops_runner(self, registry, db_session_factory, kill_flag):
        activate_required_policies(registry)
        runner = _build_runner(registry, db_session_factory, kill_flag)
        kill_switch.activate(path=kill_flag)
        await runner.run(max_bars=10)
        assert runner.bars_processed == 0  # 1バーも処理せず停止
