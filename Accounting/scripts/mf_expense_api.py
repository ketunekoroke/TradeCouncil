"""クラウド経費 REST: 自分の経費明細(me/ex_transactions)の取得(scripts 層・urllib 可)。

前期実績から費目・税区分の使用実績(core/refdata)を学習するためのデータ取得。公式 Swagger:
  GET /api/external/v1/offices/{office_id}/me/ex_transactions  (scope: transaction:write)

`transaction:write` は「明細の読み書き」権限なので、再認可なしに自分の前期明細を読める。
全費目/税区分マスタ(ex_items / excises)は office_setting:write が要るため取得しない
(使用実績は明細から学習)。

ネットワークは注入可能(`http_get`)。office_id は offices 一覧の先頭(CloudBloom は件数=1)。
ページング・日付フィルタは応答形が揺れるため寛容に扱い、日付は **クライアント側で絞る**。
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Accounting/ を import パスへ

from core import moneyforward as mf  # noqa: E402
from core import oauth  # noqa: E402

_TIMEOUT = 30
_TIMEOUT_BIN = 60  # 証憑バイナリ DL は大きめ

# 応答配列の候補キー(素のリスト / {"ex_transactions":[...]} / {"data":[...]} を吸収)。
_LIST_KEYS = ("ex_transactions", "data", "items", "results", "offices")
# 明細の取引日の候補キー(クライアント側フィルタ用)。
_DATE_KEYS = ("recognized_at", "date", "used_at", "occurred_at", "transacted_at")


def _default_http_get(url: str, token: str) -> object:
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _send_json(url: str, token: str, body: dict, method: str) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def _default_http_post(url: str, token: str, body: dict) -> dict:
    return _send_json(url, token, body, "POST")


def _default_http_put(url: str, token: str, body: dict) -> dict:
    return _send_json(url, token, body, "PUT")


def _default_http_get_bytes(url: str, token: str) -> tuple[bytes, str]:
    """バイナリ GET。`(本文 bytes, Content-Type)` を返す(JSON parse しない)。404 はそのまま送出。"""
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT_BIN) as resp:  # noqa: S310
        ctype = resp.headers.get("Content-Type", "application/octet-stream").split(";")[0].strip()
        return resp.read(), ctype


def _as_list(payload: object) -> list[dict]:
    """応答からレコード配列を取り出す(形状差を吸収)。判別できなければ []。"""
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in _LIST_KEYS:
            v = payload.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
        lists = [v for v in payload.values() if isinstance(v, list)]
        if len(lists) == 1:
            return [x for x in lists[0] if isinstance(x, dict)]
    return []


def _tx_date(tx: dict) -> str | None:
    for k in _DATE_KEYS:
        v = tx.get(k)
        if v:
            return str(v)[:10]  # ISO 日付部分
    return None


def _ex_tx_url(pc: mf.ProductConfig, office_id: str) -> str:
    """me/ex_transactions のベース URL を組み立てる。"""
    base = (pc.offices_url or "").rstrip("/")
    if not base:
        api = (pc.api_base or "").rstrip("/")
        base = f"{api}/external/v1/offices" if api else ""
    if not base:
        raise SystemExit(
            "error: 経費 API のベース URL が不明です(config の api.offices_url / api.base を確認)"
        )
    return f"{base}/{office_id}/me/ex_transactions"


def get_office_id(
    pc: mf.ProductConfig, *, access_token: str, http_get=_default_http_get
) -> str | None:
    """offices 一覧の先頭の office_id を返す(CloudBloom は件数=1)。"""
    if not pc.offices_url:
        return None
    offices = _as_list(http_get(pc.offices_url, access_token))
    if not offices:
        return None
    first = offices[0]
    return str(first.get("id") or first.get("office_id") or "") or None


def list_my_ex_transactions(
    pc: mf.ProductConfig,
    office_id: str | None = None,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    access_token: str | None = None,
    http_get=None,
    per_page: int = 100,
    max_pages: int = 200,
) -> list[dict]:
    """自分の経費明細を全ページ取得して返す(`date_from`/`date_to` はクライアント側で絞る)。

    MF は per_page を上限する(実測50件/ページ)。要求 per_page と実サイズが異なるため、
    **実ページサイズを観測** して最終ページを判定する(`len(batch)<per_page` 停止は
    初回50件で打ち切る不具合)。明細は取引日の降順なので `date_from` 未満のページで打ち切る。
    空 / 先頭 id 重複でも停止。id 重複は除外する。
    """
    http_get = http_get or _default_http_get
    if access_token is None:
        access_token = oauth.get_access_token(pc)
    if office_id is None:
        office_id = get_office_id(pc, access_token=access_token, http_get=http_get)
        if not office_id:
            raise SystemExit("error: office_id を取得できませんでした(offices 応答を確認)")

    base = _ex_tx_url(pc, office_id)
    out: list[dict] = []
    seen_ids: set[str] = set()
    seen_first: str | None = None
    page_size: int | None = None
    for page in range(1, max_pages + 1):
        url = base + "?" + urllib.parse.urlencode({"page": page, "per_page": per_page})
        batch = _as_list(http_get(url, access_token))
        if not batch:
            break
        first_id = str(batch[0].get("id") or "")
        if first_id and first_id == seen_first:  # ページングが効かず同じページが返る
            break
        seen_first = first_id
        for tx in batch:  # 境界の重複を避けつつ追加
            tid = str(tx.get("id") or "")
            if tid and tid in seen_ids:
                continue
            seen_ids.add(tid)
            out.append(tx)
        if page_size is None:  # サーバの実ページサイズを観測(per_page を無視/上限する場合に対応)
            page_size = len(batch)
        elif len(batch) < page_size:  # 観測サイズより短い = 最終ページ
            break
        if date_from:  # 降順ソート前提: 最古日付が date_from 未満なら以降は範囲外
            dates = [d for d in (_tx_date(tx) for tx in batch) if d]
            if dates and min(dates) < date_from:
                break

    if date_from or date_to:
        out = [tx for tx in out if _within(_tx_date(tx), date_from, date_to)]
    return out


def _within(date: str | None, lo: str | None, hi: str | None) -> bool:
    if date is None:
        return False
    if lo and date < lo:
        return False
    if hi and date > hi:
        return False
    return True


def create_ex_transaction(
    pc: mf.ProductConfig,
    office_id: str,
    body: dict,
    *,
    access_token: str | None = None,
    http_post=None,
) -> dict:
    """`POST me/ex_transactions` で経費明細を登録(receipt_input があれば証憑添付=電帳法)。

    **本番書き込み**。呼び出し側で明示確認・ゲート合格を必ず経ること。応答(作成された明細)を返す。
    """
    http_post = http_post or _default_http_post
    if access_token is None:
        access_token = oauth.get_access_token(pc)
    return http_post(_ex_tx_url(pc, office_id), access_token, body)


def update_ex_transaction(
    pc: mf.ProductConfig,
    office_id: str,
    tx_id: str,
    body: dict,
    *,
    access_token: str | None = None,
    http_put=None,
) -> dict:
    """`PUT me/ex_transactions/{id}` で明細を部分更新(remark/memo 等)。**本番書き込み**。"""
    http_put = http_put or _default_http_put
    if access_token is None:
        access_token = oauth.get_access_token(pc)
    return http_put(f"{_ex_tx_url(pc, office_id)}/{tx_id}", access_token, body)


def download_ex_transaction_receipt(
    pc: mf.ProductConfig,
    office_id: str,
    tx_id: str,
    *,
    access_token: str | None = None,
    http_get_bytes=None,
) -> tuple[bytes, str]:
    """添付証憑のバイナリを取得(`GET .../{id}/mf_file`)し `(bytes, content_type)` を返す。

    証憑が無い明細は API が 404 を返す。呼び出し側で `HTTPError`(404)を「証憑なし」扱いにする。
    """
    http_get_bytes = http_get_bytes or _default_http_get_bytes
    if access_token is None:
        access_token = oauth.get_access_token(pc)
    url = f"{_ex_tx_url(pc, office_id)}/{tx_id}/mf_file"
    return http_get_bytes(url, access_token)
