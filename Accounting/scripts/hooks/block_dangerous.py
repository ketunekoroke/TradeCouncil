"""PreToolUse(Bash) hook: 不可逆・人間専用の操作をブロックする(会計経理向け)。

会計エージェントにさせてはならない不可逆操作(docs/caveats.md・CLAUDE.md YOU MUST):
- 送金・資金移動・支払の実行(MoneyForward 等の支払/振込系 API への書き込み)
- 帳簿・証憑・台帳の削除(var/ や workspace の経理データの破壊)
- 権限/共有設定の変更・認証情報の入力

パターンは予防的(将来コマンドが増えても発火する)。最終判断と実行は人間が行う。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hook_common import deny, read_hook_input  # noqa: E402

BLOCKED: list[tuple[str, str]] = [
    # 送金・支払・資金移動(語・API パスの双方を予防的に拒否)
    (r"(?i)\b(transfer|remit|payout|wire|withdraw)\b", "送金・資金移動はエージェントが実行しない(人間専用)"),
    (r"送金|振込|資金移動|支払実行", "送金・資金移動はエージェントが実行しない(人間専用)"),
    (r"(?i)(POST|PUT|DELETE)\b[^\n;|&]*\b(payments?|transfers?|withdrawals?|payouts?)\b",
     "支払/振込系 API への書き込みはエージェントが実行しない(人間専用)"),
    # 帳簿・証憑・台帳の削除(経理データの破壊)
    (r"(?i)(Remove-Item|rm|del|unlink)\b[^\n;|&]*\b(ledger|journal|receipt|evidence|var|workspace)\b",
     "帳簿・証憑・台帳の削除はエージェントが実行しない(人間専用)"),
    (r"(?i)(DROP|TRUNCATE|DELETE)\s+(TABLE|FROM)\b", "会計データの破壊的 SQL はエージェントが実行しない(人間専用)"),
    # 権限・共有設定の変更
    (r"(?i)\b(icacls|chmod|chown|Set-Acl|Grant-)\b", "権限/共有設定の変更はエージェントが実行しない(人間専用)"),
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
