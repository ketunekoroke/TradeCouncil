"""core/token_store.py のトークン永続化(tmp ディレクトリ・MONEYFORWARD_TOKEN_DIR で隔離)。"""

import os

import pytest

from core import config, oauth, token_store


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    """実 .env / settings.local を遮断し、保存先を tmp_path に固定する。"""
    monkeypatch.setattr(config, "_root_env", lambda: {})
    monkeypatch.setattr(config, "_settings_local_env", lambda: {})
    for key in list(os.environ):
        if key.startswith("MONEYFORWARD"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MONEYFORWARD_TOKEN_DIR", str(tmp_path))
    yield


def test_save_load_roundtrip():
    b = oauth.TokenBundle(
        access_token="at", refresh_token="rt", token_type="Bearer",
        scope="a b", expires_at=123.0, obtained_at=1.0,
    )
    path = token_store.save("accounting", b)
    assert path.is_file()
    loaded = token_store.load("accounting")
    assert loaded.access_token == "at" and loaded.refresh_token == "rt"
    assert loaded.expires_at == 123.0 and loaded.scope == "a b"


def test_products_isolated():
    token_store.save("accounting", oauth.TokenBundle(access_token="acc"))
    token_store.save("expense", oauth.TokenBundle(access_token="exp"))
    assert token_store.load("accounting").access_token == "acc"
    assert token_store.load("expense").access_token == "exp"


def test_load_missing_returns_none():
    assert token_store.load("accounting") is None


def test_load_corrupt_returns_none():
    token_store.token_dir().mkdir(parents=True, exist_ok=True)
    token_store.token_path("accounting").write_text("{ not json", encoding="utf-8")
    assert token_store.load("accounting") is None


def test_clear():
    token_store.save("accounting", oauth.TokenBundle(access_token="at"))
    assert token_store.clear("accounting") is True
    assert token_store.load("accounting") is None
    assert token_store.clear("accounting") is False  # 既に無い


def test_token_dir_relative_to_project(monkeypatch):
    monkeypatch.setenv("MONEYFORWARD_TOKEN_DIR", "var/custom")
    assert token_store.token_dir() == config.PROJECT_ROOT / "var/custom"
