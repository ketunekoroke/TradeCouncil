r"""MoneyForward API 疎通スパイク(設定の仕組みを使った最小の実接続)。

`core/moneyforward.py` が解決した接続設定を使い、**まず offices を開く**(取得できれば認証と権限の
最小確認になる)。標準ライブラリ(urllib)のみ。手動実行用(実 credentials が必要):

  cd Accounting
  ..\.venv\Scripts\python.exe scripts\spike_moneyforward.py

前提(docs/caveats.md):
- スモールビジネスプランで開発者向け API が有効化できるかを実アカウントで確認する。
- **正確なエンドポイント/スコープ/グラントは製品ドメインの Swagger / 開発者ポータルで確認する**
  (archive 済み expense-api-doc は使わない)。URL は config/moneyforward.config.json に記入。
- 秘密(client_secret)は .env から読む。リポジトリに鍵を置かない。本番への破壊的テストはしない。

env(任意・grant の調整):
  MONEYFORWARD_GRANT_TYPE   token エンドポイントの grant_type(既定 client_credentials)
  MONEYFORWARD_AUTH_CODE    authorization_code グラント時の code
  MONEYFORWARD_OFFICES_URL  offices 取得 URL(未設定なら accounting_base + "/offices")
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Accounting/ を import パスへ

from core import moneyforward as mf  # noqa: E402
from core.config import get_setting  # noqa: E402

_TIMEOUT = 30


def _post_form(url: str, data: dict[str, str]) -> dict:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310(信頼できる設定 URL のみ)
        return json.loads(resp.read().decode("utf-8"))


def _get_json(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def fetch_token(cfg: mf.MoneyForwardConfig) -> str:
    """token エンドポイントからアクセストークンを取得する(grant_type は env で調整可)。"""
    grant_type = get_setting("MONEYFORWARD_GRANT_TYPE") or "client_credentials"
    data = {
        "grant_type": grant_type,
        "client_id": cfg.client_id or "",
        "client_secret": cfg.client_secret or "",
    }
    if cfg.scopes:
        data["scope"] = " ".join(cfg.scopes)
    if grant_type == "authorization_code":
        code = get_setting("MONEYFORWARD_AUTH_CODE")
        if not code:
            raise SystemExit("error: grant_type=authorization_code には MONEYFORWARD_AUTH_CODE が必要です")
        data["code"] = code
        if cfg.redirect_uri:
            data["redirect_uri"] = cfg.redirect_uri
    payload = _post_form(cfg.token_url or "", data)
    token = payload.get("access_token")
    if not token:
        raise SystemExit(f"error: access_token を取得できませんでした(応答キー: {list(payload)})")
    return str(token)


def fetch_offices(cfg: mf.MoneyForwardConfig, token: str) -> dict:
    """offices を取得して疎通確認する(最初のステップ — docs/caveats.md)。"""
    url = get_setting("MONEYFORWARD_OFFICES_URL")
    if not url:
        base = (cfg.accounting_base or "").rstrip("/")
        if not base:
            raise SystemExit(
                "error: offices の URL が不明です。MONEYFORWARD_OFFICES_URL を設定するか、"
                "config の api.accounting_base を Swagger で確認して記入してください"
            )
        url = base + "/offices"
    return _get_json(url, token)


def main() -> int:
    cfg = mf.load_config()
    if not cfg.is_ready():
        print(
            "MoneyForward 接続設定が未完了です。`python -m scripts.cli mf config` で確認してください。\n"
            f"未設定の必須項目: {', '.join(cfg.missing_required())}\n"
            "秘密は .env(MONEYFORWARD_CLIENT_SECRET 等)、URL は config/moneyforward.config.json に設定します。",
            file=sys.stderr,
        )
        return 1
    try:
        token = fetch_token(cfg)
        print(f"OAuth: アクセストークン取得 OK(len={len(token)})")
        offices = fetch_offices(cfg, token)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        print(f"error: HTTP {exc.code} {exc.reason}\n{detail}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"error: 接続失敗: {exc.reason}", file=sys.stderr)
        return 1

    # offices の中身(口座名等)は秘匿性があるため件数のみ表示する。
    count = len(offices.get("data", offices)) if isinstance(offices, (list, dict)) else "?"
    print(f"offices: 取得 OK(件数={count})。疎通確認できました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
