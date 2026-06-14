"""削除可能性(ADR-0011): core/ が Magi / TradeCouncil を import しないことを検査する。

Accounting/ を削除しても他プロジェクトが無傷であることの裏返し。core/ は stdlib + 自前モジュールのみ。
"""

import re
from pathlib import Path

CORE = Path(__file__).resolve().parents[1] / "core"
FORBIDDEN = re.compile(r"^\s*(?:from|import)\s+(Magi|TradeCouncil)\b", re.MULTILINE)


def test_core_does_not_import_other_projects():
    offenders = []
    for py in CORE.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if FORBIDDEN.search(text):
            offenders.append(str(py))
    assert not offenders, f"core/ が他プロジェクトを import しています(ADR-0011 違反): {offenders}"
