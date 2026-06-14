"""PostToolUse(Edit|Write) hook: core/scripts/tests の編集後に高速テストを自動実行する。

対象外パス(ドキュメント・シナリオ・設定等)の編集ではテストを走らせない(遅延防止)。
失敗時は exit 2 で結果を Claude に返す(修正を促す)。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hook_common import read_hook_input  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # Accounting/
REPO_ROOT = Path(__file__).resolve().parents[3]  # モノレポルート(共有 .venv の在処 — ADR-0011)
TEST_TRIGGER = re.compile(r"/(core|scripts|tests)/.*\.py$")


def main() -> None:
    data = read_hook_input()
    file_path = ((data.get("tool_input") or {}).get("file_path") or "").replace("\\", "/")
    if not TEST_TRIGGER.search(file_path):
        sys.exit(0)

    python = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        sys.exit(0)  # venv 未構築環境ではスキップ

    result = subprocess.run(
        [str(python), "-m", "pytest", "tests", "-x", "-q", "--no-header"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-25:])
        print(f"編集後テストが失敗(ac test 相当):\n{tail}", file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
