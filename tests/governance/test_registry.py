"""ポリシーレジストリのテスト(ライフサイクル・決裁レコード・ビュー生成)。"""

from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from core.governance.errors import (
    DecisionRecordError,
    PolicyKeyMissingError,
    PolicyNotActiveError,
)
from core.governance.registry import PolicyRegistry
from core.governance.schema import DecisionAction, PolicyStatus
from tests.conftest import TEST_POLICY_VALUES, make_decision


class TestLifecycle:
    def test_initial_state_is_empty_and_fail_closed(self, registry: PolicyRegistry):
        assert registry.all_policies() == []
        with pytest.raises(PolicyNotActiveError):
            registry.require("P-03")
        with pytest.raises(PolicyNotActiveError):
            registry.require_all()

    def test_approve_creates_active_v1(self, registry: PolicyRegistry):
        doc = registry.record_decision(make_decision("P-03", TEST_POLICY_VALUES["P-03"]))
        assert doc.status is PolicyStatus.ACTIVE
        assert doc.version == 1
        assert registry.require("P-03").value["max_daily_loss_pct"] == 99.0

    def test_second_approve_increments_version(self, registry: PolicyRegistry):
        registry.record_decision(make_decision("P-03", TEST_POLICY_VALUES["P-03"]))
        v2 = dict(TEST_POLICY_VALUES["P-03"], max_daily_loss_pct=88.0)
        doc = registry.record_decision(
            make_decision("P-03", v2, action=DecisionAction.MODIFY_APPROVE)
        )
        assert doc.version == 2
        assert registry.require("P-03").value["max_daily_loss_pct"] == 88.0

    def test_rollback_is_re_decision_of_old_value(self, registry: PolicyRegistry):
        registry.record_decision(make_decision("P-03", TEST_POLICY_VALUES["P-03"]))
        registry.record_decision(
            make_decision(
                "P-03",
                dict(TEST_POLICY_VALUES["P-03"], max_daily_loss_pct=88.0),
                action=DecisionAction.MODIFY_APPROVE,
            )
        )
        # ロールバック = 旧値の再決裁(履歴は消えない)
        doc = registry.record_decision(make_decision("P-03", TEST_POLICY_VALUES["P-03"]))
        assert doc.version == 3
        assert registry.require("P-03").value["max_daily_loss_pct"] == 99.0

    def test_reject_does_not_change_active_value(self, registry: PolicyRegistry):
        registry.record_decision(make_decision("P-03", TEST_POLICY_VALUES["P-03"]))
        registry.record_decision(
            make_decision("P-03", None, action=DecisionAction.REJECT)
        )
        assert registry.require("P-03").value["max_daily_loss_pct"] == 99.0
        assert registry.require("P-03").version == 1

    def test_defer_does_not_activate(self, registry: PolicyRegistry):
        registry.record_decision(make_decision("P-02", None, action=DecisionAction.DEFER))
        with pytest.raises(PolicyNotActiveError):
            registry.require("P-02")

    def test_retire_returns_to_fail_closed(self, registry: PolicyRegistry):
        registry.record_decision(make_decision("P-02", TEST_POLICY_VALUES["P-02"]))
        registry.retire(make_decision("P-02", None, action=DecisionAction.REJECT))
        with pytest.raises(PolicyNotActiveError):
            registry.require("P-02")

    def test_effective_from_future_is_not_effective(self, registry: PolicyRegistry):
        registry.record_decision(
            make_decision(
                "P-03", TEST_POLICY_VALUES["P-03"], effective_from="2999-12-31"
            )
        )
        with pytest.raises(PolicyNotActiveError) as ei:
            registry.require("P-03")
        assert "effective_from_future" in str(ei.value)


class TestDecisionRecordValidation:
    def test_decided_by_must_be_owner(self):
        with pytest.raises(ValidationError, match="不変条項1"):
            make_decision("P-03", TEST_POLICY_VALUES["P-03"], decided_by="agent")

    def test_decided_at_required(self):
        with pytest.raises(ValidationError):
            make_decision("P-03", TEST_POLICY_VALUES["P-03"], decided_at="  ")

    def test_approve_without_value_is_rejected(self, registry: PolicyRegistry):
        with pytest.raises(DecisionRecordError, match="value"):
            registry.record_decision(make_decision("P-03", None))

    def test_missing_required_fields_rejected(self):
        # pydantic が必須項目(channel)の欠落を拒否する
        from core.governance.schema import DecisionRecord

        with pytest.raises(ValidationError):
            DecisionRecord(
                policy_id="P-03",
                title="x",
                action=DecisionAction.APPROVE,
                value={},
                decided_by="owner",
                decided_at="2026-01-01",
            )  # channel 欠落


class TestPersistenceAndReload:
    def test_yaml_roundtrip(self, registry: PolicyRegistry, db_session_factory):
        registry.record_decision(make_decision("P-03", TEST_POLICY_VALUES["P-03"]))
        reloaded = PolicyRegistry(
            policies_dir=registry.policies_dir,
            generated_dir=registry.generated_dir,
            session_factory=db_session_factory,
        )
        assert reloaded.require("P-03").value == TEST_POLICY_VALUES["P-03"]

    def test_decision_history_is_append_only(self, registry: PolicyRegistry, db_session_factory):
        from core.db.models import PolicyDecision

        registry.record_decision(make_decision("P-03", TEST_POLICY_VALUES["P-03"]))
        registry.record_decision(
            make_decision(
                "P-03",
                dict(TEST_POLICY_VALUES["P-03"], max_daily_loss_pct=88.0),
                action=DecisionAction.MODIFY_APPROVE,
            )
        )
        with db_session_factory() as session:
            rows = session.query(PolicyDecision).order_by(PolicyDecision.version).all()
        assert len(rows) == 2
        assert [r.version for r in rows] == [1, 2]
        assert rows[0].value_snapshot_json["max_daily_loss_pct"] == 99.0


class TestKeyLevelFailClosed:
    def test_missing_key_raises(self, registry: PolicyRegistry):
        registry.record_decision(make_decision("P-03", {"max_daily_loss_pct": 99.0}))
        assert registry.require_value("P-03", "max_daily_loss_pct") == 99.0
        with pytest.raises(PolicyKeyMissingError):
            registry.require_value("P-03", "max_total_exposure_pct")


class TestViews:
    def test_generate_views_matches_active_policies(self, registry: PolicyRegistry):
        registry.record_decision(make_decision("P-03", TEST_POLICY_VALUES["P-03"]))
        paths = registry.generate_views()
        risk_path = next(p for p in paths if p.name == "risk_limits.yaml")
        content = risk_path.read_text(encoding="utf-8")
        assert "AUTO-GENERATED" in content
        data = yaml.safe_load(content)
        assert data["P-03"]["value"] == TEST_POLICY_VALUES["P-03"]
        assert "P-02" not in data  # 未決裁ポリシーはビューに出ない

    def test_views_empty_when_no_policies(self, registry: PolicyRegistry):
        paths = registry.generate_views()
        for p in paths:
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            assert data in (None, {})
