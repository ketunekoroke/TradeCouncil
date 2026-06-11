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
