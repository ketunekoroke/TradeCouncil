"""`tc policy ...` / `tc approve|reject|defer` — ポリシーレジストリ・決裁キュー操作。

`tc policy record --file <yaml>` が決裁済みポリシーを適用する**唯一の経路**
(会議の書記 = ファシリテーターがこれを呼ぶ。手編集は hooks / pre-commit が検出)。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


def _registry():
    from core.db import init_db
    from core.governance.registry import default_registry

    init_db()
    return default_registry()


def run_policy_command(args: argparse.Namespace) -> int:
    registry = _registry()

    if args.policy_command == "list":
        policies = registry.all_policies()
        if not policies:
            print("ポリシーなし(全領域 fail-closed)。第0回会議で P-01〜P-04 を決裁してください。")
            return 0
        for doc in policies:
            ref = doc.review_after or "-"
            print(f"{doc.policy_id}  v{doc.version:<3} {doc.status:<9} review_after={ref}  {doc.title}")
        return 0

    if args.policy_command == "show":
        doc = registry.get(args.policy_id)
        if doc is None:
            print(f"未登録: {args.policy_id}", file=sys.stderr)
            return 1
        print(yaml.safe_dump(doc.model_dump(mode="json", exclude_none=True),
                             allow_unicode=True, sort_keys=False))
        return 0

    if args.policy_command == "sync":
        paths = registry.generate_views()
        for p in paths:
            print(f"generated: {p}")
        return 0

    if args.policy_command == "record":
        return _record(registry, Path(args.file))

    print("usage: tc policy list|show|sync|record", file=sys.stderr)
    return 2


def _record(registry, file: Path) -> int:
    from core.governance.schema import DecisionRecord

    if not file.exists():
        print(f"ファイルが見つからない: {file}", file=sys.stderr)
        return 1
    raw = yaml.safe_load(file.read_text(encoding="utf-8"))
    try:
        record = DecisionRecord.model_validate(raw)
    except Exception as exc:
        print(f"決裁レコードの検証エラー(運営規程 §2.3):\n{exc}", file=sys.stderr)
        return 1
    doc = registry.record_decision(record)
    print(f"決裁を適用: {record.policy_id} {record.action.value} → v{doc.version} ({doc.status.value})")
    registry.generate_views()
    print("実行用ビュー(config/generated/)を再生成した")
    return 0


def run_decide_command(args: argparse.Namespace) -> int:
    """決裁キュー(proposals)への決裁: tc approve|reject|defer <proposal_id>。"""
    from core.db import get_session_factory, init_db
    from core.db.models import Proposal

    init_db()
    session_factory = get_session_factory()
    action: str = args.decide_action
    status_map = {"approve": "approved", "reject": "rejected", "defer": "deferred"}

    with session_factory() as session:
        row = session.get(Proposal, args.proposal_id)
        if row is None:
            print(f"提案が見つからない: {args.proposal_id}", file=sys.stderr)
            return 1
        if row.status != "pending_decision":
            print(f"既に処理済み: {row.status}", file=sys.stderr)
            return 1

        resolution_ref = None
        if action == "approve":
            file = getattr(args, "file", None)
            if row.target_policy_id and not file:
                print(
                    "ポリシー変更を伴う承認には決裁レコードが必要: tc approve <id> --file <yaml>",
                    file=sys.stderr,
                )
                return 1
            if file:
                registry = _registry()
                rc = _record(registry, Path(file))
                if rc != 0:
                    return rc
                resolution_ref = str(file)

        row.status = status_map[action]
        row.resolution_ref = resolution_ref
        session.commit()
        print(f"提案 {args.proposal_id} を {status_map[action]} にした")
        print(json.dumps(row.content_json, ensure_ascii=False)[:200])
    return 0
