"""シークレット解決(.env 集約)のテスト。

解決順: OS 環境変数 → ルートの .env → .claude/settings.local.json の env。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared import bridge_common as bc


def test_parse_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# コメント行",
                "",
                "PLAIN=value1",
                "export EXPORTED=value2",
                'QUOTED="va=lue3"',
                "SINGLE='value4'",
                "EMPTY=",
                "イコールを含まない行は無視される",
                "SPACED = value5 ",
            ]
        ),
        encoding="utf-8",
    )
    env = bc.parse_env_file(str(env_file))
    assert env["PLAIN"] == "value1"
    assert env["EXPORTED"] == "value2"
    assert env["QUOTED"] == "va=lue3"
    assert env["SINGLE"] == "value4"
    assert env["EMPTY"] == ""
    assert env["SPACED"] == "value5"
    assert "# コメント行" not in env


def test_parse_env_file_missing_returns_empty(tmp_path: Path) -> None:
    assert bc.parse_env_file(str(tmp_path / "nope.env")) == {}


def test_get_setting_resolution_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TC_TEST_KEY", raising=False)
    monkeypatch.setattr(bc, "dotenv_env", lambda: {"TC_TEST_KEY": "from-dotenv"})
    monkeypatch.setattr(bc, "settings_env", lambda: {"TC_TEST_KEY": "from-settings"})

    # .env が settings.local.json より優先される
    assert bc.get_setting("TC_TEST_KEY") == "from-dotenv"

    # OS 環境変数が最優先
    monkeypatch.setenv("TC_TEST_KEY", "from-os")
    assert bc.get_setting("TC_TEST_KEY") == "from-os"


def test_get_setting_skips_placeholder_and_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TC_TEST_KEY", raising=False)
    monkeypatch.setattr(
        bc, "dotenv_env", lambda: {"TC_TEST_KEY": "REPLACE_WITH_YOUR_KEY", "TC_EMPTY": ""}
    )
    monkeypatch.setattr(bc, "settings_env", lambda: {"TC_TEST_KEY": "real-value"})
    # placeholder(REPLACE)・空文字は未設定扱いで次のソースへフォールバック
    assert bc.get_setting("TC_TEST_KEY") == "real-value"
    assert bc.get_setting("TC_EMPTY") is None


def test_get_setting_multiple_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TC_KEY_A", raising=False)
    monkeypatch.delenv("TC_KEY_B", raising=False)
    monkeypatch.setattr(bc, "dotenv_env", lambda: {"TC_KEY_B": "b-value"})
    monkeypatch.setattr(bc, "settings_env", lambda: {})
    assert bc.get_setting("TC_KEY_A", "TC_KEY_B") == "b-value"
    assert bc.get_setting("TC_KEY_A") is None
