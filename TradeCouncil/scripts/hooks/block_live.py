"""PreToolUse(Bash) hook: 実弾系・人間専用コマンドをブロックする。

- live 系(将来追加されても発火するよう予防的にパターン拒否)
- キルスイッチの解除(tc resume / KILL フラグ削除)は人間専用
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hook_common import deny, read_hook_input  # noqa: E402

BLOCKED = [
    (r"(scripts\.cli|tc(\.exe)?)\s+.*\blive\b", "実弾(live)操作は人間の手でのみ実行する(CLAUDE.md 絶対ルール3)"),
    (r"\bmake\s+live\b", "実弾(live)操作は人間の手でのみ実行する"),
    (r"(scripts\.cli|tc(\.exe)?)\s+resume\b", "キルスイッチの解除(resume)は人間専用(不変条項4)"),
    (r"(Remove-Item|rm|del|unlink)\b[^\n;|&]*\bKILL\b", "KILLフラグの削除は人間専用(不変条項4)"),
]


def main() -> None:
    data = read_hook_input()
    command = (data.get("tool_input") or {}).get("command", "")
    for pattern, reason in BLOCKED:
        if re.search(pattern, command):
            deny(f"ブロック: {reason}\n該当コマンド: {command[:200]}")
    sys.exit(0)


if __name__ == "__main__":
    main()
