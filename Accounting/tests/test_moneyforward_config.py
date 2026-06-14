"""MoneyForward API 設定の解決(per-project env → config → 共有 env)・マスク・CLI 検証。"""

import json
import os

import pytest

from core import config, moneyforward as mf


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """実 .env / settings.local に依存させない。os.environ の MONEYFORWARD_* も毎回クリア。"""
    monkeypatch.setattr(config, "_root_env", lambda: {})
    monkeypatch.setattr(config, "_settings_local_env", lambda: {})
    for key in list(os.environ):
        if key.startswith("MONEYFORWARD"):
            monkeypatch.delenv(key, raising=False)
    yield


def _write_config(tmp_path, **overrides) -> "os.PathLike":
    base = {
        "enabled": False,
        "env_prefix": "AC",
        "client_id": "",
        "oauth": {"authorize_url": "", "token_url": "", "redirect_uri": "http://localhost/cb", "scopes": []},
        "api": {"expense_base": "", "accounting_base": "", "box_base": ""},
    }
    base.update(overrides)
    path = tmp_path / "moneyforward.config.json"
    path.write_text(json.dumps(base), encoding="utf-8")
    return path


def test_per_project_env_wins_over_shared(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEYFORWARD_CLIENT_SECRET", "shared-secret")
    monkeypatch.setenv("MONEYFORWARD_AC_CLIENT_SECRET", "ac-secret")
    cfg = mf.load_config(_write_config(tmp_path))
    assert cfg.client_secret == "ac-secret"


def test_shared_env_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEYFORWARD_CLIENT_SECRET", "shared-secret")
    cfg = mf.load_config(_write_config(tmp_path))
    assert cfg.client_secret == "shared-secret"


def test_config_value_used_when_no_env(tmp_path):
    cfg = mf.load_config(
        _write_config(tmp_path, oauth={"token_url": "https://example.test/token", "scopes": ["a", "b"]})
    )
    assert cfg.token_url == "https://example.test/token"
    assert cfg.scopes == ["a", "b"]


def test_env_overrides_config_url(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEYFORWARD_AC_TOKEN_URL", "https://env.test/token")
    cfg = mf.load_config(_write_config(tmp_path, oauth={"token_url": "https://config.test/token"}))
    assert cfg.token_url == "https://env.test/token"


def test_placeholder_in_config_ignored(tmp_path):
    cfg = mf.load_config(_write_config(tmp_path, client_id="<your-client-id>"))
    assert cfg.client_id is None  # プレースホルダは実値として採用しない


def test_missing_required_and_mask_does_not_leak(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEYFORWARD_CLIENT_SECRET", "super-secret-value")
    cfg = mf.load_config(_write_config(tmp_path))  # client_id / token_url 未設定
    assert "client_id" in cfg.missing_required()
    assert "token_url" in cfg.missing_required()
    assert "client_secret" not in cfg.missing_required()
    masked = cfg.masked()
    assert "super-secret-value" not in json.dumps(masked, ensure_ascii=False)
    assert masked["client_secret"].startswith("set(")


def test_ready_when_all_required_set(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEYFORWARD_CLIENT_ID", "cid-123456")
    monkeypatch.setenv("MONEYFORWARD_CLIENT_SECRET", "sec")
    cfg = mf.load_config(_write_config(tmp_path, oauth={"token_url": "https://example.test/token"}))
    assert cfg.is_ready()
    assert cfg.missing_required() == []


def test_real_config_file_is_valid_json():
    cfg = mf.load_config()  # 実ファイル(config/moneyforward.config.json)
    assert cfg.env_prefix == "AC"
    # 既定では未設定なので ready ではない(秘密・URL は運用で投入)
    assert not cfg.is_ready()


def test_cli_mf_config_check_exit_codes(monkeypatch, capsys):
    from scripts import cli

    # 未設定 → --check は exit 1
    assert cli.main(["mf", "config", "--check"]) == 1
    # 必須を env で満たす → exit 0(実 config の空欄を共有 env で補う)
    monkeypatch.setenv("MONEYFORWARD_CLIENT_ID", "cid99999")
    monkeypatch.setenv("MONEYFORWARD_CLIENT_SECRET", "topsecretvalue-abc123")
    monkeypatch.setenv("MONEYFORWARD_TOKEN_URL", "https://example.test/token")
    assert cli.main(["mf", "config", "--check"]) == 0
    out = capsys.readouterr().out
    assert "topsecretvalue-abc123" not in out  # 秘密の値は出力に漏れない
