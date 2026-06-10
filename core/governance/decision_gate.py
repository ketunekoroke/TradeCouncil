"""decision_gate — 委任ポリシー(P-01)の機械検証器(基本設計書 §1.5.5)。

入力された提案を3つに振り分ける:
  (a) 委任範囲内 → 検証して自動適用 + 事後報告(AUTO_APPLIED)
  (b) 範囲外     → 決裁キュー(proposals)へ回送(QUEUED。破棄しない)
  (c) 不変条項に抵触 → reject + 警告(REJECTED)

Phase 0 の初期値は「委任なし(全件決裁)」のため実運用は全件 (b) に落ちるが、
3分岐すべてをテストで担保する。
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from core.governance.errors import PolicyNotActiveError
from core.governance.registry import PolicyRegistry
from core.governance.schema import DecisionAction, DecisionRecord

# 不変条項(運営規程 第1章)に抵触する提案の構造的検出。
# 提案 content にこれらのキー/対象が含まれるものは無条件 reject する。
FORBIDDEN_CONTENT_KEYS: frozenset[str] = frozenset(
    {
        "disable_kill_switch",
        "bypass_decision",
        "bypass_decision_gate",
        "disable_audit_log",
        "disable_fail_closed",
        "transfer_decision_authority",
        "llm_direct_execution",
    }
)
IMMUTABLE_TARGET: str = "framework"  # target_policy_id="framework" は不変条項そのもの


class GateStatus(StrEnum):
    AUTO_APPLIED = "auto_applied"
    QUEUED = "queued"
    REJECTED = "rejected"


class ProposalInput(BaseModel):
    """会議決議・週次提案・利用者起案の共通入力。"""

    source: str  # council / weekly_review / user / bot_data
    target_policy_id: str | None = None
    title: str = ""
    content: dict[str, Any] = Field(default_factory=dict)
    session_ref: str | None = None


class GateResult(BaseModel):
    status: GateStatus
    reason: str
    proposal_id: str | None = None
    applied_policy_version: int | None = None


def _violates_immutable(proposal: ProposalInput) -> str | None:
    if proposal.target_policy_id == IMMUTABLE_TARGET:
        return "不変条項(フレームワーク憲法)は会議の議題にできない"
    bad = FORBIDDEN_CONTENT_KEYS.intersection(proposal.content.keys())
    if bad:
        return f"不変条項に抵触するキー: {sorted(bad)}"
    return None


def _delegation_scope(registry: PolicyRegistry) -> list[dict[str, Any]]:
    """P-01 の委任スコープ。P-01 が非activeなら空(=委任なし)。"""
    try:
        p01 = registry.require("P-01")
    except PolicyNotActiveError:
        return []
    delegation = p01.value.get("delegation") or {}
    if not delegation.get("enabled"):
        return []
    return list(delegation.get("scopes") or [])


def _within_scope(proposal: ProposalInput, scopes: list[dict[str, Any]]) -> bool:
    """提案が委任スコープ内か(対象ポリシー一致 + 変更キーが許可リスト内)。"""
    if proposal.target_policy_id is None:
        return False
    if proposal.target_policy_id == "P-01":
        # 委任範囲の変更そのものは常に決裁事項(運営規程 第4章)。
        # P-01 をスコープに含めても自動適用しない
        return False
    changes = proposal.content.get("value")
    if not isinstance(changes, dict) or not changes:
        return False
    for scope in scopes:
        if scope.get("target_policy_id") != proposal.target_policy_id:
            continue
        allowed_keys = set(scope.get("keys") or [])
        if set(changes.keys()) <= allowed_keys:
            return True
    return False


def route(
    proposal: ProposalInput,
    registry: PolicyRegistry,
    session_factory: sessionmaker[Session] | None = None,
    now_iso: str = "",
) -> GateResult:
    """提案を3分岐に振り分ける(§1.5.5)。"""
    # (c) 不変条項チェック
    violation = _violates_immutable(proposal)
    if violation is not None:
        _record_incident(session_factory, proposal, violation)
        return GateResult(status=GateStatus.REJECTED, reason=violation)

    # (a) 委任範囲内 → 自動適用
    scopes = _delegation_scope(registry)
    if scopes and _within_scope(proposal, scopes):
        target = registry.require(proposal.target_policy_id)  # type: ignore[arg-type]
        merged = dict(target.value)
        merged.update(proposal.content["value"])
        record = DecisionRecord(
            policy_id=target.policy_id,
            title=target.title,
            action=DecisionAction.MODIFY_APPROVE,
            value=merged,
            decided_by="owner(delegated)",
            channel="delegation",
            session_ref=proposal.session_ref,
            basis_refs=[f"delegated_by=P-01 v{registry.require('P-01').version}"],
            decided_at=now_iso or "delegated",
            review_after=target.review_after,
        )
        applied = registry.record_decision(record)
        return GateResult(
            status=GateStatus.AUTO_APPLIED,
            reason="P-01 委任範囲内のため自動適用(事後報告)",
            applied_policy_version=applied.version,
        )

    # (b) 範囲外 → 決裁キューへ回送(破棄しない)
    proposal_id = f"PR-{uuid.uuid4().hex[:10]}"
    if session_factory is not None:
        from core.db.models import Proposal as ProposalRow

        with session_factory() as session:
            session.add(
                ProposalRow(
                    proposal_id=proposal_id,
                    source=proposal.source,
                    target_policy_id=proposal.target_policy_id,
                    content_json={"title": proposal.title, **proposal.content},
                    status="pending_decision",
                )
            )
            session.commit()
    return GateResult(
        status=GateStatus.QUEUED,
        reason="委任範囲外のため決裁キューへ回送(利用者の決裁待ち)",
        proposal_id=proposal_id,
    )


def _record_incident(
    session_factory: sessionmaker[Session] | None,
    proposal: ProposalInput,
    violation: str,
) -> None:
    if session_factory is None:
        return
    from core.db.models import Incident

    with session_factory() as session:
        session.add(
            Incident(
                severity="warning",
                component="decision_gate",
                summary="不変条項に抵触する提案を reject",
                detail=f"source={proposal.source} target={proposal.target_policy_id} "
                f"violation={violation}",
            )
        )
        session.commit()
