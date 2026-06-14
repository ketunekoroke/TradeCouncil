"""scripts/notify.py: Teams Adaptive Card 生成と送信(URL 注入・無ネットワーク)。"""

import os

import pytest

from core import config
from scripts import notify


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.setattr(config, "_root_env", lambda: {})
    monkeypatch.setattr(config, "_settings_local_env", lambda: {})
    for k in list(os.environ):
        if k.startswith("TEAMS"):
            monkeypatch.delenv(k, raising=False)
    yield


def test_workflow_url_resolution(monkeypatch):
    monkeypatch.setenv("TEAMS_AC_WORKFLOW_URL", "https://default")
    monkeypatch.setenv("TEAMS_AC_WORKFLOW_URL_OPERATIONS", "https://ops")
    assert notify.workflow_url("operations") == "https://ops"
    assert notify.workflow_url("unknown") == "https://default"  # チャネル別が無ければ既定へ
    assert notify.workflow_url() == "https://default"


def test_build_card_structure():
    card = notify.build_card("題", "本文", facts={"a": "1"}, severity="good",
                             channel="operations", now="2026-06-15T00:00:00")
    assert card["type"] == "message"
    content = card["attachments"][0]["content"]
    assert content["type"] == "AdaptiveCard" and content["version"] == "1.4"
    assert any("本文" in b.get("text", "") for b in content["body"] if b.get("type") == "TextBlock")
    factsets = [b for b in content["body"] if b.get("type") == "FactSet"]
    assert factsets[0]["facts"] == [{"title": "a", "value": "1"}]


def test_send_no_url_returns_false():
    assert notify.send("operations", "t") is False  # URL 未設定 → 送信しない(best-effort)


def test_send_posts_when_url_set(monkeypatch):
    monkeypatch.setenv("TEAMS_AC_WORKFLOW_URL_OPERATIONS", "https://ops")
    seen = {}

    def fake_post(url, payload):
        seen.update(url=url, payload=payload)
        return 202

    assert notify.send("operations", "題", "本文", facts={"x": "y"}, post=fake_post) is True
    assert seen["url"] == "https://ops"
    assert seen["payload"]["attachments"][0]["content"]["type"] == "AdaptiveCard"


def test_send_failure_returns_false(monkeypatch):
    monkeypatch.setenv("TEAMS_AC_WORKFLOW_URL_OPERATIONS", "https://ops")

    def boom(url, payload):
        raise OSError("net")

    assert notify.send("operations", "t", post=boom) is False
