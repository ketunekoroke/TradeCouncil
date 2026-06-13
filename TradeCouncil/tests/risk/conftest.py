"""risk テスト用フィクスチャ・ファクトリ。"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.risk.guard import MarketContext, OrderIntent, RiskGuard


@pytest.fixture
def kill_flag(tmp_path: Path) -> Path:
    return tmp_path / "run" / "KILL"


@pytest.fixture
def guard(registry, db_session_factory, kill_flag) -> RiskGuard:
    return RiskGuard(
        registry=registry,
        session_factory=db_session_factory,
        kill_flag_path=kill_flag,
    )


@pytest.fixture(autouse=True)
def seed_trade_decision(db_session_factory):
    """orders.decision_id の FK 先(根拠レコード)を用意する。

    実運用では bot_runner が risk_guard より先に trade_decisions を起票する。
    """
    from core.db.models import TradeDecision

    with db_session_factory() as s:
        s.add(
            TradeDecision(
                decision_id="TD-test-0001",
                bot_id="dummy_rw",
                source_type="strategy_rule",
                rationale_json={"test": True},
            )
        )
        s.commit()


def make_intent(**overrides) -> OrderIntent:
    defaults = dict(
        bot_id="dummy_rw",
        decision_id="TD-test-0001",
        instrument_id="paper.btc_jpy.spot",
        asset_class="crypto_spot",
        side="buy",
        qty=0.001,
        price=10_000_000.0,
        order_type="market",
        est_max_loss_jpy=None,
        reduces_position=False,
    )
    defaults.update(overrides)
    return OrderIntent(**defaults)


def make_ctx(**overrides) -> MarketContext:
    """既定 = 全チェックを通過する健全な市場・口座状態(テスト値)。"""
    defaults = dict(
        equity_jpy=1_000_000.0,
        total_exposure_jpy=0.0,
        daily_pnl_jpy=0.0,
        week_peak_equity_jpy=1_000_000.0,
        bot_open_positions=0,
        data_age_sec=1.0,
        price_change_pct_1m=0.0,
        spread_bps=1.0,
    )
    defaults.update(overrides)
    return MarketContext(**defaults)
