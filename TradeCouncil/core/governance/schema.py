"""ポリシー・決裁レコードの pydantic スキーマ(基本設計書 §1.5.3 / 運営規程 §2.3)。"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

# 必須ポリシー(★)。これが active でない領域は fail-closed(不変条項5)
REQUIRED_POLICY_IDS: tuple[str, ...] = ("P-01", "P-02", "P-03", "P-04")


class PolicyStatus(StrEnum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    APPROVED = "approved"
    ACTIVE = "active"
    RETIRED = "retired"


class DecisionAction(StrEnum):
    APPROVE = "approve"
    MODIFY_APPROVE = "modify_approve"
    REJECT = "reject"
    DEFER = "defer"


class DecisionInfo(BaseModel):
    """ポリシーYAML内の decision ブロック。"""

    decision_id: str
    decided_by: str
    action: DecisionAction
    channel: str
    session_ref: str | None = None
    basis_refs: list[str] = Field(default_factory=list)
    decided_at: str


class PolicyDoc(BaseModel):
    """config/policies/*.yaml の形式(§1.5.3)。"""

    policy_id: str
    title: str
    status: PolicyStatus
    version: int = Field(ge=1)
    value: dict[str, Any]
    decision: DecisionInfo | None = None
    effective_from: str | None = None  # YYYY-MM-DD
    review_after: str | None = None  # YYYY-MM-DD

    @field_validator("policy_id")
    @classmethod
    def _validate_policy_id(cls, v: str) -> str:
        if not v.startswith("P-"):
            raise ValueError(f"policy_id must start with 'P-': {v}")
        return v

    def is_effective(self, today: str | None = None) -> bool:
        """active かつ effective_from が到来しているか。"""
        if self.status is not PolicyStatus.ACTIVE:
            return False
        if self.effective_from:
            now = today or datetime.now(UTC).strftime("%Y-%m-%d")
            if self.effective_from > now:
                return False
        return True


class DecisionRecord(BaseModel):
    """決裁レコード(運営規程 §2.3 必須項目)。

    `tc policy record --file <yaml>` で適用される唯一の入力形式。
    決裁権者(owner)以外の decided_by はシステムが受理しない(不変条項1)。
    """

    policy_id: str
    title: str
    action: DecisionAction
    value: dict[str, Any] | None = None  # approve/modify_approve では必須
    decided_by: str
    channel: str  # sync_council | async_approve | delegation
    session_ref: str | None = None
    basis_refs: list[str] = Field(default_factory=list)
    decided_at: str
    effective_from: str | None = None
    review_after: str | None = None
    note: str | None = None

    @field_validator("decided_by")
    @classmethod
    def _owner_only(cls, v: str) -> str:
        # 不変条項1: 決裁権は利用者(owner)のみ。delegation チャネルでも
        # 権限の源泉は owner の P-01 決裁であることを表記上も強制する
        if v not in ("owner", "owner(delegated)"):
            raise ValueError(f"decided_by must be 'owner' (got: {v!r}) — 不変条項1")
        return v

    @field_validator("decided_at")
    @classmethod
    def _decided_at_required(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("decided_at is required(運営規程 §2.3)")
        return v

    def requires_value(self) -> bool:
        return self.action in (DecisionAction.APPROVE, DecisionAction.MODIFY_APPROVE)
