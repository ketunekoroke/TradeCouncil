"""PreToolUse(Edit|Write) hook: 保護パスへの編集をブロック + 秘密情報を検査する。

- docs/accounting-policy.md … 会計ポリシーの正本。改定はポリシー改定手順(適用開始日・理由・コミット)で行う。
  自動的な書き換えを防ぐため、編集時に手順を促す(ブロックして人間に確認させる)。
- config/generated/  … 自動生成ビュー(存在する場合は手編集禁止)
- var/ / var-*/      … 実行時生成物(経理データ・ログ)
- 書き込み内容に APIキー・Client Secret・Webhook 等が含まれる場合もブロック(秘匿情報非コミット)。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hook_common import deny, find_secret, read_hook_input  # noqa: E402


def main() -> None:
    data = read_hook_input()
    tool_input = data.get("tool_input") or {}
    file_path = (tool_input.get("file_path") or "").replace("\\", "/")

    if file_path:
        if file_path.endswith("/docs/accounting-policy.md") or file_path.endswith("docs/accounting-policy.md"):
            deny(
                "docs/accounting-policy.md は会計ポリシーの正本です。改定はポリシー改定手順で行ってください"
                "(適用開始日・理由を明記し、コミット要約 `policy: ...`)。本当に改定する場合は手順に沿って進めます。"
            )
        if "/config/generated/" in file_path:
            deny("config/generated/ は自動生成ビュー(手編集禁止)。生成スクリプト経由で再生成してください")
        if re.search(r"/Accounting/var(-[^/]+)?/", file_path):
            deny("var/(実行時生成物・経理データ・ログ)は手編集しません")

    content = tool_input.get("content") or tool_input.get("new_string") or ""
    label = find_secret(content)
    if label:
        deny(f"秘密情報らしき内容を検出: {label}。コード・設定に直接書かず .env を使う(秘匿情報非コミット)")

    sys.exit(0)


if __name__ == "__main__":
    main()
