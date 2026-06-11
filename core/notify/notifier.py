"""通知(FR-7.1)。Teams(Power Automate Workflows + Adaptive Card)/ Discord Webhook。

backend は config/system.yaml の notify.backend で切替(ADR-0002)。
URL(TEAMS_WORKFLOW_URL / DISCORD_WEBHOOK_URL)未設定時はログ出力にフォールバックする。
通知失敗で本体処理を止めない(通知はベストエフォート、安全機構ではない)。
注意: Power Automate Workflows は受信時に 202 Accepted を返すため、フロー内部の失敗
(チャネル削除等)は送信側から検知できない。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime

import httpx

logger = logging.getLogger("tradecouncil.notify")

_SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}
_SEVERITY_EMOJI = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}
# Adaptive Card の Container.style / TextBlock.color に対応する値
_TEAMS_STYLE = {"info": "default", "warning": "warning", "critical": "attention"}
_DISCORD_MAX = 1900
_TEAMS_TEXT_MAX = 4000  # Workflows のペイロード上限(約28KB)への安全マージン


class Notifier(ABC):
    """通知バックエンドの抽象基底。severity フィルタ・fallback・例外吸収を共通化する。"""

    backend_name: str = "base"

    def __init__(self, url: str | None, min_severity: str = "info") -> None:
        self._url = url
        self._min_level = _SEVERITY_ORDER.get(min_severity, 0)

    def send(
        self,
        message: str,
        severity: str = "info",
        *,
        title: str | None = None,
        facts: dict[str, str] | None = None,
    ) -> bool:
        """通知を送る。送信できた場合 True(失敗・抑制は False)。

        title / facts はキーワード専用の任意引数(既存の message+severity 呼び出しは
        そのまま動く)。facts はキー値ペアとして構造化表示される(Teams は FactSet)。
        """
        if _SEVERITY_ORDER.get(severity, 0) < self._min_level:
            return False
        if not self._url:
            logger.info(
                "notify(fallback): [%s] %s%s",
                severity.upper(),
                f"{title}: " if title else "",
                message,
            )
            return False
        try:
            payload = self._build_payload(message, severity, title, facts)
            response = httpx.post(self._url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as exc:  # 通知失敗は本体を止めない
            logger.warning("%s 通知に失敗: %s", self.backend_name, exc)
            return False

    @abstractmethod
    def _build_payload(
        self,
        message: str,
        severity: str,
        title: str | None,
        facts: dict[str, str] | None,
    ) -> dict:
        """backend 固有の POST ペイロードを構築する。"""


class DiscordNotifier(Notifier):
    """Discord Webhook(プレーンテキスト)。予備チャネル。"""

    backend_name = "discord"

    def _build_payload(
        self,
        message: str,
        severity: str,
        title: str | None,
        facts: dict[str, str] | None,
    ) -> dict:
        head = f"{_SEVERITY_EMOJI.get(severity, '')} [{severity.upper()}]"
        text = f"{head} **{title}**\n{message}" if title else f"{head} {message}"
        if facts:
            text += "\n" + "\n".join(f"- {k}: {v}" for k, v in facts.items())
        return {"content": text[:_DISCORD_MAX]}


class TeamsNotifier(Notifier):
    """Microsoft Teams(Power Automate Workflows へ Adaptive Card v1.4 を POST)。"""

    backend_name = "teams"

    def _build_payload(
        self,
        message: str,
        severity: str,
        title: str | None,
        facts: dict[str, str] | None,
    ) -> dict:
        style = _TEAMS_STYLE.get(severity, "default")
        header = f"[{severity.upper()}] {title or 'TradeCouncil'}"
        body: list[dict] = [
            {
                "type": "Container",
                "style": style,
                "bleed": True,
                "items": [
                    {
                        "type": "TextBlock",
                        "size": "Medium",
                        "weight": "Bolder",
                        "color": style,
                        "wrap": True,
                        "text": header,
                    }
                ],
            },
            {"type": "TextBlock", "wrap": True, "text": message[:_TEAMS_TEXT_MAX]},
        ]
        if facts:
            body.append(
                {
                    "type": "FactSet",
                    "facts": [{"title": k, "value": v} for k, v in facts.items()],
                }
            )
        body.append(
            {
                "type": "TextBlock",
                "size": "Small",
                "isSubtle": True,
                "spacing": "Medium",
                "text": f"TradeCouncil Phase 0 (paper) | {datetime.now(UTC).isoformat(timespec='seconds')}",
            }
        )
        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "contentUrl": None,
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "msteams": {"width": "Full"},
                        "body": body,
                    },
                }
            ],
        }


def get_notifier() -> Notifier:
    from core.config import discord_webhook_url, get_config, teams_workflow_url

    cfg = get_config().notify
    if cfg.backend == "teams":
        return TeamsNotifier(teams_workflow_url(), cfg.min_severity)
    return DiscordNotifier(discord_webhook_url(), cfg.min_severity)
