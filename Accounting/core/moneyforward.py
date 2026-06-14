"""MoneyForward API 接続設定の解決(zero-dep)。会計(accounting)と経費(expense)の2系統に対応。

会計と経費は **別の OAuth サーバ・別の client_id/secret**(片方の資格情報は他方で使えない —
docs/setup/moneyforward-api-setup.md)。プロダクトごとに設定を解決する。

設定の置き場所(ADR-0011 / docs/design.md):
  - 非秘密(OAuth/API の URL・scopes・client_id・enabled): `config/moneyforward.config.json` の products.<product>
  - 秘密(client_secret)と上書き: ルート共有 `.env`(`MONEYFORWARD_<PRODUCT>_*`。ドメイン別プレフィックス)

各フィールドの解決順:
  1) env  `MONEYFORWARD_<PRODUCT>_<FIELD>`(例 MONEYFORWARD_EXPENSE_CLIENT_SECRET)
  2) config の値(非秘密の識別子・URL のみ。プレースホルダは無視)

正確なスコープ/エンドポイントは公式(開発者サイト / Swagger)で確認すること(docs/caveats.md)。
"""

from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

from core.config import PROJECT_ROOT, get_setting

CONFIG_PATH = PROJECT_ROOT / "config" / "moneyforward.config.json"
DOMAIN = "MONEYFORWARD"

# 対応プロダクト(キー: 内部名 / 値: 表示ラベル)。
PRODUCTS: dict[str, str] = {
    "accounting": "クラウド会計",
    "expense": "クラウド経費",
}

# 接続が成立するために最低限必要なフィールド(token 交換の前提)。
REQUIRED = ("client_id", "client_secret", "token_url")


@dataclass
class ProductConfig:
    """1プロダクト(会計 or 経費)の接続設定。"""

    product: str
    label: str
    enabled: bool
    client_id: str | None
    client_secret: str | None
    authorize_url: str | None
    token_url: str | None
    redirect_uri: str | None
    scopes: list[str] = field(default_factory=list)
    api_base: str | None = None
    offices_url: str | None = None  # 疎通確認の呼び先(未設定なら api_base + /offices)
    client_auth: str = "client_secret_basic"  # token エンドポイントの client 認証方式

    def missing_required(self) -> list[str]:
        return [name for name in REQUIRED if not getattr(self, name)]

    def is_ready(self) -> bool:
        return not self.missing_required()

    def masked(self) -> dict[str, object]:
        """画面表示用の要約。秘密は値を出さない(set/unset と長さのみ)。"""
        return {
            "label": self.label,
            "enabled": self.enabled,
            "client_id": _mask_id(self.client_id),
            "client_secret": _mask_secret(self.client_secret),
            "authorize_url": self.authorize_url or "(未設定)",
            "token_url": self.token_url or "(未設定)",
            "redirect_uri": self.redirect_uri or "(未設定)",
            "scopes": self.scopes,
            "api_base": self.api_base or "(未設定)",
            "offices_url": self.offices_url or "(未設定)",
            "client_auth": self.client_auth,
            "ready": self.is_ready(),
            "missing": self.missing_required(),
        }


@dataclass
class MoneyForwardConfig:
    """全プロダクトの接続設定をまとめたコンテナ。"""

    products: dict[str, ProductConfig]

    def get(self, product: str) -> ProductConfig:
        if product not in self.products:
            raise KeyError(f"未知のプロダクト: {product}(対応: {', '.join(self.products)})")
        return self.products[product]

    def ready_products(self) -> list[str]:
        return [name for name, cfg in self.products.items() if cfg.is_ready()]


def _mask_id(value: str | None) -> str:
    if not value:
        return "(未設定)"
    return f"{value[:4]}…(len={len(value)})" if len(value) > 4 else f"…(len={len(value)})"


def _mask_secret(value: str | None) -> str:
    return f"set(len={len(value)})" if value else "(未設定)"


def _is_real(value: object) -> bool:
    """config の値がプレースホルダ/空でない実値か。"""
    if not isinstance(value, str):
        return False
    v = value.strip()
    return bool(v) and "REPLACE" not in v and "<" not in v


def _env(product: str, name: str) -> str | None:
    return get_setting(f"{DOMAIN}_{product.upper()}_{name.upper()}")


def _field(product: str, name: str, config_value: object) -> str | None:
    """非秘密フィールドの解決: env(プロダクト別)→ config 値。"""
    v = _env(product, name)
    if v:
        return v
    if _is_real(config_value):
        return str(config_value).strip()
    return None


def _parse_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _load_product(product: str, raw: dict) -> ProductConfig:
    oauth = raw.get("oauth") or {}
    api = raw.get("api") or {}

    env_enabled = _env(product, "enabled")
    enabled = _parse_bool(env_enabled, default=_parse_bool(raw.get("enabled"), False))

    scopes_env = _env(product, "scopes")
    if scopes_env:
        scopes = [s for s in scopes_env.replace(",", " ").split() if s]
    else:
        scopes = [str(s) for s in (oauth.get("scopes") or []) if str(s).strip()]

    return ProductConfig(
        product=product,
        label=PRODUCTS.get(product, product),
        enabled=enabled,
        client_id=_field(product, "client_id", raw.get("client_id")),
        client_secret=_env(product, "client_secret"),  # 秘密は env のみ
        authorize_url=_field(product, "authorize_url", oauth.get("authorize_url")),
        token_url=_field(product, "token_url", oauth.get("token_url")),
        redirect_uri=_field(product, "redirect_uri", oauth.get("redirect_uri")),
        scopes=scopes,
        api_base=_field(product, "api_base", api.get("base")),
        offices_url=_field(product, "offices_url", api.get("offices_url")),
        client_auth=_field(product, "client_auth", oauth.get("client_auth")) or "client_secret_basic",
    )


def load_config(path: Path | None = None) -> MoneyForwardConfig:
    """`config/moneyforward.config.json` + env から全プロダクトの接続設定を構築する。path はテスト用。"""
    cfg_path = path or CONFIG_PATH
    raw: dict = {}
    if cfg_path.is_file():
        try:
            raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise SystemExit(f"error: moneyforward.config.json が不正な JSON です: {exc}")

    raw_products = raw.get("products") or {}
    products = {
        name: _load_product(name, raw_products.get(name) or {}) for name in PRODUCTS
    }
    return MoneyForwardConfig(products=products)


def load_product(product: str, path: Path | None = None) -> ProductConfig:
    """1プロダクトの設定だけを取得する近道(spike 等で使用)。"""
    return load_config(path).get(product)


def build_authorize_url(pc: ProductConfig, state: str | None = None) -> str:
    """認可コードフローの認可エンドポイント URL を組み立てる(秘密は含まない・client_id のみ)。

    生成される URL をブラウザで開き、許可後にリダイレクト先の `?code=...` を控える。
    redirect_uri はアプリ登録値と完全一致が必須(docs/setup/moneyforward-api-setup.md)。
    """
    if not pc.authorize_url:
        raise ValueError(f"{pc.product}: authorize_url が未設定です(config の oauth.authorize_url)")
    if not pc.client_id:
        raise ValueError(
            f"{pc.product}: client_id が未設定です(MONEYFORWARD_{pc.product.upper()}_CLIENT_ID または config)"
        )
    params = {"response_type": "code", "client_id": pc.client_id}
    if pc.redirect_uri:
        params["redirect_uri"] = pc.redirect_uri
    if pc.scopes:
        params["scope"] = " ".join(pc.scopes)
    if state:
        params["state"] = state
    return f"{pc.authorize_url}?{urllib.parse.urlencode(params)}"
