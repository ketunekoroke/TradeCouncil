"""MoneyForward API 設定(会計 / 経費の2系統)の解決・独立性・マスク・CLI 検証。"""

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


def _write_config(tmp_path, accounting=None, expense=None):
    def _product(extra):
        base = {
            "enabled": False,
            "client_id": "",
            "oauth": {"authorize_url": "", "token_url": "", "redirect_uri": "https://x/cb", "scopes": []},
            "api": {"base": ""},
        }
        if extra:
            base.update(extra)
        return base

    data = {"products": {"accounting": _product(accounting), "expense": _product(expense)}}
    path = tmp_path / "moneyforward.config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_products_are_independent(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEYFORWARD_ACCOUNTING_CLIENT_SECRET", "acct-secret")
    monkeypatch.setenv("MONEYFORWARD_EXPENSE_CLIENT_SECRET", "exp-secret")
    cfg = mf.load_config(_write_config(tmp_path))
    assert cfg.get("accounting").client_secret == "acct-secret"
    assert cfg.get("expense").client_secret == "exp-secret"


def test_expense_secret_does_not_leak_into_accounting(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEYFORWARD_EXPENSE_CLIENT_SECRET", "exp-secret")
    cfg = mf.load_config(_write_config(tmp_path))
    assert cfg.get("expense").client_secret == "exp-secret"
    assert cfg.get("accounting").client_secret is None


def test_config_value_used_when_no_env(tmp_path):
    cfg = mf.load_config(
        _write_config(tmp_path, expense={"oauth": {"token_url": "https://e.test/token", "scopes": ["a", "b"]}})
    )
    pc = cfg.get("expense")
    assert pc.token_url == "https://e.test/token"
    assert pc.scopes == ["a", "b"]


def test_env_overrides_config_url(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEYFORWARD_EXPENSE_TOKEN_URL", "https://env.test/token")
    cfg = mf.load_config(_write_config(tmp_path, expense={"oauth": {"token_url": "https://config.test/token"}}))
    assert cfg.get("expense").token_url == "https://env.test/token"


def test_scopes_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEYFORWARD_EXPENSE_SCOPES", "transaction:write public_resource:read")
    cfg = mf.load_config(_write_config(tmp_path))
    assert cfg.get("expense").scopes == ["transaction:write", "public_resource:read"]


def test_placeholder_in_config_ignored(tmp_path):
    cfg = mf.load_config(_write_config(tmp_path, accounting={"client_id": "<your-client-id>"}))
    assert cfg.get("accounting").client_id is None


def test_missing_required_and_mask_does_not_leak(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEYFORWARD_EXPENSE_CLIENT_SECRET", "super-secret-value-xyz")
    pc = mf.load_config(_write_config(tmp_path)).get("expense")  # client_id / token_url 未設定
    assert "client_id" in pc.missing_required()
    assert "token_url" in pc.missing_required()
    assert "client_secret" not in pc.missing_required()
    masked = pc.masked()
    assert "super-secret-value-xyz" not in json.dumps(masked, ensure_ascii=False)
    assert masked["client_secret"].startswith("set(")


def test_ready_when_all_required_set(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEYFORWARD_EXPENSE_CLIENT_ID", "cid-123456")
    monkeypatch.setenv("MONEYFORWARD_EXPENSE_CLIENT_SECRET", "sec")
    cfg = mf.load_config(_write_config(tmp_path, expense={"oauth": {"token_url": "https://e.test/token"}}))
    assert cfg.get("expense").is_ready()
    assert cfg.ready_products() == ["expense"]


def test_real_config_file_has_default_endpoints():
    cfg = mf.load_config()  # 実ファイル(config/moneyforward.config.json)
    assert cfg.get("accounting").token_url == "https://api.biz.moneyforward.com/token"
    assert cfg.get("expense").token_url == "https://expense.moneyforward.com/oauth/token"
    # 既定では secret/client_id 未設定なので ready ではない
    assert cfg.ready_products() == []


def test_build_authorize_url(tmp_path, monkeypatch):
    import urllib.parse

    monkeypatch.setenv("MONEYFORWARD_ACCOUNTING_CLIENT_ID", "cid-abc")
    cfg = mf.load_config(
        _write_config(
            tmp_path,
            accounting={
                "oauth": {
                    "authorize_url": "https://api.biz.moneyforward.com/authorize",
                    "redirect_uri": "http://localhost:8765/callback",
                    "scopes": ["mfc/invoice/data.read", "mfc/invoice/data.write"],
                }
            },
        )
    )
    url = mf.build_authorize_url(cfg.get("accounting"), state="xyz")
    parsed = urllib.parse.urlparse(url)
    q = urllib.parse.parse_qs(parsed.query)
    assert parsed.scheme == "https" and parsed.netloc == "api.biz.moneyforward.com"
    assert q["response_type"] == ["code"]
    assert q["client_id"] == ["cid-abc"]
    assert q["redirect_uri"] == ["http://localhost:8765/callback"]
    assert q["scope"] == ["mfc/invoice/data.read mfc/invoice/data.write"]
    assert q["state"] == ["xyz"]


def test_build_authorize_url_requires_client_id(tmp_path):
    cfg = mf.load_config(
        _write_config(tmp_path, accounting={"oauth": {"authorize_url": "https://x/authorize"}})
    )
    with pytest.raises(ValueError):
        mf.build_authorize_url(cfg.get("accounting"))


def test_cli_mf_config_check_exit_codes(monkeypatch, capsys):
    from scripts import cli

    # 未設定 → --check は exit 1(どのプロダクトも ready でない)
    assert cli.main(["mf", "config", "--check"]) == 1

    # 経費の必須を env で満たす(token_url は実 config の既定値で充足)
    monkeypatch.setenv("MONEYFORWARD_EXPENSE_CLIENT_ID", "cid")
    monkeypatch.setenv("MONEYFORWARD_EXPENSE_CLIENT_SECRET", "topsecretvalue-abc123")
    assert cli.main(["mf", "config", "--check"]) == 0           # いずれか ready → 0
    assert cli.main(["mf", "config", "--product", "expense", "--check"]) == 0
    assert cli.main(["mf", "config", "--product", "accounting", "--check"]) == 1  # 会計は未設定
    out = capsys.readouterr().out
    assert "topsecretvalue-abc123" not in out  # 秘密の値は出力に漏れない
    assert "[accounting]" in out and "[expense]" in out  # 両方表示
