"""git post-commit hook 本体(インストールは `tc hooks install` / `python shared/hooks/install` 相当)。

コミット後に**各プロジェクトの docs ミラー**(`shared/sharepoint.py mirror --project <p>` — ADR-0010)を
実行する。git は1リポジトリ=1フックなので、ここで全プロジェクトを走査して順にミラーする。
**fail-open**: ミラー失敗でコミットは止めない(warn のみ・常に exit 0)。失敗時は当該プロジェクトの
ミラー状態(`<project>/var/sharepoint_mirror.json`)が進まないため、次回コミット/プッシュ or
手動 `python shared/sharepoint.py mirror --project <p>` で追いつく。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHAREPOINT = REPO_ROOT / "shared" / "sharepoint.py"


def _projects() -> list[Path]:
    """直下サブディレクトリのうち sharepoint.config.json を持つもの = ミラー対象プロジェクト。"""
    out = []
    for p in sorted(REPO_ROOT.iterdir()):
        if p.is_dir() and (p / "sharepoint.config.json").is_file():
            out.append(p)
    return out


def _project_branch(project: Path) -> str:
    """そのプロジェクトのミラー対象ブランチ(git_mirror.branch、既定 main)。"""
    try:
        cfg = json.loads((project / "sharepoint.config.json").read_text(encoding="utf-8"))
        return str((cfg.get("git_mirror") or {}).get("branch", "main"))
    except Exception:
        return "main"


def _current_branch() -> str:
    out = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (out.stdout or "").strip()


def run_mirror(project: Path) -> None:
    """1プロジェクトの docs ミラーをサブプロセス実行(進捗は端末へ流す)。"""
    result = subprocess.run(
        [sys.executable, str(SHAREPOINT), "mirror", "--project", str(project)],
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        print(
            f"warn: {project.name} の docs ミラーに失敗(exit {result.returncode})。"
            "状態は進んでいないため次回コミット/プッシュ or 手動 mirror で追いつきます",
            file=sys.stderr,
        )


def run_all_mirrors() -> None:
    """現在ブランチが各プロジェクトのミラー対象ブランチと一致する場合のみミラーする。"""
    current = _current_branch()
    for project in _projects():
        if current == _project_branch(project):
            run_mirror(project)


def main() -> int:
    try:
        run_all_mirrors()
    except Exception as e:  # フックは何があってもコミットを妨げない
        print(f"warn: docs ミラーをスキップ: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
