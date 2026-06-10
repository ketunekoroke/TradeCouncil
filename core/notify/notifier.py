"""Discord Webhook 通知(FR-7.1)。

DISCORD_WEBHOOK_URL 未設定時はログ出力にフォールバックする(Phase 0 はこれで十分)。
通知失敗で本体処理を止めない(通知はベストエフォート、安全機構ではない)。
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("tradecouncil.notify")

_SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}
_SEVERITY_EMOJI = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}


class Notifier:
    def __init__(self, webhook_url: str | None, min_severity: str = "info") -> None:
        self._webhook_url = webhook_url
        self._min_level = _SEVERITY_ORDER.get(min_severity, 0)

    def send(self, message: str, severity: str = "info") -> bool:
        """通知を送る。送信できた場合 True(失敗・抑制は False)。"""
        if _SEVERITY_ORDER.get(severity, 0) < self._min_level:
            return False
        text = f"{_SEVERITY_EMOJI.get(severity, '')} [{severity.upper()}] {message}"
        if not self._webhook_url:
            logger.info("notify(fallback): %s", text)
            return False
        try:
            response = httpx.post(self._webhook_url, json={"content": text[:1900]}, timeout=10)
            response.raise_for_status()
            return True
        except Exception as exc:  # 通知失敗は本体を止めない
            logger.warning("Discord通知に失敗: %s", exc)
            return False


def get_notifier() -> Notifier:
    from core.config import discord_webhook_url, get_config

    return Notifier(discord_webhook_url(), get_config().notify.min_severity)
