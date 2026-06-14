"""ac mf login/refresh/token の CLI 挙動(ネットワーク・socket bind・ブラウザなし)。

経費は OOB(urn:ietf:wg:oauth:2.0:oob)+ 対話ペースト式。交換は oauth._default_post_form を、
対話は builtins.input を、ブラウザ起動は webbrowser.open を monkeypatch で無効化して検証する。
"""

import os
import urllib.error

import pytest

from core import config, oauth, token_store


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_root_env", lambda: {})
    monkeypatch.setattr(config, "_settings_local_env", lambda: {})
    for key in list(os.environ):
        if key.startswith("MONEYFORWARD"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MONEYFORWARD_TOKEN_DIR", str(tmp_path))
    monkeypatch.setattr("webbrowser.open", lambda *a, **k: True)  # テストでブラウザを開かない
    yield


def _expense_creds(monkeypatch):
    monkeypatch.setenv("MONEYFORWARD_EXPENSE_CLIENT_ID", "cid")
    monkeypatch.setenv("MONEYFORWARD_EXPENSE_CLIENT_SECRET", "topsecret-xyz")


def test_mf_token_empty_store(capsys):
    from scripts import cli

    rc = cli.main(["mf", "token", "--product", "accounting"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "保存トークンなし" in out


def test_mf_login_expense_code_exchanges_and_saves(monkeypatch, capsys):
    """経費 OOB: --code で交換 → 保存。token リクエストに redirect_uri=urn:…oob が載る。秘密は出ない。"""
    from scripts import cli

    _expense_creds(monkeypatch)
    seen = {}

    def fake_post(url, data, headers):
        seen["data"] = data
        return {"access_token": "exp-access-tok", "refresh_token": "exp-ref-tok", "expires_in": 3600}

    monkeypatch.setattr(oauth, "_default_post_form", fake_post)
    rc = cli.main(["mf", "login", "--product", "expense", "--code", "OOBCODE123"])
    out = capsys.readouterr().out
    assert rc == 0
    assert seen["data"]["code"] == "OOBCODE123"
    assert seen["data"]["redirect_uri"] == "urn:ietf:wg:oauth:2.0:oob"
    assert "ログイン完了" in out
    assert "exp-access-tok" not in out and "exp-ref-tok" not in out  # 秘密はマスク
    assert token_store.load("expense").access_token == "exp-access-tok"


def test_mf_login_expense_interactive_paste(monkeypatch):
    """対話入力で code を貼り付け(前後空白は strip)→ 交換・保存。"""
    from scripts import cli

    _expense_creds(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "  PASTED-CODE  ")
    monkeypatch.setattr(oauth, "_default_post_form",
                        lambda u, d, h: {"access_token": "at", "refresh_token": "rt"})
    rc = cli.main(["mf", "login", "--product", "expense"])
    assert rc == 0
    assert token_store.load("expense").access_token == "at"


def test_mf_login_expense_empty_input_falls_back(monkeypatch, capsys):
    """code 未入力(EOF)→ 従来手順を案内・交換しない・exit 0。"""
    from scripts import cli

    _expense_creds(monkeypatch)

    def boom(*_a, **_k):
        raise EOFError

    monkeypatch.setattr("builtins.input", boom)
    rc = cli.main(["mf", "login", "--product", "expense"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "AUTH_CODE" in out  # 従来手順の案内
    assert token_store.load("expense") is None  # 交換していない


def test_mf_login_code_exchange_network_error(monkeypatch, capsys):
    """交換時のネットワークエラー → エラー表示・exit 1。"""
    from scripts import cli

    _expense_creds(monkeypatch)

    def boom(*_a, **_k):
        raise urllib.error.URLError("no network")

    monkeypatch.setattr(oauth, "_default_post_form", boom)
    rc = cli.main(["mf", "login", "--product", "expense", "--code", "X"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "失敗" in err


def test_mf_login_accounting_no_listen_paste(monkeypatch, capsys):
    """会計 --no-listen も対話ペースト式(socket bind しない)。"""
    from scripts import cli

    monkeypatch.setenv("MONEYFORWARD_ACCOUNTING_CLIENT_ID", "cid")
    monkeypatch.setenv("MONEYFORWARD_ACCOUNTING_CLIENT_SECRET", "sec")
    monkeypatch.setattr(oauth, "_default_post_form", lambda u, d, h: {"access_token": "acc-at"})
    rc = cli.main(["mf", "login", "--product", "accounting", "--no-listen", "--code", "C"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "https://api.biz.moneyforward.com/authorize" in out
    assert token_store.load("accounting").access_token == "acc-at"


def test_mf_refresh_no_store_relogin(capsys):
    from scripts import cli

    rc = cli.main(["mf", "refresh", "--product", "accounting"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "login" in err  # 再ログイン案内
