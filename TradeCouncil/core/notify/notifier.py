"""通知(FR-7.1)。Teams(Power Automate Workflows + Adaptive Card)/ Discord Webhook。

backend は config/system.yaml の notify.backend で切替(ADR-0002)。
マルチチャネル: チャネル別 URL(TEAMS_WORKFLOW_URL_<CHANNEL> 等)と
notify.routing(severity→チャネル名)で投稿先を振り分ける(ADR-0003)。
解決順: 明示 channel → routing[severity] → default URL → ログ fallback。
通知失敗で本体処理を止めない(通知はベストエフォート、安全機構ではない)。
注意: Power Automate Workflows は受信時に 202 Accepted を返すため、フロー内部の失敗
(チャネル削除等)は送信側から検知できない。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping
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

    def __init__(
        self,
        url: str | None,
        min_severity: str = "info",
        *,
        channel_urls: Mapping[str, str] | None = None,
        routing: Mapping[str, str] | None = None,
    ) -> None:
        self._url = url  # default URL(チャネル未解決時のフォールバック先)
        self._min_level = _SEVERITY_ORDER.get(min_severity, 0)
        self._channel_urls = dict(channel_urls or {})
        self._routing = dict(routing or {})

    def send(
        self,
        message: str,
        severity: str = "info",
        *,
        title: str | None = None,
        facts: dict[str, str] | None = None,
        channel: str | None = None,
    ) -> bool:
        """通知を送る。送信できた場合 True(失敗・抑制は False)。

        title / facts / channel はキーワード専用の任意引数(既存の message+severity
        呼び出しはそのまま動く)。channel を明示すると routing(severity→チャネル)
        より優先される。facts はキー値ペアとして構造化表示される(Teams は FactSet)。
        """
        if _SEVERITY_ORDER.get(severity, 0) < self._min_level:
            return False
        url, resolved_channel = self._resolve_url(channel, severity)
        if not url:
            logger.info(
                "notify(fallback): [%s]%s %s%s",
                severity.upper(),
                f" #{resolved_channel}" if resolved_channel else "",
                f"{title}: " if title else "",
                message,
            )
            return False
        try:
            payload = self._build_payload(
                message, severity, title, facts, channel=resolved_channel
            )
            response = httpx.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as exc:  # 通知失敗は本体を止めない
            logger.warning(
                "%s 通知に失敗 (channel=%s): %s",
                self.backend_name,
                resolved_channel or "default",
                exc,
            )
            return False

    def _resolve_url(
        self, channel: str | None, severity: str
    ) -> tuple[str | None, str | None]:
        """投稿先 URL を解決する: 明示 channel → routing[severity] → default URL。

        チャネルの URL が未設定でも通知を握りつぶさず default へフォールバックする。
        """
        name = channel or self._routing.get(severity)
        if name:
            url = self._channel_urls.get(name)
            if url:
                return url, name
            logger.warning("チャネル %r の URL 未設定 → default へフォールバック", name)
        return self._url, name

    @abstractmethod
    def _build_payload(
        self,
        message: str,
        severity: str,
        title: str | None,
        facts: dict[str, str] | None,
        *,
        channel: str | None = None,
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
        *,
        channel: str | None = None,
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
        *,
        channel: str | None = None,
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
        # チャネル名をフッターに出す: フローの投稿先誤配線をカード側から発見できる
        channel_suffix = f" | #{channel}" if channel else ""
        body.append(
            {
                "type": "TextBlock",
                "size": "Small",
                "isSubtle": True,
                "spacing": "Medium",
                "text": f"TradeCouncil Phase 0 (paper){channel_suffix}"
                f" | {datetime.now(UTC).isoformat(timespec='seconds')}",
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
    from core.config import (
        discord_channel_urls,
        discord_webhook_url,
        get_config,
        teams_channel_urls,
        teams_workflow_url,
    )

    cfg = get_config().notify
    if cfg.backend == "teams":
        return TeamsNotifier(
            teams_workflow_url(),
            cfg.min_severity,
            channel_urls=teams_channel_urls(),
            routing=cfg.routing,
        )
    return DiscordNotifier(
        discord_webhook_url(),
        cfg.min_severity,
        channel_urls=discord_channel_urls(),
        routing=cfg.routing,
    )
