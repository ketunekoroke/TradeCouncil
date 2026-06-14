"""検証ゲート / ポリシー lint [実装予定 — BL-AC-011]。

compliance-checklist.md のタイミング表に従い、pre-commit / CI / 抽出・登録時に呼ぶ自動チェック。

実装予定のチェック(docs/compliance-checklist.md):
  - 為替: 取引日レートで円換算済みか(企業は前営業日)。JPY 併記との乖離なし。
  - 税区分: 内外判定済み(国外=対象外)、国内は税区分付与済み。
  - 証憑: 電帳法 検索3項目(日付・金額・取引先)を満たすか。登録番号はあれば記録。
  - 摘要に相関キー付与。
  - ポリシー文書 lint: accounting-policy.md に「適用開始日」があり、相互矛盾の自明な記述が無い。

現状(Phase 0)はポリシー文書 lint の最小版のみ提供する(pre-commit から呼べるよう exit code を返す)。
為替・税区分・証憑の検証ゲートは core 実装後に追加する。
"""

from __future__ import annotations

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


def main() -> int:
    problems = lint_policy_doc()
    if problems:
        print("ポリシー lint で問題を検出:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print("compliance: ポリシー lint OK(為替・税区分・証憑の検証ゲートは [実装予定] BL-AC-011)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
