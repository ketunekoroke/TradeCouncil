"""ポリシーレジストリ(基本設計書 §1.5.3)。

- 真実の源泉は config/policies/*.yaml(Git管理)。DB(policies / policy_decisions)は
  監査用ミラー(append-only の決裁履歴を含む)
- システム(risk_guard 等)は status=active かつ effective_from 到来のポリシーだけを読む
- 変更経路は record_decision() のみ(= `tc policy record`)。YAML の手編集は
  pre-commit / hooks が検出する
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session, sessionmaker

from core.governance.errors import (
    DecisionRecordError,
    PolicyKeyMissingError,
    PolicyNotActiveError,
)
from core.governance.schema import (
    REQUIRED_POLICY_IDS,
    DecisionAction,
    DecisionInfo,
    DecisionRecord,
    PolicyDoc,
    PolicyStatus,
)

GENERATED_HEADER = (
    "# ============================================================\n"
    "# AUTO-GENERATED — 手編集禁止\n"
    "# このファイルは active なポリシーから tc policy sync で生成される\n"
    "# 実行用の確認ビューであり、システムはレジストリを直接読む\n"
    "# ============================================================\n"
)

# 実行用ビューに反映するポリシー(リスク関連)
RISK_VIEW_POLICIES = ("P-02", "P-03", "P-04")


def _slug(title: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in title)[:40].strip("_")


class PolicyRegistry:
    def __init__(
        self,
        policies_dir: Path,
        generated_dir: Path,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self.policies_dir = policies_dir
        self.generated_dir = generated_dir
        self._session_factory = session_factory
        self._cache: dict[str, PolicyDoc] = {}
        self.load()

    # ------------------------------------------------------------------
    # 読み取り
    # ------------------------------------------------------------------

    def load(self) -> None:
        """config/policies/*.yaml を検証して読み込む。"""
        self._cache = {}
        if not self.policies_dir.exists():
            return
        for path in sorted(self.policies_dir.glob("P-*.yaml")):
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            doc = PolicyDoc.model_validate(raw)
            if doc.policy_id in self._cache:
                raise DecisionRecordError(
                    f"duplicate policy file for {doc.policy_id}: {path.name}"
                )
            self._cache[doc.policy_id] = doc

    def get(self, policy_id: str) -> PolicyDoc | None:
        return self._cache.get(policy_id)

    def all_policies(self) -> list[PolicyDoc]:
        return sorted(self._cache.values(), key=lambda p: p.policy_id)

    def require(self, policy_id: str) -> PolicyDoc:
        """active でなければ PolicyNotActiveError(fail-closed の基本素子)。"""
        doc = self._cache.get(policy_id)
        if doc is None:
            raise PolicyNotActiveError(policy_id, "not_found")
        if doc.status is not PolicyStatus.ACTIVE:
            raise PolicyNotActiveError(policy_id, f"status={doc.status}")
        if not doc.is_effective():
            raise PolicyNotActiveError(policy_id, "effective_from_future")
        return doc

    def require_all(self, policy_ids: tuple[str, ...] = REQUIRED_POLICY_IDS) -> dict[str, PolicyDoc]:
        return {pid: self.require(pid) for pid in policy_ids}

    def require_value(self, policy_id: str, key: str) -> Any:
        """active ポリシーから必須キーを読む。欠落は拒否(キー粒度 fail-closed)。"""
        doc = self.require(policy_id)
        if key not in doc.value:
            raise PolicyKeyMissingError(policy_id, key)
        return doc.value[key]

    # ------------------------------------------------------------------
    # 決裁(唯一の変更経路)
    # ------------------------------------------------------------------

    def record_decision(self, record: DecisionRecord) -> PolicyDoc:
        """決裁レコードを適用する(運営規程 §2.2 の「適用」)。

        - approve / modify_approve: 新バージョンを active 化(旧 active は置換。
          履歴は policy_decisions に不滅で残り、ロールバック = 旧値の再決裁)
        - reject / defer: ポリシー状態は変えず、決裁履歴のみ記録する
        """
        if record.requires_value() and record.value is None:
            raise DecisionRecordError(
                f"{record.action} には value が必須({record.policy_id})"
            )

        current = self._cache.get(record.policy_id)
        new_version = (current.version + 1) if current else 1
        decision_id = f"D-{record.policy_id}-v{new_version:03d}"

        if record.requires_value():
            assert record.value is not None
            doc = PolicyDoc(
                policy_id=record.policy_id,
                title=record.title,
                status=PolicyStatus.ACTIVE,
                version=new_version,
                value=record.value,
                decision=DecisionInfo(
                    decision_id=decision_id,
                    decided_by=record.decided_by,
                    action=record.action,
                    channel=record.channel,
                    session_ref=record.session_ref,
                    basis_refs=record.basis_refs,
                    decided_at=record.decided_at,
                ),
                effective_from=record.effective_from,
                review_after=record.review_after,
            )
            self._write_policy_yaml(doc)
            self._cache[record.policy_id] = doc
            result = doc
        else:
            # reject / defer は現在値を変えない(履歴のみ)
            result = current if current is not None else PolicyDoc(
                policy_id=record.policy_id,
                title=record.title,
                status=PolicyStatus.PROPOSED,
                version=new_version,
                value=record.value or {},
            )

        self._record_to_db(record, decision_id, new_version)
        return result

    def retire(self, record: DecisionRecord) -> PolicyDoc:
        """ポリシーの退役(owner の決裁による)。該当領域は fail-closed に戻る。"""
        current = self._cache.get(record.policy_id)
        if current is None:
            raise DecisionRecordError(f"unknown policy: {record.policy_id}")
        new_version = current.version + 1
        decision_id = f"D-{record.policy_id}-v{new_version:03d}"
        doc = current.model_copy(
            update={
                "status": PolicyStatus.RETIRED,
                "version": new_version,
                "decision": DecisionInfo(
                    decision_id=decision_id,
                    decided_by=record.decided_by,
                    action=record.action,
                    channel=record.channel,
                    session_ref=record.session_ref,
                    basis_refs=record.basis_refs,
                    decided_at=record.decided_at,
                ),
            }
        )
        self._write_policy_yaml(doc)
        self._cache[record.policy_id] = doc
        self._record_to_db(record, decision_id, new_version)
        return doc

    # ------------------------------------------------------------------
    # 実行用ビュー生成
    # ------------------------------------------------------------------

    def generate_views(self) -> list[Path]:
        """active ポリシーから config/generated/ の確認ビューを生成する。"""
        self.generated_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []

        risk_view: dict[str, Any] = {}
        for pid in RISK_VIEW_POLICIES:
            doc = self._cache.get(pid)
            if doc is not None and doc.is_effective():
                risk_view[pid] = {
                    "title": doc.title,
                    "version": doc.version,
                    "value": doc.value,
                }
        risk_path = self.generated_dir / "risk_limits.yaml"
        risk_path.write_text(
            GENERATED_HEADER + yaml.safe_dump(risk_view, allow_unicode=True, sort_keys=True),
            encoding="utf-8",
        )
        written.append(risk_path)

        p01 = self._cache.get("P-01")
        delegation_view = (
            {"P-01": {"title": p01.title, "version": p01.version, "value": p01.value}}
            if p01 is not None and p01.is_effective()
            else {}
        )
        delegation_path = self.generated_dir / "delegation.yaml"
        delegation_path.write_text(
            GENERATED_HEADER
            + yaml.safe_dump(delegation_view, allow_unicode=True, sort_keys=True),
            encoding="utf-8",
        )
        written.append(delegation_path)
        return written

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _write_policy_yaml(self, doc: PolicyDoc) -> None:
        self.policies_dir.mkdir(parents=True, exist_ok=True)
        # 同一 policy_id の旧ファイル(タイトル変更でスラッグが変わった場合)を除去
        for old in self.policies_dir.glob(f"{doc.policy_id}_*.yaml"):
            old.unlink()
        path = self.policies_dir / f"{doc.policy_id}_{_slug(doc.title)}.yaml"
        data = doc.model_dump(mode="json", exclude_none=True)
        path.write_text(
            "# 決裁済みポリシー — 手編集禁止(変更は tc policy record 経由のみ)\n"
            + yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _record_to_db(self, record: DecisionRecord, decision_id: str, version: int) -> None:
        if self._session_factory is None:
            return
        from core.db.models import Policy as PolicyRow
        from core.db.models import PolicyDecision as PolicyDecisionRow

        with self._session_factory() as session:
            session.add(
                PolicyDecisionRow(
                    decision_id=decision_id,
                    policy_id=record.policy_id,
                    version=version,
                    action=record.action.value,
                    channel=record.channel,
                    session_ref=record.session_ref,
                    basis_refs_json=record.basis_refs,
                    decided_by=record.decided_by,
                    decided_at=record.decided_at,
                    value_snapshot_json=record.value,
                )
            )
            doc = self._cache.get(record.policy_id)
            if doc is not None:
                row = session.get(PolicyRow, record.policy_id)
                if row is None:
                    row = PolicyRow(
                        policy_id=doc.policy_id,
                        title=doc.title,
                        status=doc.status.value,
                        version=doc.version,
                        value_json=doc.value,
                        effective_from=doc.effective_from,
                        review_after=doc.review_after,
                    )
                    session.add(row)
                else:
                    row.title = doc.title
                    row.status = doc.status.value
                    row.version = doc.version
                    row.value_json = doc.value
                    row.effective_from = doc.effective_from
                    row.review_after = doc.review_after
            session.commit()


def default_registry() -> PolicyRegistry:
    """本番構成のレジストリ(config/policies/ + 既定DB)。"""
    from core.config import get_config
    from core.db import get_session_factory

    cfg = get_config()
    return PolicyRegistry(
        policies_dir=cfg.policies_dir,
        generated_dir=cfg.generated_dir,
        session_factory=get_session_factory(),
    )
