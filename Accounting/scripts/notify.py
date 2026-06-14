"""Teams 通知(scripts 層・stdlib urllib)。Power Automate Workflows へ Adaptive Card を POST する。

env(ADR-0011 命名規約・PREFIX=AC=system.yaml notify.env_prefix):
  `TEAMS_<PREFIX>_WORKFLOW_URL[_<CHANNEL>]`。チャネル別 → 既定 の順で解決。
送信は best-effort(失敗で本体を止めない)。core は zero-dep のため通知 I/O はここ(scripts/)。
"""

from __future__ import annotations

import datetime
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Accounting/

from core.config import get_setting  # noqa: E402

_TIMEOUT = 15
# severity → Adaptive Card の style/color。
_STYLE = {
    "info": "default", "good": "good", "warning": "warning",
    "attention": "attention", "error": "attention",
}


def workflow_url(channel: str | None = None, *, env_prefix: str = "AC") -> str | None:
    """Webhook URL を解決: チャネル別 → 既定(TEAMS_<PREFIX>_WORKFLOW_URL[_<CHANNEL>])。"""
    base = f"TEAMS_{env_prefix.upper()}_WORKFLOW_URL"
    names = [f"{base}_{channel.upper()}"] if channel else []
    names.append(base)
    return get_setting(*names)


def build_card(
    title: str,
    message: str = "",
    *,
    facts: dict | None = None,
    severity: str = "info",
    channel: str | None = None,
    now: str | None = None,
) -> dict:
    """Power Automate Workflows 用の Adaptive Card v1.4 ペイロードを組み立てる。"""
    style = _STYLE.get(severity, "default")
    body: list[dict] = [
        {
            "type": "Container", "style": style, "bleed": True,
            "items": [{
                "type": "TextBlock", "size": "Medium", "weight": "Bolder",
                "color": style, "wrap": True, "text": title,
            }],
        }
    ]
    if message:
        body.append({"type": "TextBlock", "wrap": True, "text": message})
    if facts:
        body.append({
            "type": "FactSet",
            "facts": [{"title": str(k), "value": str(v)} for k, v in facts.items()],
        })
    suffix = f" | #{channel}" if channel else ""
    body.append({
        "type": "TextBlock", "size": "Small", "isSubtle": True, "spacing": "Medium",
        "text": f"Accounting / 経費{suffix} | {now or _now()}",
    })
    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": None,
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard", "version": "1.4", "msteams": {"width": "Full"},
                "body": body,
            },
        }],
    }


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _default_post(url: str, payload: dict) -> int:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
        return resp.status


def send(
    channel: str,
    title: str,
    message: str = "",
    *,
    facts: dict | None = None,
    severity: str = "info",
    env_prefix: str = "AC",
    post=None,
) -> bool:
    """Teams へ送信(best-effort)。URL 未設定 / 失敗は False(例外を投げない)。"""
    url = workflow_url(channel, env_prefix=env_prefix)
    if not url:
        return False
    post = post or _default_post
    try:
        card = build_card(title, message, facts=facts, severity=severity, channel=channel)
        return 200 <= int(post(url, card)) < 300
    except (urllib.error.URLError, OSError, ValueError):
        return False
