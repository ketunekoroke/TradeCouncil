"""PreToolUse(Edit|Write) hook: 保護パスへの編集をブロック + 秘密情報を検査する。

- config/generated/  … 自動生成ビュー(tc policy sync 経由のみ)
- config/policies/*.yaml … 決裁レコード(tc policy record 経由のみ。README は編集可)
- prototype/         … MAGI プロトタイプ(編集禁止・参照のみ)
- var/               … 実行時生成物
- 書き込み内容に APIキー・Webhook 等が含まれる場合もブロック
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hook_common import deny, find_secret, read_hook_input  # noqa: E402


def main() -> None:
    data = read_hook_input()
    tool_input = data.get("tool_input") or {}
    file_path = (tool_input.get("file_path") or "").replace("\\", "/")

    if file_path:
        if "/config/generated/" in file_path:
            deny(
                "config/generated/ は自動生成ビュー(手編集禁止)。"
                "変更は `python -m scripts.cli policy sync` で再生成する"
            )
        if "/config/policies/" in file_path and file_path.endswith((".yaml", ".yml")):
            deny(
                "config/policies/*.yaml は決裁レコード経由でのみ変更できる(不変条項3)。"
                "`python -m scripts.cli policy record --file <決裁レコード>` を使う"
            )
        if "/prototype/" in file_path:
            deny("prototype/ は MAGI プロトタイプ(編集禁止・参照のみ)。CLAUDE.md 絶対ルール8")
        if "/var/" in file_path and "/TradeCouncil/var/" in file_path:
            deny("var/ は実行時生成物。手編集しない")

    content = tool_input.get("content") or tool_input.get("new_string") or ""
    label = find_secret(content)
    if label:
        deny(f"秘密情報らしき内容を検出: {label}。コード・設定に直接書かず .env を使う(絶対ルール4)")

    sys.exit(0)


if __name__ == "__main__":
    main()
