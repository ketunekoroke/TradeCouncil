"""docs lint: 会計ポリシー正本の最小検証(適用開始日・相互矛盾)。"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY = PROJECT_ROOT / "docs" / "accounting-policy.md"


def test_policy_has_effective_date():
    text = POLICY.read_text(encoding="utf-8")
    assert "適用開始日" in text, "accounting-policy.md に『適用開始日』が必要(版管理の必須要素)"


def test_check_compliance_lint_passes():
    from scripts.check_compliance import lint_policy_doc

    problems = lint_policy_doc()
    assert problems == [], f"ポリシー lint で問題: {problems}"
