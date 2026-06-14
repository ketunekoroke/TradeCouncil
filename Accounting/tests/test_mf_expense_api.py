"""scripts/mf_expense_api.py: 明細取得(http_get 注入・無ネットワーク)。"""

import urllib.parse

from core.moneyforward import ProductConfig
from scripts import mf_expense_api as api


def _pc():
    return ProductConfig(
        product="expense", label="クラウド経費", enabled=True, client_id="c", client_secret="s",
        authorize_url=None, token_url="https://t/token", redirect_uri="urn:...:oob",
        scopes=["transaction:write"], api_base="https://expense.moneyforward.com/api",
        offices_url="https://expense.moneyforward.com/api/external/v1/offices",
    )


def _make_get(pages, offices=None):
    def _get(url, token):
        if "/me/ex_transactions" in url:
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            page = int(q["page"][0])
            return {"ex_transactions": pages.get(page, [])}
        return {"offices": offices if offices is not None else [{"id": "of1"}]}
    return _get


def test_get_office_id():
    oid = api.get_office_id(_pc(), access_token="tok", http_get=_make_get({}))
    assert oid == "of1"


def test_pagination_collects_until_short_page():
    pages = {
        1: [{"id": "a"}, {"id": "b"}],
        2: [{"id": "c"}],  # 端数 → 停止
    }
    txs = api.list_my_ex_transactions(
        _pc(), office_id="of1", access_token="tok", http_get=_make_get(pages), per_page=2
    )
    assert [t["id"] for t in txs] == ["a", "b", "c"]


def test_pagination_stops_on_duplicate_first_id():
    pages = {
        1: [{"id": "a"}, {"id": "b"}],  # full
        2: [{"id": "a"}, {"id": "c"}],  # 同じ先頭 id → ページング無効とみなし停止
    }
    txs = api.list_my_ex_transactions(
        _pc(), office_id="of1", access_token="tok", http_get=_make_get(pages), per_page=2
    )
    assert [t["id"] for t in txs] == ["a", "b"]


def test_date_filter_client_side():
    pages = {
        1: [
            {"id": "a", "recognized_at": "2024-08-01", "ex_item": {"name": "旅費交通費"}},
            {"id": "b", "recognized_at": "2025-09-01", "ex_item": {"name": "通信費"}},
        ],
    }
    txs = api.list_my_ex_transactions(
        _pc(), office_id="of1", access_token="tok", http_get=_make_get(pages),
        per_page=100, date_from="2024-07-01", date_to="2025-06-30",
    )
    assert [t["id"] for t in txs] == ["a"]  # b は前期外


def test_create_ex_transaction_posts_body():
    seen = {}

    def fake_post(url, token, body):
        seen.update(url=url, token=token, body=body)
        return {"ex_transaction": {"id": "EXT123"}}

    resp = api.create_ex_transaction(
        _pc(), "of1", {"ex_transaction": {"x": 1}}, access_token="tok", http_post=fake_post
    )
    assert resp["ex_transaction"]["id"] == "EXT123"
    assert seen["url"].endswith("/of1/me/ex_transactions")
    assert seen["token"] == "tok"
    assert seen["body"]["ex_transaction"]["x"] == 1


def test_update_ex_transaction_puts_body():
    seen = {}

    def fake_put(url, token, body):
        seen.update(url=url, body=body)
        return {"id": "EXT123"}

    resp = api.update_ex_transaction(
        _pc(), "of1", "EXT123", {"ex_transaction": {"remark": "r"}},
        access_token="tok", http_put=fake_put,
    )
    assert resp["id"] == "EXT123"
    assert seen["url"].endswith("/of1/me/ex_transactions/EXT123")
    assert seen["body"]["ex_transaction"]["remark"] == "r"


def test_auto_office_id_then_list():
    pages = {1: [{"id": "x", "ex_item": {"name": "通信費"}}]}
    txs = api.list_my_ex_transactions(
        _pc(), access_token="tok", http_get=_make_get(pages, offices=[{"id": "of9"}]), per_page=100
    )
    assert txs and txs[0]["id"] == "x"
