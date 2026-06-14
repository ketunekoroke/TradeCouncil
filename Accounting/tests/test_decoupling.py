"""削除可能性(ADR-0011): core/ が Magi / TradeCouncil を import しないことを検査する。

Accounting/ を削除しても他プロジェクトが無傷であることの裏返し。core/ は stdlib + 自前モジュールのみ。
"""

import re
from pathlib import Path

CORE = Path(__file__).resolve().parents[1] / "core"
FORBIDDEN = re.compile(r"^\s*(?:from|import)\s+(Magi|TradeCouncil)\b", re.MULTILINE)
# core は stdlib + 自前のみ。scripts 層の依存(yaml/PIL/pypdf)や shared を core から import しない。
FORBIDDEN_DEP = re.compile(
    r"^\s*(?:from|import)\s+(yaml|PIL|Pillow|pypdf|requests|httpx|pydantic|numpy|pandas|shared)\b",
    re.MULTILINE,
)


def test_core_does_not_import_other_projects():
    offenders = []
    for py in CORE.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if FORBIDDEN.search(text):
            offenders.append(str(py))
    assert not offenders, f"core/ が他プロジェクトを import しています(ADR-0011 違反): {offenders}"


def test_core_is_stdlib_only():
    """core/ がサードパーティ(yaml/PIL 等)や shared を import しないこと(zero-dep — BL-AC-020)。"""
    offenders = []
    for py in CORE.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for m in FORBIDDEN_DEP.finditer(text):
            offenders.append(f"{py.name}: {m.group(1)}")
    assert not offenders, f"core/ が非 stdlib を import しています(zero-dep 違反): {offenders}"
