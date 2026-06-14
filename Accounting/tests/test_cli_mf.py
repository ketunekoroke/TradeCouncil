"""ac mf login/refresh/token の CLI 挙動(ネットワーク・socket bind なし)。"""

import os

import pytest

from core import config


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_root_env", lambda: {})
    monkeypatch.setattr(config, "_settings_local_env", lambda: {})
    for key in list(os.environ):
        if key.startswith("MONEYFORWARD"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MONEYFORWARD_TOKEN_DIR", str(tmp_path))
    yield


def test_mf_token_empty_store(capsys):
    from scripts import cli

    rc = cli.main(["mf", "token", "--product", "accounting"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "保存トークンなし" in out


def test_mf_login_expense_is_manual_no_bind(monkeypatch, capsys):
    """expense は HTTPS redirect → loopback リスナを使わず手動 URL を表示(socket bind しない)。"""
    from scripts import cli

    monkeypatch.setenv("MONEYFORWARD_EXPENSE_CLIENT_ID", "cid")
    monkeypatch.setenv("MONEYFORWARD_EXPENSE_CLIENT_SECRET", "topsecret-xyz")
    rc = cli.main(["mf", "login", "--product", "expense"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "https://expense.moneyforward.com/oauth/authorize" in out
    assert "topsecret-xyz" not in out  # 秘密は出力に漏れない


def test_mf_login_accounting_no_listen_is_manual(monkeypatch, capsys):
    """--no-listen 指定時はリスナを使わず手動フロー(bind しない)。"""
    from scripts import cli

    monkeypatch.setenv("MONEYFORWARD_ACCOUNTING_CLIENT_ID", "cid")
    monkeypatch.setenv("MONEYFORWARD_ACCOUNTING_CLIENT_SECRET", "sec")
    rc = cli.main(["mf", "login", "--product", "accounting", "--no-listen"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "https://api.biz.moneyforward.com/authorize" in out
    assert "AUTH_CODE" in out  # 手動 code 設定の案内


def test_mf_refresh_no_store_relogin(capsys):
    from scripts import cli

    rc = cli.main(["mf", "refresh", "--product", "accounting"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "login" in err  # 再ログイン案内
