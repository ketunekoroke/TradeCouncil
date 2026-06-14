"""decision_gate の3分岐テスト(基本設計書 §1.5.5)。"""

from __future__ import annotations

from core.db.models import Incident, Proposal
from core.governance.decision_gate import (
    GateStatus,
    ProposalInput,
    route,
)
from core.governance.registry import PolicyRegistry
from tests.conftest import TEST_POLICY_VALUES, activate_required_policies, make_decision


def _proposal(**kw) -> ProposalInput:
    defaults = dict(
        source="council",
        target_policy_id="P-03",
        title="日次損失上限の変更案",
        content={"value": {"max_daily_loss_pct": 77.0}},
        session_ref="council-test",
    )
    defaults.update(kw)
    return ProposalInput(**defaults)


class TestRejectBranch:
    def test_framework_target_is_rejected(self, registry, db_session_factory):
        result = route(
            _proposal(target_policy_id="framework", content={"value": {"x": 1}}),
            registry,
            db_session_factory,
        )
        assert result.status is GateStatus.REJECTED
        with db_session_factory() as s:
            incidents = s.query(Incident).all()
        assert len(incidents) == 1
        assert incidents[0].component == "decision_gate"

    def test_forbidden_content_key_is_rejected(self, registry, db_session_factory):
        result = route(
            _proposal(content={"disable_kill_switch": True}),
            registry,
            db_session_factory,
        )
        assert result.status is GateStatus.REJECTED
        assert "不変条項" in result.reason


class TestQueueBranch:
    def test_no_delegation_routes_to_queue(self, registry, db_session_factory):
        """初期値(委任なし)では全提案が決裁キューへ(破棄しない)。"""
        activate_required_policies(registry)  # P-01 は delegation.enabled=False
        result = route(_proposal(), registry, db_session_factory)
        assert result.status is GateStatus.QUEUED
        assert result.proposal_id is not None
        with db_session_factory() as s:
            row = s.get(Proposal, result.proposal_id)
        assert row is not None
        assert row.status == "pending_decision"
        assert row.target_policy_id == "P-03"

    def test_no_policies_at_all_routes_to_queue(self, registry, db_session_factory):
        """P-01 すら無い状態でも提案は破棄せずキューに積む。"""
        result = route(_proposal(), registry, db_session_factory)
        assert result.status is GateStatus.QUEUED

    def test_out_of_scope_delegation_routes_to_queue(
        self, registry: PolicyRegistry, db_session_factory
    ):
        """委任が有効でも、スコープ外のキー変更はキューへ。"""
        overrides = {
            "P-01": {
                "delegation": {
                    "enabled": True,
                    "scopes": [
                        {"target_policy_id": "P-03", "keys": ["per_bot_max_positions"]}
                    ],
                }
            }
        }
        activate_required_policies(registry, overrides=overrides)
        result = route(_proposal(), registry, db_session_factory)  # max_daily_loss_pct は対象外
        assert result.status is GateStatus.QUEUED


class TestAutoApplyBranch:
    def test_within_delegation_scope_is_auto_applied(
        self, registry: PolicyRegistry, db_session_factory
    ):
        overrides = {
            "P-01": {
                "delegation": {
                    "enabled": True,
                    "scopes": [
                        {"target_policy_id": "P-03", "keys": ["max_daily_loss_pct"]}
                    ],
                }
            }
        }
        activate_required_policies(registry, overrides=overrides)
        before = registry.require("P-03").version
        result = route(_proposal(), registry, db_session_factory, now_iso="2026-01-02T00:00:00+09:00")
        assert result.status is GateStatus.AUTO_APPLIED
        after = registry.require("P-03")
        assert after.version == before + 1
        assert after.value["max_daily_loss_pct"] == 77.0
        # 他のキーは維持される(マージ適用)
        assert after.value["max_total_exposure_pct"] == TEST_POLICY_VALUES["P-03"][
            "max_total_exposure_pct"
        ]
        # 監査ログ(決裁履歴)が残る
        from core.db.models import PolicyDecision

        with db_session_factory() as s:
            last = (
                s.query(PolicyDecision)
                .filter_by(policy_id="P-03")
                .order_by(PolicyDecision.version.desc())
                .first()
            )
        assert last.channel == "delegation"
        assert last.decided_by == "owner(delegated)"


class TestDelegationRequiresOwnerDecision:
    def test_delegation_change_itself_is_never_auto_applied(
        self, registry: PolicyRegistry, db_session_factory
    ):
        """委任範囲の変更(P-01 自体)はたとえ委任が有効でも自動適用させない設計を確認。

        P-01 のスコープに P-01 を含めても、運営規程 第4章「委任範囲の変更そのものは
        常に決裁事項」をテストとして固定する。
        """
        overrides = {
            "P-01": {
                "delegation": {
                    "enabled": True,
                    "scopes": [{"target_policy_id": "P-01", "keys": ["delegation"]}],
                }
            }
        }
        activate_required_policies(registry, overrides=overrides)
        result = route(
            _proposal(
                target_policy_id="P-01",
                content={"value": {"delegation": {"enabled": False}}},
            ),
            registry,
            db_session_factory,
        )
        assert result.status is GateStatus.QUEUED
