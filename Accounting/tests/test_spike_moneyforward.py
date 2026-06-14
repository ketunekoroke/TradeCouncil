"""MoneyForward 疎通スパイクの純粋ロジック(ネットワークなし)。

token リクエスト組立(認可コード grant・client 認証方式)・offices URL 解決・offices 件数抽出を、
実 credentials / 実通信なしで検証する。実 API への疎通は手動の spike 実行(TC-AC08)で確認する。
"""

import os

import pytest

from core import config
from core import moneyforward as mf
from scripts import spike_moneyforward as spike


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
    """テスト用の最小 ProductConfig。overrides で各フィールドを差し替える。"""
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


# --- build_token_request: 認可コードフロー -------------------------------------------------

def test_token_request_authorization_code_basic(monkeypatch):
    import base64

    monkeypatch.setenv("MONEYFORWARD_EXPENSE_AUTH_CODE", "the-code")
    url, data, headers = spike.build_token_request(_pc())

    assert url == "https://e.test/oauth/token"
    assert data["grant_type"] == "authorization_code"
    assert data["code"] == "the-code"
    assert data["redirect_uri"] == "https://e.test/cb"
    assert data["scope"] == "transaction:write public_resource:read"
    # client_secret_basic: 資格情報は Authorization ヘッダ、body には出さない。
    expected = base64.b64encode(b"cid-123:sec-xyz").decode()
    assert headers["Authorization"] == f"Basic {expected}"
    assert "client_secret" not in data and "client_id" not in data


def test_token_request_client_secret_post(monkeypatch):
    monkeypatch.setenv("MONEYFORWARD_EXPENSE_AUTH_CODE", "the-code")
    url, data, headers = spike.build_token_request(_pc(client_auth="client_secret_post"))

    # client_secret_post: 資格情報は body、Authorization ヘッダは付けない。
    assert data["client_id"] == "cid-123"
    assert data["client_secret"] == "sec-xyz"
    assert "Authorization" not in headers


def test_token_request_missing_auth_code_raises(monkeypatch):
    # AUTH_CODE 未設定(認可コードフロー)は SystemExit。
    with pytest.raises(SystemExit):
        spike.build_token_request(_pc())


def test_token_request_non_authcode_grant_skips_code(monkeypatch):
    # grant_type を上書きすると code / redirect_uri は要求されない。
    monkeypatch.setenv("MONEYFORWARD_EXPENSE_GRANT_TYPE", "client_credentials")
    _url, data, _headers = spike.build_token_request(_pc())
    assert data["grant_type"] == "client_credentials"
    assert "code" not in data and "redirect_uri" not in data


def test_token_request_no_scopes_omits_scope(monkeypatch):
    monkeypatch.setenv("MONEYFORWARD_EXPENSE_AUTH_CODE", "c")
    _url, data, _headers = spike.build_token_request(_pc(scopes=[]))
    assert "scope" not in data


# --- _offices_url: env 上書き → config の offices_url → api_base+/offices → None -----------

def test_offices_url_from_api_base():
    assert spike._offices_url(_pc()) == "https://e.test/api/offices"


def test_offices_url_config_field_beats_api_base():
    # /offices 形でないパス(例: 会計の /v2/tenant)は config の offices_url で明示する。
    pc = _pc(offices_url="https://api.biz.moneyforward.com/v2/tenant")
    assert spike._offices_url(pc) == "https://api.biz.moneyforward.com/v2/tenant"


def test_offices_url_env_override(monkeypatch):
    monkeypatch.setenv("MONEYFORWARD_EXPENSE_OFFICES_URL", "https://e.test/custom/offices")
    # env は config の offices_url よりも優先される。
    assert spike._offices_url(_pc(offices_url="https://e.test/config/tenant")) == \
        "https://e.test/custom/offices"


def test_offices_url_none_without_base():
    assert spike._offices_url(_pc(api_base=None)) is None


# --- count_offices: 応答形状の差を吸収して件数のみを返す -----------------------------------

@pytest.mark.parametrize(
    "payload,expected",
    [
        ([{"id": 1}, {"id": 2}], 2),                              # 素のリスト
        ({"data": [{"id": 1}]}, 1),                               # data 包み
        ({"offices": [{"id": 1}, {"id": 2}, {"id": 3}]}, 3),      # offices 包み
        ({"items": []}, 0),                                       # 空(0 件は ready 扱い)
        ({"data": {"offices": [{"id": 1}]}}, 1),                  # 二段包み
        ({"results": [1, 2]}, 2),                                 # results 包み
        ({"foo": [1, 2, 3]}, 3),                  # 想定外キーでもリストが1つなら採用
    ],
)
def test_count_offices_shapes(payload, expected):
    assert spike.count_offices(payload) == expected


@pytest.mark.parametrize(
    "payload",
    [
        {"message": "ok"},               # リストが無い
        {"a": [1], "b": [2]},            # リストが複数(曖昧)→ 判別しない
        "unexpected-string",             # dict/list 以外
        42,
    ],
)
def test_count_offices_unknown_returns_none(payload):
    assert spike.count_offices(payload) is None
