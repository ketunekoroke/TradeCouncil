"""MoneyForward API 接続設定の解決(zero-dep)。

設定の置き場所(ADR-0011 / docs/design.md):
  - 非秘密(OAuth/API のエンドポイント・リダイレクト・スコープ・enabled): `config/moneyforward.config.json`
  - 秘密(client_secret)と上書き: ルート共有 `.env`(`MONEYFORWARD_*`。BYBIT_* と同じくドメイン別プレフィックス)

各フィールドの解決順(SharePoint と同じ — shared/sharepoint.py):
  1) プロジェクト別 env  `MONEYFORWARD_<env_prefix>_<FIELD>`(既定 env_prefix=AC)
  2) config の値        (非秘密の識別子・URL のみ。プレースホルダは無視)
  3) 共有 env           `MONEYFORWARD_<FIELD>`

正確なエンドポイント/スコープは **製品ドメインの Swagger / 開発者ポータルで確認** すること
(archive 済みドキュメントは使わない — docs/caveats.md)。config の URL は既定空で、確認後に記入する。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from core.config import PROJECT_ROOT, get_setting

CONFIG_PATH = PROJECT_ROOT / "config" / "moneyforward.config.json"
DOMAIN = "MONEYFORWARD"

# 接続が成立するために最低限必要なフィールド(検証ゲート・spike の前提)。
REQUIRED = ("client_id", "client_secret", "token_url")


@dataclass
class MoneyForwardConfig:
    enabled: bool
    env_prefix: str
    client_id: str | None
    client_secret: str | None
    authorize_url: str | None
    token_url: str | None
    redirect_uri: str | None
    scopes: list[str] = field(default_factory=list)
    expense_base: str | None = None
    accounting_base: str | None = None
    box_base: str | None = None

    def missing_required(self) -> list[str]:
        """接続に不足しているフィールド名を返す(空なら ready)。"""
        return [name for name in REQUIRED if not getattr(self, name)]

    def is_ready(self) -> bool:
        return not self.missing_required()

    def masked(self) -> dict[str, object]:
        """画面表示用の要約。秘密は値を出さない(set/unset と長さのみ)。"""
        return {
            "enabled": self.enabled,
            "env_prefix": self.env_prefix,
            "client_id": _mask_id(self.client_id),
            "client_secret": _mask_secret(self.client_secret),
            "authorize_url": self.authorize_url or "(未設定)",
            "token_url": self.token_url or "(未設定)",
            "redirect_uri": self.redirect_uri or "(未設定)",
            "scopes": self.scopes,
            "expense_base": self.expense_base or "(未設定)",
            "accounting_base": self.accounting_base or "(未設定)",
            "box_base": self.box_base or "(未設定)",
            "ready": self.is_ready(),
            "missing": self.missing_required(),
        }


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


def _field(env_prefix: str, name: str, config_value: object) -> str | None:
    """非秘密フィールドの解決: プロジェクト別 env → config 値 → 共有 env。"""
    if env_prefix:
        v = get_setting(f"{DOMAIN}_{env_prefix}_{name.upper()}")
        if v:
            return v
    if _is_real(config_value):
        return str(config_value).strip()
    return get_setting(f"{DOMAIN}_{name.upper()}")


def _secret(env_prefix: str, name: str) -> str | None:
    """秘密フィールドの解決: プロジェクト別 env → 共有 env(config には置かない)。"""
    if env_prefix:
        v = get_setting(f"{DOMAIN}_{env_prefix}_{name.upper()}")
        if v:
            return v
    return get_setting(f"{DOMAIN}_{name.upper()}")


def _parse_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def load_config(path: Path | None = None) -> MoneyForwardConfig:
    """`config/moneyforward.config.json` + env から接続設定を構築する。path 指定はテスト用。"""
    cfg_path = path or CONFIG_PATH
    raw: dict = {}
    if cfg_path.is_file():
        try:
            raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise SystemExit(f"error: moneyforward.config.json が不正な JSON です: {exc}")

    env_prefix = str(raw.get("env_prefix") or "").strip().upper()
    oauth = raw.get("oauth") or {}
    api = raw.get("api") or {}

    # enabled は env(プロジェクト別 → 共有)で上書き可能。未設定なら config 値。
    env_enabled = _field(env_prefix, "enabled", None)
    enabled = _parse_bool(env_enabled, default=_parse_bool(raw.get("enabled"), False))

    # scopes は config(リスト)優先、env はスペース/カンマ区切り文字列で上書き可。
    scopes_env = _field(env_prefix, "scopes", None)
    if scopes_env:
        scopes = [s for s in scopes_env.replace(",", " ").split() if s]
    else:
        scopes = [str(s) for s in (oauth.get("scopes") or []) if str(s).strip()]

    return MoneyForwardConfig(
        enabled=enabled,
        env_prefix=env_prefix,
        client_id=_field(env_prefix, "client_id", raw.get("client_id")),
        client_secret=_secret(env_prefix, "client_secret"),
        authorize_url=_field(env_prefix, "authorize_url", oauth.get("authorize_url")),
        token_url=_field(env_prefix, "token_url", oauth.get("token_url")),
        redirect_uri=_field(env_prefix, "redirect_uri", oauth.get("redirect_uri")),
        scopes=scopes,
        expense_base=_field(env_prefix, "expense_base", api.get("expense_base")),
        accounting_base=_field(env_prefix, "accounting_base", api.get("accounting_base")),
        box_base=_field(env_prefix, "box_base", api.get("box_base")),
    )
