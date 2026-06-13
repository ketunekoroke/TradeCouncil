"""shared/hooks — リポジトリ単位の git ライフサイクルフック(秘密/ポリシー検査・docs ミラー)。

git は1リポジトリに1組のフックしか持てないため、ここに**リポジトリ横断**のフックを置く。
`install_hooks(repo_root)` が .git/hooks に3種(pre-commit / post-commit / pre-push)を書く。
"""

from __future__ import annotations

from pathlib import Path

_LIFECYCLE = {
    "pre-commit": "pre_commit.py",
    "post-commit": "post_commit.py",
    "pre-push": "pre_push.py",
}


def install_hooks(repo_root) -> list[Path]:
    """.git/hooks へ3種のフックを書き込む(冪等・再実行で上書き)。書いたパスを返す。

    各フックは shared/hooks/<script>.py をリポジトリ共有 .venv の python で実行する。
    """
    repo_root = Path(repo_root)
    python = repo_root / ".venv" / "Scripts" / "python.exe"
    src = repo_root / "shared" / "hooks"
    written = []
    for name, script in _LIFECYCLE.items():
        hook_path = repo_root / ".git" / "hooks" / name
        hook_path.write_text(
            "#!/bin/sh\n" f'"{python}" "{src / script}"\n',
            encoding="utf-8",
        )
        written.append(hook_path)
    return written
