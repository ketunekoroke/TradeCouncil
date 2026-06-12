"""git post-commit hook 本体(インストールは `tc hooks install`)。

main 上のコミット後に docs ミラー(`sharepoint.py mirror` — ADR-0010)を実行する。
**fail-open**: ミラー失敗でコミットは止めない(warn のみ・常に exit 0)。
失敗時はミラー状態(var/sharepoint_mirror.json)が進まないため、
次回のコミット/プッシュ or 手動 `python scripts/sharepoint.py mirror` で追いつく。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _mirror_branch() -> str:
    """ミラー対象ブランチ(git_mirror.branch)。設定不備でもフックは落とさない。"""
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    try:
        import sharepoint as sp

        return str(sp.mirror_config(sp.load_config()).get("branch", "main"))
    except BaseException:  # SystemExit(設定欠落)含む
        return "main"


def _current_branch() -> str:
    out = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (out.stdout or "").strip()


def run_mirror() -> None:
    """docs ミラーをサブプロセスで実行(進捗は端末へそのまま流す)。"""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "sharepoint.py"), "mirror"],
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        print(
            f"warn: docs ミラーに失敗(exit {result.returncode})。状態は進んでいないため"
            "次回コミット/プッシュ or `python scripts/sharepoint.py mirror` で追いつきます",
            file=sys.stderr,
        )


def main() -> int:
    try:
        if _current_branch() == _mirror_branch():
            run_mirror()
    except Exception as e:  # フックは何があってもコミットを妨げない
        print(f"warn: docs ミラーをスキップ: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
