"""git pre-push hook 本体(インストールは `tc hooks install`)。

push 前に**各プロジェクトの docs ミラー**(ADR-0010)を実行する。ff マージ等で post-commit が
発火しないケースの回収役。up to date なら通信しない。
**fail-open**: ミラー失敗でも push は止めない(warn のみ・常に exit 0)。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from post_commit import run_all_mirrors  # noqa: E402


def main() -> int:
    try:
        run_all_mirrors()
    except Exception as e:  # フックは何があっても push を妨げない
        print(f"warn: docs ミラーをスキップ: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
