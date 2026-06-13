"""モノレポ・ルートの pytest 設定(ADR-0011)。

ルートから全体スイート(`pytest`)を流すとき、各プロジェクトのトップレベルパッケージを
import できるよう sys.path を通す。`shared`(ルート直下)は rootdir 追加で解決されるが、
`core`/`bots`/`scripts`(TradeCouncil 配下)は明示的に通す必要がある。
各プロジェクト dir から個別に流す場合(`cd TradeCouncil && pytest`)は本ファイルは読まれない。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
for _p in (_ROOT, _ROOT / "TradeCouncil"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
