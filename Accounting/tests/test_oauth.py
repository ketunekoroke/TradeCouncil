"""core/oauth.py の純粋ロジック(ネットワーク・実 creds なし)。

token/refresh リクエスト組立・token 応答解析・コールバック解析・TokenBundle・get_access_token を、
clock(now)と post_form を注入して密閉テストする。実 API 疎通は手動 spike(TC-AC08)で確認。
"""

import json
import os

import pytest

from core import config, oauth
from core import moneyforward as mf


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """実 .env / settings.local に依存させない。os.environ の MONEYFORWARD_* も毎回クリア。"""
    monkeypatch.setattr(config, "_root_env", lambda: {})
    monkeypatch.setattr(config, "_settings_local_env", lambda: {})
    for key in list(os.environ):
        if key.startswith("MONEYFORWARD"):
            monkeypatch.delenv(key, raising=False)
    yield


def _pc(**overrides) -> mf.ProductConfig:
    base = dict(
        product="expense",
        label="クラウド経費",
        enabled=True,
        client_id="cid-123",
        client_secret="sec-xyz",
        authorize_url="https://e.test/authorize",
        token_url="https://e.test/oauth/token",
        redirect_uri="https://e.test/cb",
        scopes=["transaction:write", "public_resource:read"],
        api_base="https://e.test/api",
        client_auth="client_secret_basic",
    )
    base.update(overrides)
    return mf.ProductConfig(**base)


# --- build_token_request(純粋・明示 code)-----------------------------------------------

def test_build_token_request_authcode_basic():
    url, data, headers = oauth.build_token_request(
        _pc(), auth_code="the-code", redirect_uri="https://e.test/cb"
    )
    assert url == "https://e.test/oauth/token"
    assert data["grant_type"] == "authorization_code"
    assert data["code"] == "the-code"
    assert data["redirect_uri"] == "https://e.test/cb"
    assert data["scope"] == "transaction:write public_resource:read"
    assert headers["Authorization"].startswith("Basic ")
    assert "client_secret" not in data and "client_id" not in data


def test_build_token_request_post_auth():
    _url, data, headers = oauth.build_token_request(
        _pc(client_auth="client_secret_post"), auth_code="c"
    )
    assert data["client_id"] == "cid-123" and data["client_secret"] == "sec-xyz"
    assert "Authorization" not in headers


def test_build_token_request_missing_code_raises():
    with pytest.raises(ValueError):
        oauth.build_token_request(_pc(), auth_code=None)


# --- build_refresh_request ----------------------------------------------------------------

def test_build_refresh_request_basic():
    _url, data, headers = oauth.build_refresh_request(_pc(), "rt-123")
    assert data["grant_type"] == "refresh_token"
    assert data["refresh_token"] == "rt-123"
    assert data["scope"] == "transaction:write public_resource:read"
    assert "code" not in data and "redirect_uri" not in data
    assert headers["Authorization"].startswith("Basic ")


def test_build_refresh_request_post_auth():
    _url, data, headers = oauth.build_refresh_request(_pc(client_auth="client_secret_post"), "rt")
    assert data["client_id"] == "cid-123" and data["client_secret"] == "sec-xyz"
    assert "Authorization" not in headers


def test_build_refresh_request_requires_token():
    with pytest.raises(ValueError):
        oauth.build_refresh_request(_pc(), "")


# --- parse_token_response -----------------------------------------------------------------

def test_parse_token_response_full():
    b = oauth.parse_token_response(
        {"access_token": "at", "refresh_token": "rt", "token_type": "Bearer",
         "scope": "a b", "expires_in": 3600},
        now=1000.0,
    )
    assert b.access_token == "at" and b.refresh_token == "rt"
    assert b.token_type == "Bearer" and b.scope == "a b"
    assert b.expires_at == 1000.0 + 3600 and b.obtained_at == 1000.0


def test_parse_token_response_str_expires_in():
    b = oauth.parse_token_response({"access_token": "at", "expires_in": "900"}, now=0.0)
    assert b.expires_at == 900.0


def test_parse_token_response_bad_expires_in():
    b = oauth.parse_token_response({"access_token": "at", "expires_in": "oops"}, now=0.0)
    assert b.expires_at is None


def test_parse_token_response_no_refresh_no_expiry():
    b = oauth.parse_token_response({"access_token": "at"}, now=0.0)
    assert b.refresh_token is None and b.expires_at is None
    assert b.is_expired(now=10**12) is False  # 期限不明 → 失効扱いしない


def test_parse_token_response_missing_access_raises():
    with pytest.raises(ValueError):
        oauth.parse_token_response({"token_type": "Bearer"})


# --- TokenBundle --------------------------------------------------------------------------

def test_token_bundle_is_expired_with_skew():
    b = oauth.TokenBundle(access_token="at", expires_at=1000.0)  # skew=60
    assert b.is_expired(now=900.0) is False
    assert b.is_expired(now=939.0) is False
    assert b.is_expired(now=941.0) is True  # 941 >= 1000-60
    assert b.is_expired(now=1000.0) is True


def test_token_bundle_masked_no_leak():
    # 値は「漏れたら検知できる」短いカナリア(秘密スキャナの token="..." パターンを避ける)。
    b = oauth.TokenBundle(
        access_token="leak-canary-A", refresh_token="leak-canary-R",
        token_type="Bearer", scope="a b", expires_at=None,
    )
    m = b.masked()
    blob = json.dumps(m, ensure_ascii=False, default=str)
    assert "leak-canary-A" not in blob and "leak-canary-R" not in blob
    assert m["access_token"].startswith("set(")
    assert m["refresh_token"].startswith("set(")


def test_token_bundle_roundtrip_dict():
    b = oauth.TokenBundle(access_token="at", refresh_token="rt", expires_at=12.0, obtained_at=1.0)
    assert oauth.TokenBundle.from_dict(b.to_dict()).to_dict() == b.to_dict()


# --- parse_callback -----------------------------------------------------------------------

def test_parse_callback_valid():
    r = oauth.parse_callback("/callback?code=abc&state=xyz")
    assert r.code == "abc" and r.state == "xyz" and r.error is None


def test_parse_callback_error():
    r = oauth.parse_callback("/callback?error=access_denied&error_description=nope")
    assert r.error == "access_denied" and r.error_description == "nope" and r.code is None


def test_parse_callback_missing():
    r = oauth.parse_callback("/callback")
    assert r.code is None and r.state is None and r.error is None


# --- exchange_code（poster 注入）----------------------------------------------------------

def test_exchange_code_injected_poster():
    seen = {}

    def fake_post(url, data, headers):
        seen["url"], seen["data"] = url, data
        return {"access_token": "at", "refresh_token": "rt", "expires_in": 3600}

    b = oauth.exchange_code(_pc(), "the-code", post_form=fake_post)
    assert b.access_token == "at" and b.refresh_token == "rt"
    assert seen["data"]["code"] == "the-code"
    assert seen["data"]["grant_type"] == "authorization_code"
    assert seen["url"] == "https://e.test/oauth/token"


# --- get_access_token（clock + poster + token_store 注入）---------------------------------

def test_get_access_token_valid_no_refresh(monkeypatch, tmp_path):
    monkeypatch.setenv("MONEYFORWARD_TOKEN_DIR", str(tmp_path))
    from core import token_store

    token_store.save("accounting", oauth.TokenBundle(
        access_token="at", refresh_token="rt", expires_at=10_000.0))

    def boom(*_a, **_k):
        raise AssertionError("有効なトークンで refresh してはならない")

    assert oauth.get_access_token(_pc(product="accounting"), post_form=boom, now=0.0) == "at"


def test_get_access_token_refreshes_and_carries_refresh(monkeypatch, tmp_path):
    monkeypatch.setenv("MONEYFORWARD_TOKEN_DIR", str(tmp_path))
    from core import token_store

    token_store.save("accounting", oauth.TokenBundle(
        access_token="old", refresh_token="rt-1", expires_at=100.0))

    def fake_post(url, data, headers):
        assert data["grant_type"] == "refresh_token" and data["refresh_token"] == "rt-1"
        return {"access_token": "new", "expires_in": 3600}  # 応答に refresh_token なし

    tok = oauth.get_access_token(_pc(product="accounting"), post_form=fake_post, now=1000.0)
    assert tok == "new"
    saved = token_store.load("accounting")
    assert saved.access_token == "new" and saved.refresh_token == "rt-1"  # 旧 refresh を引き継ぐ


def test_get_access_token_empty_store_relogin(monkeypatch, tmp_path):
    monkeypatch.setenv("MONEYFORWARD_TOKEN_DIR", str(tmp_path))
    with pytest.raises(oauth.ReloginRequired):
        oauth.get_access_token(_pc(product="accounting"), now=0.0)


def test_get_access_token_expired_no_refresh_relogin(monkeypatch, tmp_path):
    monkeypatch.setenv("MONEYFORWARD_TOKEN_DIR", str(tmp_path))
    from core import token_store

    token_store.save("accounting", oauth.TokenBundle(
        access_token="at", refresh_token=None, expires_at=100.0))
    with pytest.raises(oauth.ReloginRequired):
        oauth.get_access_token(_pc(product="accounting"), now=1000.0)


# --- spike の後方互換ラッパ ---------------------------------------------------------------

def test_spike_build_token_request_delegates(monkeypatch):
    from scripts import spike_moneyforward as spike

    monkeypatch.setenv("MONEYFORWARD_EXPENSE_AUTH_CODE", "code-1")
    _url, data, _headers = spike.build_token_request(_pc())
    assert data["code"] == "code-1" and data["grant_type"] == "authorization_code"


def test_spike_build_token_request_missing_code_systemexit():
    from scripts import spike_moneyforward as spike

    with pytest.raises(SystemExit):
        spike.build_token_request(_pc())  # AUTH_CODE 未設定
