"""MoneyForward OAuth の共通ロジック(zero-dep・純粋寄り)。会計 / 経費 共通。

`core/moneyforward.py` が解決した `ProductConfig` を使い、認可コードフローの

  - token 交換リクエスト組立(`build_token_request`)
  - リフレッシュリクエスト組立(`build_refresh_request`)
  - token 応答の解釈(`parse_token_response` → `TokenBundle`)
  - リダイレクトのコールバック解析(`parse_callback`)
  - 保存トークンの取得・失効時の自動更新(`get_access_token`)

を提供する。**標準ライブラリのみ**(urllib/base64/json/time/dataclass)に依存し、`scripts/` は import
しない(ADR-0011: `core/` は stdlib + 自前モジュールのみ)。socket/ブラウザ等の副作用は `scripts/` 側。

秘匿情報(access/refresh token・client_secret)は値を出力しない。表示は `TokenBundle.masked()`。
"""

from __future__ import annotations

import base64
import datetime
import json
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from core.moneyforward import ProductConfig, _mask_secret

_TIMEOUT = 30


class ReloginRequired(RuntimeError):
    """保存トークンが無い / 失効していて refresh もできない。ブラウザ再認可が必要。"""


# --- token リクエスト組立(ネットワークなし・純粋)----------------------------------------

def _apply_client_auth(pc: ProductConfig, data: dict[str, str], headers: dict[str, str]) -> None:
    """client 認証方式に応じて資格情報を data/headers へ載せる。

    - client_secret_basic: Authorization: Basic base64(client_id:client_secret)(MoneyForward 既定)
    - client_secret_post:  body に client_id / client_secret
    """
    if pc.client_auth == "client_secret_post":
        data["client_id"] = pc.client_id or ""
        data["client_secret"] = pc.client_secret or ""
    else:  # client_secret_basic(既定)
        cred = base64.b64encode(f"{pc.client_id or ''}:{pc.client_secret or ''}".encode()).decode()
        headers["Authorization"] = f"Basic {cred}"


def build_token_request(
    pc: ProductConfig,
    *,
    auth_code: str | None = None,
    redirect_uri: str | None = None,
    grant_type: str = "authorization_code",
) -> tuple[str, dict[str, str], dict[str, str]]:
    """token エンドポイントへ送る (url, form, headers) を組み立てる(純粋)。

    認可コードフローでは `auth_code` 必須・`redirect_uri` はアプリ登録値と完全一致が前提。
    env からの読み出しは呼び出し側の責務(spike のラッパや CLI が行う)。
    """
    data: dict[str, str] = {"grant_type": grant_type}
    headers: dict[str, str] = {}
    _apply_client_auth(pc, data, headers)
    if pc.scopes:
        data["scope"] = " ".join(pc.scopes)
    if grant_type == "authorization_code":
        if not auth_code:
            raise ValueError("authorization_code grant には code が必要です")
        data["code"] = auth_code
        if redirect_uri:
            data["redirect_uri"] = redirect_uri
    return pc.token_url or "", data, headers


def build_refresh_request(
    pc: ProductConfig, refresh_token: str
) -> tuple[str, dict[str, str], dict[str, str]]:
    """refresh_token から access token を更新する (url, form, headers) を組み立てる(純粋)。"""
    if not refresh_token:
        raise ValueError("refresh_token が必要です")
    data: dict[str, str] = {"grant_type": "refresh_token", "refresh_token": refresh_token}
    headers: dict[str, str] = {}
    _apply_client_auth(pc, data, headers)
    if pc.scopes:
        data["scope"] = " ".join(pc.scopes)
    return pc.token_url or "", data, headers


# --- token 応答の解釈 ---------------------------------------------------------------------

@dataclass
class TokenBundle:
    """token エンドポイントの応答。秘匿のため表示は `masked()` のみ。"""

    access_token: str
    refresh_token: str | None = None
    token_type: str | None = None
    scope: str | None = None
    expires_at: float | None = None  # epoch 秒(expires_in から算出)
    obtained_at: float | None = None

    def is_expired(self, now: float | None = None, skew: int = 60) -> bool:
        """期限切れか。`expires_at` 不明なら False(使ってみて 401 なら呼び出し側で再ログイン)。"""
        if self.expires_at is None:
            return False
        now = time.time() if now is None else now
        return now >= (self.expires_at - skew)

    def to_dict(self) -> dict[str, object]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "scope": self.scope,
            "expires_at": self.expires_at,
            "obtained_at": self.obtained_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> TokenBundle:
        if not d.get("access_token"):
            raise ValueError("access_token がありません")
        return cls(
            access_token=str(d["access_token"]),
            refresh_token=d.get("refresh_token") or None,
            token_type=d.get("token_type") or None,
            scope=d.get("scope") or None,
            expires_at=d.get("expires_at"),
            obtained_at=d.get("obtained_at"),
        )

    def masked(self) -> dict[str, object]:
        return {
            "access_token": _mask_secret(self.access_token),
            "refresh_token": _mask_secret(self.refresh_token),
            "token_type": self.token_type or "(未設定)",
            "scope": self.scope or "(未設定)",
            "expires_at": _fmt_ts(self.expires_at),
            "expired": self.is_expired(),
        }


def _fmt_ts(ts: float | None) -> str:
    if ts is None:
        return "(不明)"
    try:
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except (OverflowError, OSError, ValueError):
        return str(ts)


def parse_token_response(payload: dict, *, now: float | None = None) -> TokenBundle:
    """token 応答(JSON)を `TokenBundle` にする。access_token 欠落は ValueError。

    `expires_in`(秒)があれば `expires_at = now + expires_in` を算出する(文字列も許容)。
    """
    access = payload.get("access_token")
    if not access:
        raise ValueError(f"access_token が応答にありません(キー: {list(payload)})")
    now = time.time() if now is None else now
    expires_at: float | None = None
    exp = payload.get("expires_in")
    if exp is not None:
        try:
            expires_at = now + float(exp)
        except (TypeError, ValueError):
            expires_at = None
    return TokenBundle(
        access_token=str(access),
        refresh_token=payload.get("refresh_token") or None,
        token_type=payload.get("token_type") or None,
        scope=payload.get("scope") or None,
        expires_at=expires_at,
        obtained_at=now,
    )


# --- リダイレクトのコールバック解析(リスナの純粋核)--------------------------------------

@dataclass
class CallbackResult:
    """リダイレクト URL のクエリから取り出した値。"""

    code: str | None = None
    state: str | None = None
    error: str | None = None
    error_description: str | None = None


def parse_callback(path: str) -> CallbackResult:
    """`/callback?code=..&state=..`(または `?error=..`)から値を取り出す。純粋。"""
    query = urllib.parse.urlsplit(path).query
    params = urllib.parse.parse_qs(query)

    def first(key: str) -> str | None:
        values = params.get(key)
        return values[0] if values else None

    return CallbackResult(
        code=first("code"),
        state=first("state"),
        error=first("error"),
        error_description=first("error_description"),
    )


# --- 実通信(注入可能。既定は zero-dep の urllib POST)-------------------------------------

PostForm = Callable[[str, dict, "dict | None"], dict]


def _default_post_form(url: str, data: dict[str, str], headers: dict[str, str] | None = None) -> dict:
    body = urllib.parse.urlencode(data).encode("utf-8")
    hdrs = {"Content-Type": "application/x-www-form-urlencoded"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    # 信頼できる設定由来の token_url のみ(config/env)。
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def exchange_code(
    pc: ProductConfig,
    code: str,
    *,
    redirect_uri: str | None = None,
    post_form: PostForm | None = None,
) -> TokenBundle:
    """認可コードを token に交換して `TokenBundle` を返す(保存はしない・呼び出し側で save)。"""
    poster = post_form or _default_post_form
    url, data, headers = build_token_request(
        pc, auth_code=code, redirect_uri=redirect_uri or pc.redirect_uri
    )
    payload = poster(url, data, headers)
    return parse_token_response(payload)


def get_access_token(
    pc: ProductConfig, *, post_form: PostForm | None = None, now: float | None = None
) -> str:
    """保存トークンの有効な access_token を返す。失効時は refresh_token で更新して保存する。

    保存が無い / refresh もできない場合は `ReloginRequired`(ブラウザ再認可が必要)。
    `post_form`/`now` はテスト用に注入できる。
    """
    from core import token_store  # 遅延 import(token_store → oauth の循環回避)

    bundle = token_store.load(pc.product)
    if bundle is None:
        raise ReloginRequired(
            f"{pc.product}: 保存トークンがありません。`python -m scripts.cli mf login "
            f"--product {pc.product}` を実行してください。"
        )
    if not bundle.is_expired(now=now):
        return bundle.access_token
    if not bundle.refresh_token:
        raise ReloginRequired(
            f"{pc.product}: アクセストークンが失効し refresh_token もありません。"
            f"`mf login --product {pc.product}` で再認可してください。"
        )
    poster = post_form or _default_post_form
    url, data, headers = build_refresh_request(pc, bundle.refresh_token)
    payload = poster(url, data, headers)
    new_bundle = parse_token_response(payload, now=now)
    if not new_bundle.refresh_token:  # 応答が refresh_token を省略したら旧値を引き継ぐ
        new_bundle.refresh_token = bundle.refresh_token
    token_store.save(pc.product, new_bundle)
    return new_bundle.access_token
