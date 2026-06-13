"""Claude Code hooks 共通処理(stdin JSON の読み取り)。"""

from __future__ import annotations

import json
import sys
from typing import Any


def read_hook_input() -> dict[str, Any]:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def deny(message: str) -> None:
    """exit 2 = ツール実行をブロックし、メッセージを Claude に返す。"""
    print(message, file=sys.stderr)
    sys.exit(2)


SECRET_PATTERNS: list[tuple[str, str]] = [
    (r"sk-[A-Za-z0-9_\-]{20,}", "OpenAI/Anthropic 形式のAPIキー"),
    (r"AIza[A-Za-z0-9_\-]{30,}", "Google APIキー"),
    (r"AKIA[A-Z0-9]{16}", "AWS アクセスキー"),
    (r"discord(app)?\.com/api/webhooks/\d+/[A-Za-z0-9_\-]+", "Discord Webhook URL"),
    # sig=(SAS署名)を含む場合のみ秘密扱い。sig なしのプレースホルダは許容する
    (r"https://[\w.-]+\.logic\.azure\.com[:/][^\s\"']*sig=[A-Za-z0-9_\-%]{10,}",
     "Power Automate Workflow URL(sig付き)"),
    (r"https://[\w.-]+\.api\.powerplatform\.com/[^\s\"']*sig=[A-Za-z0-9_\-%]{10,}",
     "Power Platform Workflow URL(sig付き)"),
    (r"(?i)(api_key|secret|token|password)\s*[:=]\s*['\"][A-Za-z0-9_\-/+]{16,}['\"]", "資格情報らしき代入"),
]


def find_secret(text: str) -> str | None:
    import re

    for pattern, label in SECRET_PATTERNS:
        if re.search(pattern, text):
            return label
    return None
