"""notifier のテスト(TC-302 ほか)。

httpx.post をモックし、実際の送信は行わない。
注意: sig= 付き URL はシークレット検出(hook_common)の対象なので、
テスト内では実行時に文字列結合で組み立てる(ソースに直書きしない)。
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

import core.notify.notifier as notifier_mod
from core.config import NotifyConfig
from core.notify import DiscordNotifier, TeamsNotifier, get_notifier
from scripts.hooks.hook_common import find_secret

DUMMY_URL = "https://example.invalid/workflow"


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None


@pytest.fixture
def posted(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """httpx.post を記録用スタブに差し替え、送信ペイロードのリストを返す。"""
    calls: list[dict[str, Any]] = []

    def fake_post(url: str, json: dict, timeout: float) -> _FakeResponse:
        calls.append({"url": url, "json": json, "timeout": timeout})
        return _FakeResponse()

    monkeypatch.setattr(notifier_mod.httpx, "post", fake_post)
    return calls


# --- 共通挙動 ---


def test_severity_filter_suppresses_below_min(posted: list) -> None:
    n = TeamsNotifier(DUMMY_URL, min_severity="warning")
    assert n.send("情報", "info") is False
    assert posted == []


def test_fallback_to_log_when_url_missing(
    posted: list, caplog: pytest.LogCaptureFixture
) -> None:
    n = TeamsNotifier(None)
    with caplog.at_level("INFO", logger="tradecouncil.notify"):
        assert n.send("テスト", "critical") is False
    assert posted == []
    assert "notify(fallback)" in caplog.text
    assert "CRITICAL" in caplog.text


def test_send_exception_is_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("network down")

    monkeypatch.setattr(notifier_mod.httpx, "post", boom)
    for n in (DiscordNotifier(DUMMY_URL), TeamsNotifier(DUMMY_URL)):
        assert n.send("失敗しても伝播しない", "critical") is False


def test_send_backward_compatible_two_positional_args(posted: list) -> None:
    """既存呼び出し(bot_runner / watchdog)の 2 引数形式が通る。"""
    assert DiscordNotifier(DUMMY_URL).send("メッセージ", "warning") is True
    assert TeamsNotifier(DUMMY_URL).send("メッセージ", "warning") is True
    assert len(posted) == 2


# --- Discord ---


def test_discord_payload_format(posted: list) -> None:
    DiscordNotifier(DUMMY_URL).send("BOT停止", "critical")
    payload = posted[0]["json"]
    assert set(payload) == {"content"}
    assert "[CRITICAL]" in payload["content"]
    assert "BOT停止" in payload["content"]


def test_discord_truncates_at_1900(posted: list) -> None:
    DiscordNotifier(DUMMY_URL).send("x" * 5000, "info")
    assert len(posted[0]["json"]["content"]) <= 1900


def test_discord_title_and_facts(posted: list) -> None:
    DiscordNotifier(DUMMY_URL).send(
        "本文", "warning", title="日次サマリ", facts={"注文": "12", "約定": "10"}
    )
    content = posted[0]["json"]["content"]
    assert "日次サマリ" in content
    assert "- 注文: 12" in content
    assert "- 約定: 10" in content


# --- Teams(Adaptive Card)---


def _card(posted: list) -> dict:
    payload = posted[-1]["json"]
    assert payload["type"] == "message"
    attachment = payload["attachments"][0]
    assert attachment["contentType"] == "application/vnd.microsoft.card.adaptive"
    return attachment["content"]


def test_teams_payload_is_adaptive_card(posted: list) -> None:
    TeamsNotifier(DUMMY_URL).send("約定しました", "info", title="約定")
    card = _card(posted)
    assert card["type"] == "AdaptiveCard"
    assert card["version"] == "1.4"
    texts = json.dumps(card, ensure_ascii=False)
    assert "約定しました" in texts
    assert "[INFO] 約定" in texts


@pytest.mark.parametrize(
    ("severity", "style"),
    [("info", "default"), ("warning", "warning"), ("critical", "attention")],
)
def test_teams_severity_maps_to_style(posted: list, severity: str, style: str) -> None:
    TeamsNotifier(DUMMY_URL).send("msg", severity)
    header_container = _card(posted)["body"][0]
    assert header_container["style"] == style
    assert header_container["items"][0]["color"] == style


def test_teams_factset_only_when_facts_given(posted: list) -> None:
    n = TeamsNotifier(DUMMY_URL)
    n.send("factsなし", "info")
    assert all(b["type"] != "FactSet" for b in _card(posted)["body"])
    n.send("factsあり", "info", facts={"realized": "+3,420円"})
    fact_sets = [b for b in _card(posted)["body"] if b["type"] == "FactSet"]
    assert fact_sets == [
        {"type": "FactSet", "facts": [{"title": "realized", "value": "+3,420円"}]}
    ]


def test_teams_payload_stays_under_28kb(posted: list) -> None:
    TeamsNotifier(DUMMY_URL).send("y" * 100_000, "critical")
    assert len(json.dumps(posted[0]["json"])) < 28 * 1024


# --- 設定・ファクトリ ---


def test_get_notifier_backend_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.config as config_mod

    def fake_config(backend: str) -> Any:
        cfg = config_mod.load_config()
        cfg.notify.backend = backend  # type: ignore[assignment]
        return cfg

    monkeypatch.setattr(config_mod, "get_config", lambda: fake_config("teams"))
    assert isinstance(get_notifier(), TeamsNotifier)
    monkeypatch.setattr(config_mod, "get_config", lambda: fake_config("discord"))
    assert isinstance(get_notifier(), DiscordNotifier)


def test_notify_config_rejects_unknown_backend() -> None:
    with pytest.raises(ValidationError):
        NotifyConfig(backend="slack")  # type: ignore[arg-type]


# --- マルチチャネルルーティング(ADR-0003)---

OPS_URL = "https://example.invalid/wf-ops"
ALERTS_URL = "https://example.invalid/wf-alerts"
GOV_URL = "https://example.invalid/wf-governance"
ROUTING = {"info": "ops", "warning": "alerts", "critical": "alerts"}
CHANNEL_URLS = {"ops": OPS_URL, "alerts": ALERTS_URL, "governance": GOV_URL}


def _multi(url: str | None = DUMMY_URL, **kwargs: Any) -> TeamsNotifier:
    kwargs.setdefault("channel_urls", CHANNEL_URLS)
    kwargs.setdefault("routing", ROUTING)
    return TeamsNotifier(url, **kwargs)


def test_routing_maps_severity_to_channel_url(posted: list) -> None:
    n = _multi()
    n.send("停止", "critical")
    assert posted[-1]["url"] == ALERTS_URL
    n.send("サマリ", "info")
    assert posted[-1]["url"] == OPS_URL


def test_explicit_channel_overrides_routing(posted: list) -> None:
    _multi().send("決裁待ち提案があります", "warning", channel="governance")
    assert posted[-1]["url"] == GOV_URL


def test_routing_unmapped_severity_uses_default(posted: list) -> None:
    n = TeamsNotifier(DUMMY_URL, channel_urls=CHANNEL_URLS, routing={"critical": "alerts"})
    n.send("info は routing 未記載", "info")
    assert posted[-1]["url"] == DUMMY_URL


def test_unknown_channel_falls_back_to_default_with_warning(
    posted: list, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("WARNING", logger="tradecouncil.notify"):
        assert _multi().send("typo チャネル", "info", channel="alers") is True
    assert posted[-1]["url"] == DUMMY_URL
    assert "alers" in caplog.text
    assert "フォールバック" in caplog.text


def test_channel_url_missing_falls_back_to_default(
    posted: list, caplog: pytest.LogCaptureFixture
) -> None:
    n = TeamsNotifier(DUMMY_URL, channel_urls={}, routing=ROUTING)
    with caplog.at_level("WARNING", logger="tradecouncil.notify"):
        assert n.send("ops の URL なし", "info") is True
    assert posted[-1]["url"] == DUMMY_URL
    assert "'ops'" in caplog.text


def test_channel_url_used_when_default_missing(posted: list) -> None:
    n = _multi(url=None)
    assert n.send("default なしでもチャネル URL があれば送れる", "critical") is True
    assert posted[-1]["url"] == ALERTS_URL


def test_no_url_at_all_falls_back_to_log_with_channel(
    posted: list, caplog: pytest.LogCaptureFixture
) -> None:
    n = TeamsNotifier(None, channel_urls={}, routing=ROUTING)
    with caplog.at_level("INFO", logger="tradecouncil.notify"):
        assert n.send("全 URL なし", "critical") is False
    assert posted == []
    assert "notify(fallback)" in caplog.text
    assert "#alerts" in caplog.text


def test_severity_filter_applies_before_channel_resolution(posted: list) -> None:
    n = _multi(min_severity="warning")
    assert n.send("info は抑制", "info", channel="governance") is False
    assert posted == []


def test_legacy_construction_behaves_as_before(posted: list) -> None:
    """channel_urls / routing 未指定の従来構築は常に default URL へ(後方互換)。"""
    n = TeamsNotifier(DUMMY_URL)
    assert n.send("従来呼び出し", "critical") is True
    assert posted[-1]["url"] == DUMMY_URL


def test_discord_routing_symmetric(posted: list) -> None:
    n = DiscordNotifier(DUMMY_URL, channel_urls=CHANNEL_URLS, routing=ROUTING)
    n.send("停止", "critical")
    assert posted[-1]["url"] == ALERTS_URL
    n.send("決裁", "info", channel="governance")
    assert posted[-1]["url"] == GOV_URL


def test_teams_footer_contains_channel(posted: list) -> None:
    _multi().send("msg", "critical")
    footer = _card(posted)["body"][-1]["text"]
    assert "#alerts" in footer
    TeamsNotifier(DUMMY_URL).send("チャネル未解決", "critical")
    assert "#" not in _card(posted)["body"][-1]["text"].replace("Phase 0", "")


def test_notify_config_routing_defaults_empty() -> None:
    assert NotifyConfig().routing == {}


def test_notify_config_rejects_unknown_severity_key() -> None:
    with pytest.raises(ValidationError):
        NotifyConfig(routing={"fatal": "ops"})


@pytest.mark.parametrize("bad", ["", "OPS", "日本語", "a-b", "1ops"])
def test_notify_config_rejects_invalid_channel_name(bad: str) -> None:
    with pytest.raises(ValidationError):
        NotifyConfig(routing={"info": bad})


def test_get_notifier_builds_channel_urls_from_env(
    posted: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    import core.config as config_mod

    # load_config() 内の load_dotenv が実 .env から URL を再注入しないよう無効化し、
    # そのうえで実環境の URL を遮断してテスト値だけを注入する(実 .env の内容に非依存)
    monkeypatch.setattr(config_mod, "load_dotenv", lambda *a, **k: None)
    for key in list(__import__("os").environ):
        if key.startswith(("TEAMS_WORKFLOW_URL", "DISCORD_WEBHOOK_URL")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("TEAMS_WORKFLOW_URL", DUMMY_URL)
    monkeypatch.setenv("TEAMS_WORKFLOW_URL_ALERTS", ALERTS_URL)

    cfg = config_mod.load_config()
    cfg.notify.backend = "teams"  # type: ignore[assignment]
    cfg.notify.routing = ROUTING
    monkeypatch.setattr(config_mod, "get_config", lambda: cfg)

    n = get_notifier()
    n.send("critical は alerts へ", "critical")
    assert posted[-1]["url"] == ALERTS_URL
    n.send("ops は URL 未設定 → default", "info")
    assert posted[-1]["url"] == DUMMY_URL


# --- シークレット検出(hook)---


def test_hook_detects_workflow_url_with_sig() -> None:
    url = (
        "https://prod-01.japaneast.logic.azure.com/workflows/abc123/triggers/"
        "manual/paths/invoke?api-version=2016-06-01&sig=" + "A1b2C3d4E5f6G7h8"
    )
    assert find_secret(url) == "Power Automate Workflow URL(sig付き)"
    url2 = "https://env-x.api.powerplatform.com/flows/y/run?sig=" + "Z9y8X7w6V5u4T3s2"
    assert find_secret(url2) == "Power Platform Workflow URL(sig付き)"


def test_hook_allows_placeholder_without_sig() -> None:
    placeholder = "https://prod-XX.japaneast.logic.azure.com/workflows/.../invoke"
    assert find_secret(placeholder) is None
