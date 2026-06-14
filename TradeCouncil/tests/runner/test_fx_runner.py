"""bot_runner の JPY 換算(ADR-0008)と FxConfig のテスト。

USDT 建て instrument の場合:
  - MarketContext(equity/exposure/daily_pnl)は JPY 換算される
  - OrderIntent.fx_rate_jpy が設定される(price は instrument 通貨のまま)
  - 戦略の est_max_loss(instrument 通貨)も JPY 換算される
  - data_age_sec はフィードの実測値が渡る
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from core.config import FxConfig, PaperConfig, RandomWalkConfig
from core.exchange.base import Bar, Ticker
from core.exchange.feeds import RandomWalkFeed
from core.exchange.paper_crypto import PaperCryptoAdapter
from core.execution.executor import Executor
from core.market.instrument import InstrumentSpec
from core.risk.guard import MarketContext, OrderIntent, RiskGuard
from core.runner.bot_runner import BotConfigDoc, BotRunner
from bots.dummy_random_walk import DummyRandomWalk
from tests.conftest import activate_required_policies

IID = "bybit_testnet.btc_usdt.spot"
RATE = 165.0


class TestFxConfig:
    def test_jpy_is_identity(self) -> None:
        assert FxConfig(usdjpy_rate=165.0).rate_to_jpy("JPY") == 1.0

    @pytest.mark.parametrize("ccy", ["USDT", "USD"])
    def test_usd_like_uses_configured_rate(self, ccy: str) -> None:
        assert FxConfig(usdjpy_rate=165.0).rate_to_jpy(ccy) == 165.0

    def test_unconfigured_rate_fails_closed(self) -> None:
        with pytest.raises(ValueError, match="usdjpy_rate"):
            FxConfig().rate_to_jpy("USDT")  # 未設定なら換算不可(fail-closed)

    def test_unsupported_currency_fails_closed(self) -> None:
        with pytest.raises(ValueError, match="EUR"):
            FxConfig(usdjpy_rate=165.0).rate_to_jpy("EUR")

    @pytest.mark.parametrize("bad", [0.0, -165.0, 0.5])
    def test_invalid_rate_rejected(self, bad: float) -> None:
        """0以下に加え、1未満も誤設定(リスク上限が甘くなる方向)として拒否する。"""
        with pytest.raises(ValidationError):
            FxConfig(usdjpy_rate=bad)


class SpyGuard(RiskGuard):
    """check に渡った intent / ctx を記録する(検証用)。"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.captured: list[tuple[OrderIntent, MarketContext]] = []

    def check(self, intent: OrderIntent, ctx: MarketContext):
        self.captured.append((intent, ctx))
        return super().check(intent, ctx)


class FakeAgedFeed:
    """data_age_sec の配線確認用フィード(PriceFeed Protocol)。"""

    bar_interval_sec = 60

    def __init__(self, instrument_id: str) -> None:
        self._iid = instrument_id
        self._price = 50_000.0
        self._n = 0

    def next_bar(self) -> Bar:
        self._n += 1
        ts = datetime(2026, 1, 1, 0, self._n, tzinfo=UTC)
        return Bar(
            instrument_id=self._iid, timeframe="1m", ts=ts,
            o=self._price, h=self._price, l=self._price, c=self._price,
        )

    def current_ticker(self) -> Ticker:
        return Ticker(
            instrument_id=self._iid,
            bid=self._price - 1, ask=self._price + 1, last=self._price,
            ts=datetime(2026, 1, 1, tzinfo=UTC),
        )

    def data_age_sec(self) -> float:
        return 42.0


def _build(registry, session_factory, kill_flag: Path, *, feed=None) -> tuple[BotRunner, SpyGuard]:
    bot_config = BotConfigDoc(
        bot_id="bybit_rw",
        strategy="dummy_random_walk",
        instrument_id=IID,
        params={"order_qty": 0.001, "hold_bars": 3},
    )
    instrument = InstrumentSpec(
        instrument_id=IID,
        asset_class="crypto_spot",
        broker="bybit_testnet",
        symbol="BTC/USDT",
        currency="USDT",
        tick_size=0.01,
        lot_size=0.000001,
        session_calendar="always",
        margin_rule="cash",
    )
    feed = feed or RandomWalkFeed(IID, RandomWalkConfig(seed=7, start_price=50_000.0))
    adapter = PaperCryptoAdapter(  # 執行は模擬でよい(換算の検証が目的)
        ticker_provider=lambda _iid: feed.current_ticker(),
        config=PaperConfig(initial_balance_jpy=10_000.0),  # ここでは 10,000 USDT として使う
        currency="USDT",
    )
    guard = SpyGuard(registry=registry, session_factory=session_factory, kill_flag_path=kill_flag)
    runner = BotRunner(
        bot_config=bot_config,
        instrument=instrument,
        strategy=DummyRandomWalk("bybit_rw", bot_config.params),
        feed=feed,
        adapter=adapter,
        guard=guard,
        executor=Executor(adapter, session_factory),
        session_factory=session_factory,
        kill_flag_path=kill_flag,
        bar_sleep_sec=None,
        fx_rate_jpy=RATE,
    )
    return runner, guard


@pytest.fixture
def kill_flag(tmp_path: Path) -> Path:
    return tmp_path / "run" / "KILL"


class TestRunnerFxConversion:
    async def test_context_and_intent_converted(
        self, registry, db_session_factory, kill_flag
    ) -> None:
        activate_required_policies(registry)
        runner, guard = _build(registry, db_session_factory, kill_flag)
        await runner.run(max_bars=2)  # 1バー目で dummy が買いを出す

        assert guard.captured, "注文意図が guard に届いていない"
        intent, ctx = guard.captured[0]
        # OrderIntent: fx_rate_jpy が設定され price は USDT のまま
        assert intent.fx_rate_jpy == RATE
        assert intent.price < 100_000.0  # 50,000 USDT 近辺(JPY 換算されていない)
        # est_max_loss(戦略は USDT 建てで見積もる)も JPY 換算されている
        expected_est_usdt = 0.001 * intent.price * 0.01
        assert intent.est_max_loss_jpy == pytest.approx(expected_est_usdt * RATE)
        # MarketContext: equity = USDT 残高 × レート(建玉なし時点)
        assert ctx.equity_jpy == pytest.approx(10_000.0 * RATE)

    async def test_exposure_converted_after_position(
        self, registry, db_session_factory, kill_flag
    ) -> None:
        activate_required_policies(registry)
        runner, guard = _build(registry, db_session_factory, kill_flag)
        await runner.run(max_bars=4)  # 買い → 保有 → 売り(hold_bars=3)

        # 建玉保有中の ctx(2回目以降の capture)で exposure が JPY 換算されている
        held = [c for _i, c in guard.captured if c.total_exposure_jpy > 0]
        assert held, "建玉保有中のコンテキストがない"
        # 0.001 BTC × ~50,000 USDT × 165 ≈ 8,250円(桁が JPY 換算であること)
        assert held[0].total_exposure_jpy == pytest.approx(0.001 * 50_000.0 * RATE, rel=0.1)

    async def test_data_age_passed_from_feed(
        self, registry, db_session_factory, kill_flag
    ) -> None:
        activate_required_policies(registry)
        runner, guard = _build(
            registry, db_session_factory, kill_flag, feed=FakeAgedFeed(IID)
        )
        await runner.run(max_bars=1)
        _intent, ctx = guard.captured[0]
        assert ctx.data_age_sec == 42.0


class TestBackwardCompatibility:
    async def test_jpy_runner_unchanged(self, registry, db_session_factory, kill_flag) -> None:
        """既存の JPY ペーパー構成(fx_rate_jpy 未指定 = 1.0)は従来どおり。"""
        from tests.e2e.test_paper_bot import _build_runner

        activate_required_policies(registry)
        runner = _build_runner(registry, db_session_factory, kill_flag)
        await runner.run(max_bars=5)
        assert runner.orders_submitted > 0  # 経路が壊れていない
