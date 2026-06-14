"""検証ゲート / ポリシー lint [実装予定 — BL-AC-011]。

compliance-checklist.md のタイミング表に従い、pre-commit / CI / 抽出・登録時に呼ぶ自動チェック。

実装予定のチェック(docs/compliance-checklist.md):
  - 為替: 取引日レートで円換算済みか(企業は前営業日)。JPY 併記との乖離なし。
  - 税区分: 内外判定済み(国外=対象外)、国内は税区分付与済み。
  - 証憑: 電帳法 検索3項目(日付・金額・取引先)を満たすか。登録番号はあれば記録。
  - 摘要に相関キー付与。
  - ポリシー文書 lint: accounting-policy.md に「適用開始日」があり、相互矛盾の自明な記述が無い。

ポリシー文書 lint(常時)に加え、`--drafts` で経費明細下書き(var/expense/drafts)の検証ゲート結果を
点検する(BL-AC-020)。下書きは取込時に `core/gate.check` で検査済みで、その error 級の指摘が残って
いないかを集約する(無人 CI / コミット前の安全網)。為替・税区分・証憑のチェックは core/gate が担う。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY = PROJECT_ROOT / "docs" / "accounting-policy.md"


def lint_policy_doc() -> list[str]:
    """会計ポリシー正本の最小 lint。問題のリストを返す(空なら合格)。"""
    problems: list[str] = []
    if not POLICY.is_file():
        return [f"会計ポリシーが見つかりません: {POLICY}"]
    text = POLICY.read_text(encoding="utf-8")
    if "適用開始日" not in text:
        problems.append("accounting-policy.md に『適用開始日』がありません(版管理の必須要素)")
    # 自明な相互矛盾の検査: 2割特例/簡易課税の文脈で経過措置(80%→50%)を適用と書いていないか。
    if "経過措置" in text and "適用する" in text and "本則課税" not in text:
        problems.append(
            "経過措置(80%→50%)は 2割特例/簡易課税では無関係(みなし控除)。"
            "適用すると読める記述がないか確認してください(docs/caveats.md)"
        )
    return problems


def scan_drafts() -> list[str]:
    """経費明細下書きの検証ゲート結果を点検し、error 級の指摘が残る下書きを列挙する。

    下書きは取込時に `core/gate.check` で検査済み(その結果が draft["gate"] に埋め込まれている)。
    ここでは error 級が残っていないかだけを集約する(再計算はしない)。drafts が無ければ空。
    """
    sys.path.insert(0, str(PROJECT_ROOT))
    from scripts import expense_pipeline as ep

    problems: list[str] = []
    for draft in ep.list_drafts():
        errors = [g for g in draft.get("gate", []) if g.get("level") == "error"]
        if errors:
            key = draft.get("correlation_key", "(no-key)")
            msgs = " / ".join(g.get("message", "") for g in errors)
            problems.append(f"{key}: {msgs}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="検証ゲート / ポリシー lint(Accounting)")
    parser.add_argument(
        "--drafts", action="store_true", help="経費明細下書きの検証ゲート結果も点検する(BL-AC-020)"
    )
    args = parser.parse_args(argv)

    problems = lint_policy_doc()
    if args.drafts:
        problems += scan_drafts()
    if problems:
        print("compliance: 問題を検出:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    scope = "ポリシー lint + 下書きゲート" if args.drafts else "ポリシー lint"
    print(f"compliance: {scope} OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
