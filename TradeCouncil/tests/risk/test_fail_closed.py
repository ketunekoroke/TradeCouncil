"""fail-closed(No Policy, No Trade)の性質テスト — Phase 0 DoD の中核。

「必須ポリシーが active でない領域では発注を拒否する」(不変条項5)を
あらゆる欠落パターンで確認する。
"""

from __future__ import annotations

import pytest

from core.db.models import Order
from core.governance.schema import REQUIRED_POLICY_IDS, DecisionAction
from core.risk.errors import RiskRejection
from tests.conftest import TEST_POLICY_VALUES, activate_required_policies, make_decision
from tests.risk.conftest import make_ctx, make_intent


class TestNoPolicyNoTrade:
    def test_zero_policies_rejects(self, guard):
        """clone 直後(ポリシー0件)では一切発注されない。"""
        with pytest.raises(RiskRejection) as ei:
            guard.check(make_intent(), make_ctx())
        assert ei.value.reason_code.startswith("POLICY_MISSING")

    @pytest.mark.parametrize("missing", REQUIRED_POLICY_IDS)
    def test_any_single_missing_policy_rejects(self, guard, registry, missing):
        """P-01〜P-04 のどれか1つでも欠けると拒否。"""
        for pid, value in TEST_POLICY_VALUES.items():
            if pid != missing:
                registry.record_decision(make_decision(pid, value))
        with pytest.raises(RiskRejection) as ei:
            guard.check(make_intent(), make_ctx())
        assert missing in ei.value.reason_code

    @pytest.mark.parametrize("missing", REQUIRED_POLICY_IDS)
    def test_retired_policy_rejects(self, guard, registry, missing):
        """active だったポリシーが退役すると fail-closed に戻る。"""
        activate_required_policies(registry)
        guard.check(make_intent(), make_ctx())  # まず通ることを確認
        registry.retire(make_decision(missing, None, action=DecisionAction.REJECT))
        with pytest.raises(RiskRejection):
            guard.check(make_intent(), make_ctx())

    def test_effective_from_future_rejects(self, guard, registry):
        for pid, value in TEST_POLICY_VALUES.items():
            kw = {"effective_from": "2999-12-31"} if pid == "P-03" else {}
            registry.record_decision(make_decision(pid, value, **kw))
        with pytest.raises(RiskRejection) as ei:
            guard.check(make_intent(), make_ctx())
        assert "P-03" in ei.value.reason_code


class TestAssetClassFailClosed:
    def test_undecided_asset_class_rejects(self, guard, registry):
        """P-02 に載っていない資産クラスは封鎖(未決裁クラスの fail-closed)。"""
        activate_required_policies(registry)
        with pytest.raises(RiskRejection) as ei:
            guard.check(make_intent(asset_class="equity_jp"), make_ctx())
        assert ei.value.reason_code == "ASSET_CLASS_BLOCKED:equity_jp"

    def test_zero_leverage_asset_class_rejects(self, guard, registry):
        """上限 0 のクラスは使用禁止。"""
        overrides = {
            "P-02": {
                "account_max_effective": 1.0,
                "per_asset_class": {"crypto_spot": 0.0},
                "hard_ceiling": 1.0,
            }
        }
        activate_required_policies(registry, overrides=overrides)
        with pytest.raises(RiskRejection) as ei:
            guard.check(make_intent(), make_ctx())
        assert "ASSET_CLASS_BLOCKED" in ei.value.reason_code


class TestKeyLevelFailClosed:
    @pytest.mark.parametrize(
        "policy_id,drop_key",
        [
            ("P-02", "per_asset_class"),
            ("P-02", "account_max_effective"),
            ("P-03", "max_daily_loss_pct"),
            ("P-03", "max_weekly_drawdown_pct"),
            ("P-03", "per_trade_max_loss_pct"),
            ("P-03", "max_total_exposure_pct"),
            ("P-03", "per_bot_max_positions"),
            ("P-04", "stale_data_sec"),
            ("P-04", "cb_price_jump_pct_1m"),
            ("P-04", "cb_max_spread_bps"),
        ],
    )
    def test_missing_policy_key_rejects(self, guard, registry, policy_id, drop_key):
        """ポリシーに必要キーが無ければ拒否(たたき台値のフォールバック禁止)。"""
        value = {k: v for k, v in TEST_POLICY_VALUES[policy_id].items() if k != drop_key}
        activate_required_policies(registry, overrides={policy_id: value})
        with pytest.raises(RiskRejection) as ei:
            guard.check(make_intent(), make_ctx())
        assert "POLICY_KEY_MISSING" in ei.value.reason_code


class TestRejectionAudit:
    def test_rejection_is_recorded_in_orders(self, guard, db_session_factory):
        """拒否も orders に status=rejected で記録される(監査ログ一元化)。"""
        with pytest.raises(RiskRejection):
            guard.check(make_intent(), make_ctx())
        with db_session_factory() as s:
            rows = s.query(Order).all()
        assert len(rows) == 1
        assert rows[0].status == "rejected"
        assert rows[0].reject_reason.startswith("POLICY_MISSING")
        assert rows[0].decision_id == "TD-test-0001"
