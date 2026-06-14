"""OrderIntent.fx_rate_jpy(USDT 建て等の JPY 換算 — ADR-0008)のテスト。

リスク上限(P-02/P-03)は JPY 建てのため、instrument 通貨が JPY 以外の場合は
bot_runner が fx_rate_jpy を設定して notional を JPY 換算する。
price は instrument 通貨のまま(orders/fills の通貨整合を守る)。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.risk.errors import RiskRejection
from core.risk.guard import MarketContext, OrderIntent, RiskGuard
from tests.conftest import activate_required_policies


def _intent(**overrides) -> OrderIntent:
    kwargs = dict(
        bot_id="b1",
        decision_id="D-1",
        instrument_id="bybit_testnet.btc_usdt.spot",
        asset_class="crypto_spot",
        side="buy",
        qty=0.001,
        price=50_000.0,  # USDT
    )
    kwargs.update(overrides)
    return OrderIntent(**kwargs)


def _ctx(**overrides) -> MarketContext:
    kwargs = dict(
        equity_jpy=1_000_000.0,
        total_exposure_jpy=0.0,
        daily_pnl_jpy=0.0,
        week_peak_equity_jpy=1_000_000.0,
        bot_open_positions=0,
        data_age_sec=0.0,
        price_change_pct_1m=0.0,
        spread_bps=1.0,
    )
    kwargs.update(overrides)
    return MarketContext(**kwargs)


class TestNotionalConversion:
    def test_notional_jpy_applies_fx_rate(self) -> None:
        intent = _intent(fx_rate_jpy=165.0)
        assert intent.notional_jpy == pytest.approx(0.001 * 50_000.0 * 165.0)  # 8,250円

    def test_default_rate_is_1_backward_compatible(self) -> None:
        """JPY 建て(既存パス)は fx_rate_jpy 未指定 = 1.0 で従来どおり。"""
        intent = _intent()
        assert intent.fx_rate_jpy == 1.0
        assert intent.notional_jpy == pytest.approx(0.001 * 50_000.0)

    @pytest.mark.parametrize("bad_rate", [0.0, -1.0])
    def test_non_positive_rate_rejected(self, bad_rate: float) -> None:
        with pytest.raises(ValidationError):
            _intent(fx_rate_jpy=bad_rate)


class TestGuardUsesConvertedNotional:
    """est_max_loss_jpy なし = notional 全損とみなす経路で、換算が効くことを確認。"""

    @pytest.fixture
    def guard(self, registry) -> RiskGuard:
        # per_trade 上限 1% × equity 100万円 = 許容 10,000円
        activate_required_policies(
            registry,
            overrides={
                "P-03": {
                    "max_daily_loss_pct": 99.0,
                    "max_weekly_drawdown_pct": 99.0,
                    "per_trade_max_loss_pct": 1.0,
                    "max_total_exposure_pct": 999.0,
                    "per_bot_max_positions": 999,
                }
            },
        )
        return RiskGuard(registry=registry)

    def test_passes_under_limit_with_conversion(self, guard: RiskGuard) -> None:
        # 0.001 BTC × 50,000 USDT × 165 = 8,250円 < 10,000円 → 通過
        approved = guard.check(_intent(fx_rate_jpy=165.0), _ctx())
        assert approved.price == 50_000.0  # price は instrument 通貨のまま(換算しない)

    def test_rejected_over_limit_with_conversion(self, guard: RiskGuard) -> None:
        # 0.0015 BTC × 50,000 USDT × 165 = 12,375円 > 10,000円 → 拒否
        with pytest.raises(RiskRejection, match="PER_TRADE_LOSS"):
            guard.check(_intent(qty=0.0015, fx_rate_jpy=165.0), _ctx())

    def test_same_qty_without_conversion_would_pass(self, guard: RiskGuard) -> None:
        """換算しなければ通っていた注文(75円扱い)が、換算で正しく拒否される対照。"""
        approved = guard.check(_intent(qty=0.0015), _ctx())  # fx=1.0 → 75円
        assert approved.qty == 0.0015
