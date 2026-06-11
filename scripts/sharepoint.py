#!/usr/bin/env python3
"""sharepoint.py — MAGI の入出力を SharePoint(Microsoft Graph)と同期する薄いブリッジ。

ask_openai.py / ask_gemini.py と同じ「ファシリテーターが呼ぶ薄いブリッジ」の作法に倣う。
クライアントシークレット(アプリ)認証でドキュメントライブラリと読み書きし、ローカルの
ミラーディレクトリ `prototype/sharepoint/` と遠隔を `pull` / `push` で同期する。

入出力 root は `sharepoint.config.json` の "enabled" で切り替わる:
  enabled: true  → root = prototype/sharepoint/(遠隔と同期するミラー)
  enabled: false → root = prototype/local/(純ローカル。同期しない)
両 root とも input / media-output / reviews / deliberations / brainstorms / persona-tests の構成は同一。

サブコマンド:
  python scripts/sharepoint.py root                 アクティブ root の絶対パスを出力
  python scripts/sharepoint.py status               設定・enabled・root を表示(ネットワーク不使用)
  python scripts/sharepoint.py test                 認証 + site/drive 解決まで検証
  python scripts/sharepoint.py pull [name ...]      遠隔 → ローカル(既定: input)
  python scripts/sharepoint.py push [name ...]      ローカル → 遠隔(既定: reviews deliberations brainstorms persona-tests media-output)
  python scripts/sharepoint.py info <localpath>     ローカルミラーパスに対応する SharePoint URL を出力

name は folders マップのキー(input / media-output / reviews / deliberations / brainstorms / persona-tests)。

設定(prototype/sharepoint.config.json、非機密・追跡):
  enabled / site_url / drive / root(遠隔基点フォルダ)/ folders(ローカル名 ↔ 遠隔名)
シークレット(環境変数 → ルートの .env → .claude/settings.local.json の env、bridge_common と同じ解決):
  MAGI_SHAREPOINT_TENANT_ID / MAGI_SHAREPOINT_CLIENT_ID / MAGI_SHAREPOINT_CLIENT_SECRET
  (任意)MAGI_SHAREPOINT_SITE_URL / MAGI_SHAREPOINT_DRIVE で config を上書き
Azure 側: アプリ登録 + アプリケーション許可 Sites.ReadWrite.All に管理者同意が必要。

依存: 標準ライブラリのみ(HTTP は bridge_common 経由で urllib)。
"""
import argparse
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bridge_common as bc  # noqa: E402

PROVIDER = "Microsoft Graph"
GRAPH = "https://graph.microsoft.com/v1.0"
UPLOAD_CHUNK = 4 * 1024 * 1024  # 4MiB。これ未満は単純 PUT、以上はアップロードセッション分割
DEFAULT_PULL = ["input"]
DEFAULT_PUSH = ["reviews", "deliberations", "brainstorms", "persona-tests", "media-output"]

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROTO = os.path.normpath(os.path.join(_HERE, os.pardir))
_CONFIG_PATH = os.path.join(_PROTO, "sharepoint.config.json")


# --------------------------------------------------------------------------- #
# 設定 / root 解決
# --------------------------------------------------------------------------- #
def load_config():
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"error: 設定が見つかりません: {_CONFIG_PATH}")
    except ValueError as e:
        raise SystemExit(f"error: sharepoint.config.json が不正な JSON です: {e}")
    cfg.setdefault("enabled", False)
    cfg.setdefault("drive", "Documents")
    cfg.setdefault("root", "")
    cfg.setdefault("folders", {})
    # env(→ settings.local.json)で config を上書きできる(bridge_common と同じ解決順)。
    # オンオフ・接続先を Git 追跡外の settings.local.json に置けるようにするため。
    env_enabled = bc.get_setting("MAGI_SHAREPOINT_ENABLED")
    if env_enabled is not None:
        cfg["enabled"] = _parse_bool(env_enabled)
    else:
        cfg["enabled"] = bool(cfg.get("enabled", False))
    cfg["site_url"] = bc.get_setting("MAGI_SHAREPOINT_SITE_URL") or cfg.get("site_url", "")
    cfg["drive"] = bc.get_setting("MAGI_SHAREPOINT_DRIVE") or cfg["drive"]
    cfg["root"] = bc.get_setting("MAGI_SHAREPOINT_ROOT") or cfg.get("root", "")
    return cfg


def _parse_bool(v):
    """env の真偽表現を bool に。1/true/yes/on(大小無視)を真、それ以外を偽とする。"""
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def active_root_name(cfg):
    return "sharepoint" if cfg.get("enabled") else "local"


def active_root_path(cfg):
    return os.path.join(_PROTO, active_root_name(cfg))


def local_dir(cfg, name):
    """folders キー name に対応するアクティブ root 下のローカルディレクトリ。"""
    if name not in cfg["folders"]:
        raise SystemExit(
            f"error: 未知のフォルダ名: {name}(有効: {', '.join(cfg['folders']) or 'なし'})"
        )
    return os.path.join(active_root_path(cfg), name)


def remote_dir(cfg, name):
    """folders キー name に対応する遠隔のサーバ相対パス(root/<folder>)。"""
    sub = cfg["folders"][name]
    parts = [p for p in (cfg.get("root", ""), sub) if p]
    return "/".join(parts)


# --------------------------------------------------------------------------- #
# 認証 / Graph 呼び出し
# --------------------------------------------------------------------------- #
def get_token(cfg):
    tenant = bc.get_setting("MAGI_SHAREPOINT_TENANT_ID")
    client_id = bc.get_setting("MAGI_SHAREPOINT_CLIENT_ID")
    secret = bc.get_setting("MAGI_SHAREPOINT_CLIENT_SECRET")
    missing = [
        n
        for n, v in (
            ("MAGI_SHAREPOINT_TENANT_ID", tenant),
            ("MAGI_SHAREPOINT_CLIENT_ID", client_id),
            ("MAGI_SHAREPOINT_CLIENT_SECRET", secret),
        )
        if not v
    ]
    if missing:
        raise SystemExit(
            "error: SharePoint の認証情報が未設定です: "
            + ", ".join(missing)
            + "\nルートの .env(推奨)か環境変数、または .claude/settings.local.json の env に設定してください。"
        )
    url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    body = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": secret,
            "scope": "https://graph.microsoft.com/.default",
        }
    ).encode()
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    try:
        data = bc.http_json("POST", url, headers, body, provider=PROVIDER)
    except SystemExit:
        raise
    except bc.ProviderHTTPError as e:
        raise SystemExit(bc.fmt_http_error(PROVIDER + " (token)", e))
    token = data.get("access_token")
    if not token:
        raise SystemExit(f"error: トークン取得に失敗しました: {data}")
    return token


def _auth_headers(token, extra=None):
    h = {"Authorization": f"Bearer {token}"}
    if extra:
        h.update(extra)
    return h


def graph_json(method, url, token, body=None, content_type="application/json"):
    headers = _auth_headers(token)
    data = None
    if body is not None:
        if content_type == "application/json":
            data = json.dumps(body).encode("utf-8")
        else:
            data = body  # 既に bytes
        headers["Content-Type"] = content_type
    if not url.startswith("http"):
        url = GRAPH + url
    try:
        return bc.http_json(method, url, headers, data, provider=PROVIDER)
    except bc.ProviderHTTPError as e:
        raise SystemExit(bc.fmt_http_error(PROVIDER, e))


def resolve_site(cfg, token):
    site_url = (cfg.get("site_url") or "").strip().rstrip("/")
    if not site_url or "<tenant>" in site_url:
        raise SystemExit(
            "error: site_url が未設定です。sharepoint.config.json か "
            "MAGI_SHAREPOINT_SITE_URL に SharePoint サイト URL を設定してください。"
        )
    parsed = urllib.parse.urlparse(site_url)
    host = parsed.netloc
    path = parsed.path  # 例: /sites/MAGI
    if not host:
        raise SystemExit(f"error: site_url が不正です: {site_url}")
    data = graph_json("GET", f"/sites/{host}:{path}", token)
    return data["id"]


def resolve_drive(cfg, token, site_id):
    want = (cfg.get("drive") or "Documents").strip()
    data = graph_json("GET", f"/sites/{site_id}/drives", token)
    for d in data.get("value", []):
        if d.get("name", "").lower() == want.lower():
            return d["id"]
    # 名前一致が無ければ既定のドキュメントライブラリにフォールバック
    default = graph_json("GET", f"/sites/{site_id}/drive", token)
    sys.stderr.write(
        f"warn: drive '{want}' が見つからないため既定ライブラリ "
        f"'{default.get('name', '?')}' を使います\n"
    )
    return default["id"]


# --------------------------------------------------------------------------- #
# pull / push
# --------------------------------------------------------------------------- #
def _list_children(drive_id, remote_path, token):
    """遠隔フォルダ直下の driveItem を列挙(ページング対応)。空/未存在は []。"""
    if remote_path:
        enc = urllib.parse.quote(remote_path)
        url = f"/drives/{drive_id}/root:/{enc}:/children"
    else:
        url = f"/drives/{drive_id}/root/children"
    items = []
    while url:
        try:
            data = graph_json("GET", url, token)
        except SystemExit as e:
            if "HTTP 404" in str(e):  # フォルダ未作成は空扱い
                return []
            raise
        items.extend(data.get("value", []))
        url = data.get("@odata.nextLink")
    return items


def pull_folder(drive_id, remote_path, local_path, token):
    """遠隔 remote_path 配下を local_path へ再帰ダウンロード。件数を返す。"""
    os.makedirs(local_path, exist_ok=True)
    count = 0
    for item in _list_children(drive_id, remote_path, token):
        name = item["name"]
        dest = os.path.join(local_path, name)
        if item.get("folder"):
            count += pull_folder(drive_id, f"{remote_path}/{name}", dest, token)
            continue
        dl = item.get("@microsoft.graph.downloadUrl") or item.get("@content.downloadUrl")
        if not dl:  # フォールバック: content エンドポイント
            enc = urllib.parse.quote(f"{remote_path}/{name}")
            dl = f"/drives/{drive_id}/root:/{enc}:/content"
        try:
            # downloadUrl は事前認証済みなので認証ヘッダ無しで取得する
            hdr = {} if dl.startswith("http") else _auth_headers(token)
            url = dl if dl.startswith("http") else GRAPH + dl
            _, content = bc.http_raw("GET", url, hdr, None, provider=PROVIDER)
        except bc.ProviderHTTPError as e:
            raise SystemExit(bc.fmt_http_error(PROVIDER, e))
        with open(dest, "wb") as f:
            f.write(content)
        sys.stderr.write(f"  pull: {name} ({len(content)} bytes)\n")
        count += 1
    return count


def _ensure_remote_path(drive_id, remote_path, token):
    """遠隔フォルダ階層を作成(冪等)。root 直下から1段ずつ作る。"""
    if not remote_path:
        return
    parts = remote_path.split("/")
    parent = ""  # サーバ相対(root: 基準)
    for part in parts:
        cur = f"{parent}/{part}" if parent else part
        # 既存確認 → 無ければ親に作成
        try:
            graph_json("GET", f"/drives/{drive_id}/root:/{urllib.parse.quote(cur)}", token)
        except SystemExit as e:
            if "HTTP 404" not in str(e):
                raise
            if parent:
                base = f"/drives/{drive_id}/root:/{urllib.parse.quote(parent)}:/children"
            else:
                base = f"/drives/{drive_id}/root/children"
            graph_json(
                "POST",
                base,
                token,
                {"name": part, "folder": {}, "@microsoft.graph.conflictBehavior": "replace"},
            )
        parent = cur


def _upload_small(drive_id, remote_file, data, token):
    enc = urllib.parse.quote(remote_file)
    url = f"/drives/{drive_id}/root:/{enc}:/content"
    graph_json("PUT", url, token, body=data, content_type="application/octet-stream")


def _upload_large(drive_id, remote_file, path, size, token):
    enc = urllib.parse.quote(remote_file)
    sess = graph_json(
        "POST",
        f"/drives/{drive_id}/root:/{enc}:/createUploadSession",
        token,
        {"item": {"@microsoft.graph.conflictBehavior": "replace"}},
    )
    upload_url = sess["uploadUrl"]
    with open(path, "rb") as f:
        start = 0
        while start < size:
            chunk = f.read(UPLOAD_CHUNK)
            end = start + len(chunk) - 1
            headers = {
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {start}-{end}/{size}",
            }
            try:
                bc.http_json("PUT", upload_url, headers, chunk, provider=PROVIDER)
            except bc.ProviderHTTPError as e:
                raise SystemExit(bc.fmt_http_error(PROVIDER + " (upload)", e))
            start = end + 1


def push_folder(drive_id, local_path, remote_path, token):
    """ローカル local_path 配下を遠隔 remote_path へ再帰アップロード。件数を返す。"""
    if not os.path.isdir(local_path):
        return 0
    _ensure_remote_path(drive_id, remote_path, token)
    count = 0
    for entry in sorted(os.listdir(local_path)):
        if entry == ".gitkeep":
            continue
        src = os.path.join(local_path, entry)
        remote_file = f"{remote_path}/{entry}" if remote_path else entry
        if os.path.isdir(src):
            count += push_folder(drive_id, src, remote_file, token)
            continue
        size = os.path.getsize(src)
        if size < UPLOAD_CHUNK:
            with open(src, "rb") as f:
                _upload_small(drive_id, remote_file, f.read(), token)
        else:
            _upload_large(drive_id, remote_file, src, size, token)
        sys.stderr.write(f"  push: {entry} ({size} bytes)\n")
        count += 1
    return count


# --------------------------------------------------------------------------- #
# サブコマンド
# --------------------------------------------------------------------------- #
def cmd_root(cfg, _args):
    sys.stdout.write(active_root_path(cfg) + "\n")


def cmd_status(cfg, _args):
    print(f"enabled    : {cfg.get('enabled')}")
    print(f"active root: {active_root_path(cfg)}  ({active_root_name(cfg)}/)")
    print(f"site_url   : {cfg.get('site_url') or '(未設定)'}")
    print(f"drive      : {cfg.get('drive')}")
    print(f"remote root: {cfg.get('root') or '(ライブラリ直下)'}")
    print("folders    :")
    for k, v in cfg["folders"].items():
        print(f"  {k:14s} ↔ {remote_dir(cfg, k) or '(直下)'}")
    if not cfg.get("enabled"):
        print("\n注: enabled=false。pull/push は SharePoint と通信しません(local/ を使用)。")


def _require_enabled(cfg):
    if not cfg.get("enabled"):
        sys.stderr.write(
            "SharePoint 無効(enabled=false)。pull/push は何もしません。"
            "local/ をそのまま使ってください。\n"
        )
        raise SystemExit(0)


def cmd_test(cfg, _args):
    _require_enabled(cfg)
    token = get_token(cfg)
    print("token      : OK")
    site_id = resolve_site(cfg, token)
    print(f"site id    : {site_id}")
    drive_id = resolve_drive(cfg, token, site_id)
    print(f"drive id   : {drive_id}")
    print("認証・サイト・ドライブの解決に成功しました。")


def cmd_pull(cfg, args):
    _require_enabled(cfg)
    names = args.names or DEFAULT_PULL
    token = get_token(cfg)
    site_id = resolve_site(cfg, token)
    drive_id = resolve_drive(cfg, token, site_id)
    total = 0
    for name in names:
        rp, lp = remote_dir(cfg, name), local_dir(cfg, name)
        sys.stderr.write(f"pull {name}: {rp or '(直下)'} → {lp}\n")
        total += pull_folder(drive_id, rp, lp, token)
    print(f"pull 完了: {total} ファイル")


def cmd_push(cfg, args):
    _require_enabled(cfg)
    names = args.names or DEFAULT_PUSH
    token = get_token(cfg)
    site_id = resolve_site(cfg, token)
    drive_id = resolve_drive(cfg, token, site_id)
    total = 0
    for name in names:
        rp, lp = remote_dir(cfg, name), local_dir(cfg, name)
        sys.stderr.write(f"push {name}: {lp} → {rp or '(直下)'}\n")
        total += push_folder(drive_id, lp, rp, token)
    print(f"push 完了: {total} ファイル")


def cmd_info(cfg, args):
    _require_enabled(cfg)
    target = os.path.abspath(args.path)
    root = os.path.abspath(active_root_path(cfg))
    if not target.startswith(root):
        raise SystemExit(f"error: パスがアクティブ root({root})の外です: {target}")
    rel = os.path.relpath(target, root).replace(os.sep, "/")
    top = rel.split("/", 1)[0]
    if top not in cfg["folders"]:
        raise SystemExit(f"error: '{top}' は folders に未定義です")
    sub = rel.split("/", 1)[1] if "/" in rel else ""
    remote = remote_dir(cfg, top) + (f"/{sub}" if sub else "")
    token = get_token(cfg)
    site_id = resolve_site(cfg, token)
    drive_id = resolve_drive(cfg, token, site_id)
    try:
        item = graph_json(
            "GET", f"/drives/{drive_id}/root:/{urllib.parse.quote(remote)}", token
        )
        sys.stdout.write(item.get("webUrl", "(webUrl なし)") + "\n")
    except SystemExit as e:
        if "HTTP 404" in str(e):
            sys.stderr.write("warn: 遠隔にまだ存在しません(push 前)。想定パスを表示します。\n")
            sys.stdout.write(f"{cfg['site_url'].rstrip('/')}/{cfg['drive']}/{remote}\n")
        else:
            raise


COMMANDS = {
    "root": cmd_root,
    "status": cmd_status,
    "test": cmd_test,
    "pull": cmd_pull,
    "push": cmd_push,
    "info": cmd_info,
}


def main():
    p = argparse.ArgumentParser(description="MAGI の入出力を SharePoint と同期するブリッジ")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("root", help="アクティブ root の絶対パスを出力")
    sub.add_parser("status", help="設定・enabled・root を表示(通信なし)")
    sub.add_parser("test", help="認証 + site/drive 解決を検証")
    pp = sub.add_parser("pull", help="遠隔 → ローカル(既定: input)")
    pp.add_argument("names", nargs="*", help="folders キー(既定: input)")
    pu = sub.add_parser("push", help="ローカル → 遠隔(既定: reviews deliberations brainstorms persona-tests media-output)")
    pu.add_argument("names", nargs="*", help="folders キー(既定: reviews deliberations brainstorms persona-tests media-output)")
    pi = sub.add_parser("info", help="ローカルミラーパスに対応する SharePoint URL を出力")
    pi.add_argument("path", help="アクティブ root 下のローカルパス")
    args = p.parse_args()
    cfg = load_config()
    COMMANDS[args.cmd](cfg, args)


if __name__ == "__main__":
    main()
