"""ガバナンス層の例外。"""

from __future__ import annotations


class GovernanceError(Exception):
    """ガバナンス層の基底例外。"""


class PolicyNotActiveError(GovernanceError):
    """必須ポリシーが active でない(No Policy, No Trade の基本素子)。"""

    def __init__(self, policy_id: str, reason: str = "not_active") -> None:
        self.policy_id = policy_id
        self.reason = reason
        super().__init__(f"POLICY_MISSING:{policy_id} ({reason})")


class PolicyKeyMissingError(GovernanceError):
    """active ポリシーに必要キーが無い(キー粒度の fail-closed)。"""

    def __init__(self, policy_id: str, key: str) -> None:
        self.policy_id = policy_id
        self.key = key
        super().__init__(f"POLICY_KEY_MISSING:{policy_id}.{key}")


class DecisionRecordError(GovernanceError):
    """決裁レコードの不備(必須項目欠落・権限違反・不正な遷移)。"""
