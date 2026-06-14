r"""MoneyForward API 疎通スパイク(設定の仕組みを使った最小の実接続)。会計 / 経費の両対応。

`core/moneyforward.py` が解決したプロダクト別の接続設定を使い、**まず offices を開く**
(取得できれば認証と権限の最小確認になる)。標準ライブラリ(urllib)のみ。手動実行用(実 credentials が必要):

  cd Accounting
  ..\.venv\Scripts\python.exe scripts\spike_moneyforward.py --product expense
  ..\.venv\Scripts\python.exe scripts\spike_moneyforward.py --product accounting

前提(docs/caveats.md・docs/setup/moneyforward-api-setup.md):
- MoneyForward は **OAuth 2.0 認可コードフロー**(grant_type=authorization_code)。先にブラウザで認可して
  `code` を取得し、`MONEYFORWARD_<PRODUCT>_AUTH_CODE` に設定しておく。
- **保存トークンがあれば再利用**(`var/moneyforward/`・gitignore)。失効時は refresh_token で更新するため、
  2回目以降はブラウザ不要。会計は `python -m scripts.cli mf login --product accounting` で認可〜code 取得〜
  保存まで自動化できる(BL-AC-016)。
- 会計と経費は別の client_id/secret・別エンドポイント。`--product` で切り替える。
- **正確なエンドポイント/スコープは公式(開発者サイト / Swagger)で確認する**(archive 済みは使わない)。
- 秘密は .env から読む。リポジトリに鍵を置かない。本番への破壊的テストはしない。

env(任意・プロダクト別に上書き):
  MONEYFORWARD_<PRODUCT>_GRANT_TYPE   token の grant_type(既定 authorization_code)
  MONEYFORWARD_<PRODUCT>_AUTH_CODE    認可後にリダイレクトで受け取った code
  MONEYFORWARD_<PRODUCT>_OFFICES_URL  offices 取得 URL(未設定なら api_base + "/offices")
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Accounting/ を import パスへ

from core import moneyforward as mf  # noqa: E402
from core import oauth, token_store  # noqa: E402
from core.config import get_setting  # noqa: E402

_TIMEOUT = 30


def _penv(product: str, name: str) -> str | None:
    return get_setting(f"MONEYFORWARD_{product.upper()}_{name.upper()}")


def _post_form(url: str, data: dict[str, str], headers: dict[str, str] | None = None) -> dict:
    body = urllib.parse.urlencode(data).encode("utf-8")
    hdrs = {"Content-Type": "application/x-www-form-urlencoded"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310(信頼できる設定 URL のみ)
        return json.loads(resp.read().decode("utf-8"))


def _get_json(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def build_token_request(pc: mf.ProductConfig) -> tuple[str, dict[str, str], dict[str, str]]:
    """token リクエストを組み立てる(後方互換ラッパ)。env から grant_type/auth_code を読み
    `core.oauth.build_token_request` へ委譲する。code 未設定(認可コードフロー)は SystemExit。"""
    grant_type = _penv(pc.product, "grant_type") or "authorization_code"
    auth_code = _penv(pc.product, "auth_code")
    if grant_type == "authorization_code" and not auth_code:
        raise SystemExit(
            f"error: grant_type=authorization_code には MONEYFORWARD_{pc.product.upper()}_AUTH_CODE が必要です"
            "(先にブラウザで認可して code を取得 — `mf login` か docs/setup/moneyforward-api-setup.md)"
        )
    return oauth.build_token_request(
        pc, auth_code=auth_code, redirect_uri=pc.redirect_uri, grant_type=grant_type
    )


def fetch_token(pc: mf.ProductConfig) -> oauth.TokenBundle:
    """token エンドポイントで交換し、`TokenBundle` を保存して返す(既定は認可コードフロー)。"""
    url, data, headers = build_token_request(pc)
    payload = _post_form(url, data, headers=headers)
    try:
        bundle = oauth.parse_token_response(payload)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from exc
    token_store.save(pc.product, bundle)
    return bundle


def _offices_url(pc: mf.ProductConfig) -> str | None:
    """疎通確認の呼び先 URL を決める(env 上書き → config の offices_url → api_base + /offices)。

    会計は認可サーバ v2 の `/v2/tenant`(config に記入済・2026-06-14 実機検証済)。
    パスが `/offices` 形でない系統は config の `api.offices_url` で明示する。無ければ None。
    """
    url = _penv(pc.product, "offices_url") or pc.offices_url
    if url:
        return url
    base = (pc.api_base or "").rstrip("/")
    return base + "/offices" if base else None


# offices 応答を包む、よくあるキー(API/バージョンで揺れる)。先頭から順に試す。
_OFFICE_LIST_KEYS = ("offices", "data", "items", "results")


def count_offices(payload: object) -> int | None:
    """offices 応答から件数だけを取り出す(応答形状の差を吸収)。判別できなければ None。

    秘匿性(口座名・事業者名)があるため **件数のみ** を返す(生値は返さない — caveats.md)。
    対応する形: 素のリスト / {"offices"|"data"|...: [...]} / {"data": {"offices": [...]}}(二段) /
    リスト値が1つだけの dict。
    """
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in _OFFICE_LIST_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
            if isinstance(value, dict):  # {"data": {"offices": [...]}} の二段包み
                for inner in _OFFICE_LIST_KEYS:
                    nested = value.get(inner)
                    if isinstance(nested, list):
                        return len(nested)
        # 包みキーが想定外でも、リスト値が1つだけならそれを件数とみなす。
        lists = [v for v in payload.values() if isinstance(v, list)]
        if len(lists) == 1:
            return len(lists[0])
    return None


def run(product: str) -> int:
    pc = mf.load_product(product)
    if not pc.is_ready():
        print(
            f"[{product}] {pc.label} の接続設定が未完了です。"
            f"`python -m scripts.cli mf config --product {product}` で確認してください。\n"
            f"未設定の必須項目: {', '.join(pc.missing_required())}\n"
            f"秘密は .env(MONEYFORWARD_{product.upper()}_CLIENT_SECRET 等)、"
            "URL は config/moneyforward.config.json に設定します。",
            file=sys.stderr,
        )
        return 1

    # 1) アクセストークンを用意(保存済みを再利用 → 失効なら refresh → 無ければ AUTH_CODE で交換)
    try:
        try:
            token = oauth.get_access_token(pc)
            print(f"[{product}] OAuth: 保存トークンを再利用しました(ブラウザ不要)。")
        except oauth.ReloginRequired:
            bundle = fetch_token(pc)
            token = bundle.access_token
            print(
                f"[{product}] OAuth: 認可コードで交換 OK"
                f"(access len={len(token)} / refresh={'有' if bundle.refresh_token else '無'})。保存しました。"
            )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        print(f"error: トークン交換に失敗: HTTP {exc.code} {exc.reason}\n{detail}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"error: 接続失敗: {exc.reason}", file=sys.stderr)
        return 1

    # 2) offices 疎通(URL が分かる場合のみ。無ければトークン成功で合格扱い)
    url = _offices_url(pc)
    if not url:
        print(
            f"[{product}] offices URL 未設定のためトークン交換のみ確認しました(疎通の主テストは合格)。\n"
            f"  REST 疎通も見るなら MONEYFORWARD_{product.upper()}_OFFICES_URL か "
            "config の api.base を設定してください。"
        )
        return 0
    try:
        offices = _get_json(url, token)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        print(f"warn: トークンは取得 OK。offices 取得は失敗: HTTP {exc.code} {exc.reason}\n{detail}", file=sys.stderr)
        return 0
    except urllib.error.URLError as exc:
        print(f"warn: トークンは取得 OK。offices 接続失敗: {exc.reason}", file=sys.stderr)
        return 0

    # offices の中身(口座名等)は秘匿性があるため件数のみ表示する。
    count = count_offices(offices)
    if count is None:
        # 件数を判別できなくても、応答が返った時点で疎通は確認できている(キーのみ表示)。
        keys = list(offices) if isinstance(offices, dict) else "(list)"
        print(f"[{product}] offices: 取得 OK(件数は不明。応答キー: {keys})。疎通確認できました。")
    else:
        print(f"[{product}] offices: 取得 OK(件数={count})。疎通確認できました。")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MoneyForward API 疎通スパイク(会計 / 経費)")
    parser.add_argument(
        "--product", choices=["accounting", "expense"], default="expense",
        help="対象プロダクト(既定: expense)",
    )
    args = parser.parse_args(argv)
    return run(args.product)


if __name__ == "__main__":
    sys.exit(main())
