"""各リスク上限の境界値テスト(上限ちょうど = 可 / 超過 = 拒否)。

値はすべてテスト用ポリシー(conftest)から差し替える。
"""

from __future__ import annotations

import pytest

from core.risk.errors import RiskRejection
from core.risk.guard import RiskApprovedOrder
from tests.conftest import TEST_POLICY_VALUES, activate_required_policies
from tests.risk.conftest import make_ctx, make_intent


def _activate(registry, policy_id: str, **value_overrides):
    value = dict(TEST_POLICY_VALUES[policy_id])
    value.update(value_overrides)
    activate_required_policies(registry, overrides={policy_id: value})


class TestStaleDataAndCircuitBreaker:
    def test_stale_data_rejects(self, guard, registry):
        _activate(registry, "P-04", stale_data_sec=90)
        guard.check(make_intent(), make_ctx(data_age_sec=90.0))  # ちょうど = 可
        with pytest.raises(RiskRejection) as ei:
            guard.check(make_intent(), make_ctx(data_age_sec=90.1))
        assert ei.value.reason_code == "STALE_DATA"

    def test_price_jump_circuit_breaker(self, guard, registry):
        _activate(registry, "P-04", cb_price_jump_pct_1m=5.0)
        guard.check(make_intent(), make_ctx(price_change_pct_1m=5.0))
        for jump in (5.1, -5.1):
            with pytest.raises(RiskRejection) as ei:
                guard.check(make_intent(), make_ctx(price_change_pct_1m=jump))
            assert ei.value.reason_code == "CIRCUIT_BREAKER_PRICE_JUMP"

    def test_spread_circuit_breaker(self, guard, registry):
        _activate(registry, "P-04", cb_max_spread_bps=30)
        guard.check(make_intent(), make_ctx(spread_bps=30.0))
        with pytest.raises(RiskRejection) as ei:
            guard.check(make_intent(), make_ctx(spread_bps=30.5))
        assert ei.value.reason_code == "CIRCUIT_BREAKER_SPREAD"


class TestLossLimits:
    def test_per_trade_loss_with_estimate(self, guard, registry):
        _activate(registry, "P-03", per_trade_max_loss_pct=1.0)
        ctx = make_ctx(equity_jpy=1_000_000.0)
        # 想定最大損失 1% = 10,000円 ちょうど → 可
        guard.check(make_intent(est_max_loss_jpy=10_000.0, qty=0.001), ctx)
        with pytest.raises(RiskRejection) as ei:
            guard.check(make_intent(est_max_loss_jpy=10_001.0, qty=0.001), ctx)
        assert ei.value.reason_code == "PER_TRADE_LOSS"

    def test_per_trade_loss_without_estimate_uses_full_notional(self, guard, registry):
        """損失見積りが無い注文は想定元本全額を損失と見なす(保守的 = fail-closed)。"""
        _activate(registry, "P-03", per_trade_max_loss_pct=1.0)
        ctx = make_ctx(equity_jpy=1_000_000.0)
        # notional = 0.002 * 10,000,000 = 20,000円 > 10,000円 → 拒否
        with pytest.raises(RiskRejection) as ei:
            guard.check(make_intent(qty=0.002, est_max_loss_jpy=None), ctx)
        assert ei.value.reason_code == "PER_TRADE_LOSS"
        # notional = 0.001 * 10,000,000 = 10,000円 = ちょうど → 可
        guard.check(make_intent(qty=0.001, est_max_loss_jpy=None), ctx)

    def test_daily_loss_limit_blocks_new_orders(self, guard, registry):
        _activate(registry, "P-03", max_daily_loss_pct=2.0)
        equity = 1_000_000.0
        guard.check(make_intent(), make_ctx(equity_jpy=equity, daily_pnl_jpy=-20_000.0))
        with pytest.raises(RiskRejection) as ei:
            guard.check(
                make_intent(), make_ctx(equity_jpy=equity, daily_pnl_jpy=-20_001.0)
            )
        assert ei.value.reason_code == "DAILY_LOSS_LIMIT"

    def test_daily_profit_never_blocks(self, guard, registry):
        _activate(registry, "P-03", max_daily_loss_pct=2.0)
        guard.check(make_intent(), make_ctx(daily_pnl_jpy=+999_999.0))

    def test_weekly_drawdown_blocks(self, guard, registry):
        _activate(registry, "P-03", max_weekly_drawdown_pct=5.0)
        # ピーク100万 → 95万(DD 5.0%) = ちょうど → 可
        guard.check(
            make_intent(),
            make_ctx(week_peak_equity_jpy=1_000_000.0, equity_jpy=950_000.0),
        )
        with pytest.raises(RiskRejection) as ei:
            guard.check(
                make_intent(),
                make_ctx(week_peak_equity_jpy=1_000_000.0, equity_jpy=949_000.0),
            )
        assert ei.value.reason_code == "WEEKLY_DRAWDOWN"


class TestExposureAndPositions:
    def test_total_exposure_limit(self, guard, registry):
        _activate(registry, "P-03", max_total_exposure_pct=60.0)
        ctx = make_ctx(equity_jpy=1_000_000.0, total_exposure_jpy=590_000.0)
        # 新規 10,000円 → 合計 600,000円 = 60% ちょうど → 可
        guard.check(make_intent(qty=0.001, est_max_loss_jpy=1.0), ctx)
        ctx2 = make_ctx(equity_jpy=1_000_000.0, total_exposure_jpy=595_000.0)
        with pytest.raises(RiskRejection) as ei:
            guard.check(make_intent(qty=0.001, est_max_loss_jpy=1.0), ctx2)
        assert ei.value.reason_code == "EXPOSURE_LIMIT"

    def test_max_positions_per_bot(self, guard, registry):
        _activate(registry, "P-03", per_bot_max_positions=3)
        guard.check(
            make_intent(est_max_loss_jpy=1.0), make_ctx(bot_open_positions=2)
        )  # 3つ目 → 可
        with pytest.raises(RiskRejection) as ei:
            guard.check(
                make_intent(est_max_loss_jpy=1.0), make_ctx(bot_open_positions=3)
            )
        assert ei.value.reason_code == "MAX_POSITIONS"

    def test_reducing_order_bypasses_position_count(self, guard, registry):
        """決済方向の注文はポジション数上限の対象外(防御は妨げない)。"""
        _activate(registry, "P-03", per_bot_max_positions=1)
        guard.check(
            make_intent(side="sell", reduces_position=True, est_max_loss_jpy=1.0),
            make_ctx(bot_open_positions=1),
        )

    def test_effective_leverage_limit(self, guard, registry):
        _activate(registry, "P-02", account_max_effective=1.0)
        ctx = make_ctx(equity_jpy=1_000_000.0, total_exposure_jpy=990_000.0)
        # 新規 10,000円 → 実効レバ 1.0 ちょうど → 可
        guard.check(make_intent(qty=0.001, est_max_loss_jpy=1.0), ctx)
        ctx2 = make_ctx(equity_jpy=1_000_000.0, total_exposure_jpy=995_000.0)
        with pytest.raises(RiskRejection) as ei:
            guard.check(make_intent(qty=0.001, est_max_loss_jpy=1.0), ctx2)
        assert ei.value.reason_code == "LEVERAGE_LIMIT"


class TestApprovedOrderType:
    def test_approved_order_cannot_be_constructed_directly(self):
        """RiskApprovedOrder は risk_guard のみが生成できる(経路の型レベル遮断)。"""
        with pytest.raises(PermissionError):
            RiskApprovedOrder(
                bot_id="x",
                decision_id="TD-test-0001",
                instrument_id="paper.btc_jpy.spot",
                side="buy",
                qty=0.001,
                price=10_000_000.0,
                order_type="market",
            )

    def test_check_returns_approved_order(self, guard, registry):
        activate_required_policies(registry)
        approved = guard.check(make_intent(est_max_loss_jpy=1.0), make_ctx())
        assert isinstance(approved, RiskApprovedOrder)
        assert approved.decision_id == "TD-test-0001"
        assert approved.side == "buy"


class TestNoBotExchangeImport:
    def test_bots_do_not_import_exchange_directly(self):
        """bots/ から core/exchange/ を直接 import する経路を禁止(原則2)。"""
        import pathlib

        import re

        bots_dir = pathlib.Path(__file__).resolve().parents[2] / "bots"
        if not bots_dir.exists():
            pytest.skip("bots/ not yet created")
        forbidden = re.compile(r"^\s*(from|import)\s+core\.(exchange|execution)", re.MULTILINE)
        for py in bots_dir.glob("**/*.py"):
            source = py.read_text(encoding="utf-8")
            match = forbidden.search(source)
            assert match is None, f"{py} が {match.group(0).strip() if match else ''} している"
