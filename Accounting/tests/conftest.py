"""Accounting テストの共通設定。

Accounting dir を cwd にして `pytest` を流す前提(editable install しない — DEVELOPMENT.md)。
プロジェクトルートを sys.path に通し、`import core` / `import scripts` を解決する。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]  # Accounting/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
