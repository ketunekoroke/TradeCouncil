#!/usr/bin/env python3
"""sharepoint.py — workspace/ を SharePoint(Microsoft Graph)と同期する薄いブリッジ。

ask_openai.py / ask_gemini.py と同じ「ファシリテーターが呼ぶ薄いブリッジ」の作法に倣う。
クライアントシークレット(アプリ)認証でドキュメントライブラリと読み書きする。

入出力 root は常に単一の `workspace/`(ADR-0009。local/sharepoint の二重ツリーは廃止)。
`sharepoint.config.json` の "enabled" は **SharePoint と同期通信するか**のみを制御する:
  enabled: true  → sync/pull/push が遠隔と通信する
  enabled: false → 純ローカル(sync 等は何もしない。作業場所は同じ workspace/)

同期(sync)の意味論 — 双方向・追加型・newer-wins:
  - 片側にしかないファイル → もう片方へコピー
  - 両側にあるファイル → 更新時刻の新しい方が勝つ(差が SYNC_SKEW_SEC 以内はスキップ)
  - **削除は伝播しない**(片側で消してももう片方に残る = 安全側。完全削除は両側で行う)
  - push/pull 後は遠隔の lastModifiedDateTime をローカル mtime に反映(ピンポン同期の防止)
  - 除外: .gitkeep / workspace 直下の README.md / *.tmp

docs ミラー(ADR-0010)— workspace 同期とは別系統の一方向ミラー:
  `git_mirror` 節(branch / remote / paths / files)で定義された docs/・ルート管理表を
  **git <branch> のコミット内容**から SharePoint `<remote>/`(既定 Docs/)へミラーする。
  作業ツリーは読まない(未コミットの編集は流れない)。**削除・リネームも反映**(完全ミラー)。
  前回ミラー済み sha を var/sharepoint_mirror.json に記録し差分のみ転送、失敗時は状態を
  進めず次回追いつく。git フック(post-commit/pre-push — `tc hooks install`)が自動実行する。

サブコマンド:
  python scripts/sharepoint.py root                 workspace の絶対パスを出力
  python scripts/sharepoint.py status               設定・enabled・root を表示(ネットワーク不使用)
  python scripts/sharepoint.py test                 認証 + site/drive 解決まで検証
  python scripts/sharepoint.py sync                 双方向同期(全フォルダ。シナリオ開始/終了時に実行)
  python scripts/sharepoint.py mirror [--full]      docs/管理表を git main から一方向ミラー(ADR-0010)
  python scripts/sharepoint.py pull [name ...]      遠隔 → ローカル(選択的リカバリ用。既定: input)
  python scripts/sharepoint.py push [name ...]      ローカル → 遠隔(選択的リカバリ用)
  python scripts/sharepoint.py info <localpath>     ローカルパスに対応する SharePoint URL を出力

name は folders マップのキー(council / input / media-output / reviews / deliberations /
brainstorms / persona-tests)。

設定(sharepoint.config.json、非機密・追跡。**プロジェクトごとのレイアウト**はここで持つ):
  enabled / site_url / drive / root(遠隔基点フォルダ。per-project)/ folders(ローカル名 ↔ 遠隔名)
シークレット・接続(環境変数 → ルート共有 .env → .claude/settings.local.json、bridge_common と同じ解決):
  SHAREPOINT_TENANT_ID / SHAREPOINT_CLIENT_ID / SHAREPOINT_CLIENT_SECRET
  (任意)SHAREPOINT_SITE_URL / SHAREPOINT_DRIVE / SHAREPOINT_ENABLED で接続を上書き(全プロジェクト共通)。
  root は per-project config を優先(ADR-0011)。旧 MAGI_SHAREPOINT_* は非推奨エイリアス(後方互換)。
Azure 側: アプリ登録 + アプリケーション許可 Sites.ReadWrite.All に管理者同意が必要。

依存: 標準ライブラリのみ(HTTP は bridge_common 経由で urllib)。
"""
import argparse
import json
import os
import subprocess
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
# git 操作・差分の基点はリポジトリルート(shared/ の親 — ADR-0011)。
_PROTO = os.path.normpath(os.path.join(_HERE, os.pardir))

# config / workspace / var / mirror 状態の基点 = プロジェクト dir(per-project 化 — ADR-0011)。
# 既定は cwd(プロジェクト dir から実行する想定)。--project で明示上書きできる。
_PROJECT_DIR = os.getcwd()


def set_project(path):
    """config/workspace/var を解決する基点プロジェクト dir を設定する。"""
    global _PROJECT_DIR
    _PROJECT_DIR = os.path.abspath(path)


def project_dir():
    return _PROJECT_DIR


def config_path():
    return os.path.join(_PROJECT_DIR, "sharepoint.config.json")


# --------------------------------------------------------------------------- #
# 設定 / root 解決
# --------------------------------------------------------------------------- #
def load_config():
    cfg_path = config_path()
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"error: 設定が見つかりません: {cfg_path}")
    except ValueError as e:
        raise SystemExit(f"error: sharepoint.config.json が不正な JSON です: {e}")
    cfg.setdefault("enabled", False)
    cfg.setdefault("drive", "Documents")
    cfg.setdefault("root", "")
    cfg.setdefault("folders", {})
    # 接続設定(全プロジェクト共通)は env(→ settings.local.json)で上書きできる。
    # オンオフ・接続先を Git 追跡外に置けるようにするため。site/drive/enabled は同一テナント・
    # 同一サイトなので共有 .env に置いてよい。
    env_enabled = bc.setting("SHAREPOINT_ENABLED")
    if env_enabled is not None:
        cfg["enabled"] = _parse_bool(env_enabled)
    else:
        cfg["enabled"] = bool(cfg.get("enabled", False))
    cfg["site_url"] = bc.setting("SHAREPOINT_SITE_URL") or cfg.get("site_url", "")
    cfg["drive"] = bc.setting("SHAREPOINT_DRIVE") or cfg["drive"]
    # root(遠隔の基点フォルダ)は**プロジェクトごとのレイアウト**なので config を優先する
    # (例: Magi/Workspace と TradeCouncil/Workspace を分離 — ADR-0011)。env は config 未設定時の
    # フォールバックに留める。共有 .env に1つの SHAREPOINT_ROOT を置いても各プロジェクトの
    # config 値が勝つので、同期先が衝突しない。
    cfg["root"] = cfg.get("root") or bc.setting("SHAREPOINT_ROOT") or ""
    return cfg


def _parse_bool(v):
    """env の真偽表現を bool に。1/true/yes/on(大小無視)を真、それ以外を偽とする。"""
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def active_root_name(cfg):
    # 常に workspace(ADR-0009)。enabled は同期通信の有無のみを制御する
    return "workspace"


def active_root_path(cfg):
    return os.path.join(_PROJECT_DIR, active_root_name(cfg))


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
# 同期計画(純関数 — tests/scripts/test_sharepoint_sync.py で検査)
# --------------------------------------------------------------------------- #
SYNC_SKEW_SEC = 2.0  # SharePoint のタイムスタンプは秒精度 → この差以内は同一とみなす


def _should_sync(rel):
    """同期対象か。rel は workspace 基準の相対パス(/'区切り)。"""
    base = rel.rsplit("/", 1)[-1]
    if base == ".gitkeep":
        return False
    if rel == "README.md":  # workspace 直下の README のみ除外(成果物の README は対象)
        return False
    if base.endswith(".tmp"):
        return False
    return True


def plan_sync(local_index, remote_index, skew_sec=SYNC_SKEW_SEC):
    """相対パス→更新時刻(epoch秒)の索引2つから同期アクションを決める。

    返り値: [(rel, action)] — action は push / pull / skip。
    追加型(削除は伝播しない): 片側にしか無い = コピー対象。
    """
    actions = []
    for rel in sorted(set(local_index) | set(remote_index)):
        if not _should_sync(rel):
            continue
        lt = local_index.get(rel)
        rt = remote_index.get(rel)
        if rt is None:
            actions.append((rel, "push"))
        elif lt is None:
            actions.append((rel, "pull"))
        elif abs(lt - rt) <= skew_sec:
            actions.append((rel, "skip"))
        elif lt > rt:
            actions.append((rel, "push"))
        else:
            actions.append((rel, "pull"))
    return actions


# --------------------------------------------------------------------------- #
# 認証 / Graph 呼び出し
# --------------------------------------------------------------------------- #
def get_token(cfg):
    tenant = bc.setting("SHAREPOINT_TENANT_ID")
    client_id = bc.setting("SHAREPOINT_CLIENT_ID")
    secret = bc.setting("SHAREPOINT_CLIENT_SECRET")
    missing = [
        n
        for n, v in (
            ("SHAREPOINT_TENANT_ID", tenant),
            ("SHAREPOINT_CLIENT_ID", client_id),
            ("SHAREPOINT_CLIENT_SECRET", secret),
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
            "SHAREPOINT_SITE_URL に SharePoint サイト URL を設定してください。"
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
# 双方向同期(sync)
# --------------------------------------------------------------------------- #
def _parse_graph_ts(value):
    """Graph の lastModifiedDateTime(ISO 8601 / Z)→ epoch 秒。不明は 0.0。"""
    if not value:
        return 0.0
    from datetime import datetime

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _local_index(base):
    """base 配下を walk して {相対パス('/'区切り): mtime epoch秒}。未存在は {}。"""
    index = {}
    if not os.path.isdir(base):
        return index
    for dirpath, _dirs, files in os.walk(base):
        for fn in files:
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, base).replace(os.sep, "/")
            index[rel] = os.path.getmtime(path)
    return index


def _remote_index(drive_id, remote_path, token, prefix=""):
    """遠隔 remote_path 配下を再帰列挙 → {相対パス: (mtime epoch秒, driveItem)}。"""
    index = {}
    for item in _list_children(drive_id, remote_path, token):
        name = item["name"]
        rel = f"{prefix}{name}"
        child_remote = f"{remote_path}/{name}" if remote_path else name
        if item.get("folder"):
            index.update(
                _remote_index(drive_id, child_remote, token, prefix=rel + "/")
            )
        else:
            index[rel] = (_parse_graph_ts(item.get("lastModifiedDateTime")), item)
    return index


def _fetch_item(drive_id, remote_file, token):
    return graph_json(
        "GET", f"/drives/{drive_id}/root:/{urllib.parse.quote(remote_file)}", token
    )


def _align_local_mtime(local_path, remote_ts):
    """ローカル mtime を遠隔の更新時刻に合わせる(次回 sync が skip になる)。"""
    if remote_ts > 0:
        os.utime(local_path, (remote_ts, remote_ts))


def _sync_push_file(drive_id, local_path, remote_file, token):
    parent = remote_file.rsplit("/", 1)[0] if "/" in remote_file else ""
    _ensure_remote_path(drive_id, parent, token)
    size = os.path.getsize(local_path)
    if size < UPLOAD_CHUNK:
        with open(local_path, "rb") as f:
            _upload_small(drive_id, remote_file, f.read(), token)
    else:
        _upload_large(drive_id, remote_file, local_path, size, token)
    # アップロード後の遠隔タイムスタンプをローカルへ反映(ピンポン防止)
    item = _fetch_item(drive_id, remote_file, token)
    _align_local_mtime(local_path, _parse_graph_ts(item.get("lastModifiedDateTime")))
    sys.stderr.write(f"  push: {remote_file} ({size} bytes)\n")


def _sync_pull_file(drive_id, item, remote_file, local_path, token):
    dl = None
    if item:
        dl = item.get("@microsoft.graph.downloadUrl") or item.get("@content.downloadUrl")
    if not dl:
        dl = f"/drives/{drive_id}/root:/{urllib.parse.quote(remote_file)}:/content"
    hdr = {} if dl.startswith("http") else _auth_headers(token)
    url = dl if dl.startswith("http") else GRAPH + dl
    try:
        _, content = bc.http_raw("GET", url, hdr, None, provider=PROVIDER)
    except bc.ProviderHTTPError as e:
        raise SystemExit(bc.fmt_http_error(PROVIDER, e))
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "wb") as f:
        f.write(content)
    ts = _parse_graph_ts((item or {}).get("lastModifiedDateTime"))
    _align_local_mtime(local_path, ts)
    sys.stderr.write(f"  pull: {remote_file} ({len(content)} bytes)\n")


def cmd_sync(cfg, _args):
    """全フォルダの双方向同期(追加型・newer-wins)。シナリオ開始/終了時に実行する。"""
    _require_enabled(cfg)
    token = get_token(cfg)
    site_id = resolve_site(cfg, token)
    drive_id = resolve_drive(cfg, token, site_id)

    local_index = {}
    remote_times = {}
    remote_items = {}
    for name in cfg["folders"]:
        base = local_dir(cfg, name)
        for rel, mtime in _local_index(base).items():
            local_index[f"{name}/{rel}"] = mtime
        for rel, (mtime, item) in _remote_index(
            drive_id, remote_dir(cfg, name), token
        ).items():
            remote_times[f"{name}/{rel}"] = mtime
            remote_items[f"{name}/{rel}"] = item

    pushed = pulled = skipped = 0
    for rel, action in plan_sync(local_index, remote_times):
        if action == "skip":
            skipped += 1
            continue
        name, sub = rel.split("/", 1)
        local_path = os.path.join(local_dir(cfg, name), sub.replace("/", os.sep))
        rd = remote_dir(cfg, name)
        remote_file = f"{rd}/{sub}" if rd else sub
        if action == "push":
            _sync_push_file(drive_id, local_path, remote_file, token)
            pushed += 1
        else:
            _sync_pull_file(drive_id, remote_items.get(rel), remote_file, local_path, token)
            pulled += 1
    print(f"sync 完了: push {pushed} / pull {pulled} / skip {skipped}")


# --------------------------------------------------------------------------- #
# docs ミラー(git main → SharePoint 一方向・削除反映 — ADR-0010)
# --------------------------------------------------------------------------- #
DEFAULT_GIT_MIRROR = {
    "branch": "main",
    "remote": "Docs",
    "paths": ["docs"],
    "files": [
        "README.md",
        "DOCS.md",
        "REQUIREMENTS.md",
        "FEATURES.md",
        "TESTCASES.md",
        "BACKLOG.md",
        "DEVELOPMENT.md",
    ],
}


def mirror_config(cfg):
    """config の git_mirror 節を既定値とマージして返す。"""
    mcfg = dict(DEFAULT_GIT_MIRROR)
    mcfg.update(cfg.get("git_mirror") or {})
    return mcfg


def mirror_target(rel, mcfg):
    """rel(リポジトリ相対・'/'区切り)がミラー対象か。paths は階層一致、files は完全一致。"""
    rel = rel.replace("\\", "/")
    if rel in mcfg["files"]:
        return True
    return any(rel.startswith(p.rstrip("/") + "/") for p in mcfg["paths"])


def plan_mirror(diff_entries, mcfg):
    """git diff --name-status の項目列 → ミラーアクション列(純関数)。

    diff_entries: [(status, path)] または [(status, old, new)](R/C)。
    返り値: [(action, rel)] — action は push / delete。
    一方向ミラーのため **D(削除)は遠隔削除に変換する**(workspace 双方向とは別方針)。
    """
    actions = []
    for entry in diff_entries:
        status = entry[0][:1]
        if status in ("R", "C"):
            old, new = entry[1], entry[2]
            if status == "R" and mirror_target(old, mcfg):
                actions.append(("delete", old))
            if mirror_target(new, mcfg):
                actions.append(("push", new))
        elif status == "D":
            if mirror_target(entry[1], mcfg):
                actions.append(("delete", entry[1]))
        elif status in ("A", "M", "T"):
            if mirror_target(entry[1], mcfg):
                actions.append(("push", entry[1]))
        # それ以外(U 等)は対象外
    return actions


def plan_full_mirror(tree_paths, remote_rels, mcfg):
    """全量ミラー計画(初回 / --full)。木の対象を全 push + 木に無い遠隔を削除(prune)。"""
    targets = [p for p in tree_paths if mirror_target(p, mcfg)]
    target_set = set(targets)
    actions = [("push", p) for p in targets]
    actions.extend(("delete", r) for r in sorted(remote_rels) if r not in target_set)
    return actions


def mirror_state_path():
    """前回ミラー済み sha の記録先(プロジェクト dir の var/ 配下。TC_VAR_DIR を尊重 — ADR-0004)。"""
    var_dir = os.environ.get("TC_VAR_DIR", "var")
    if not os.path.isabs(var_dir):
        var_dir = os.path.join(_PROJECT_DIR, var_dir)
    return os.path.join(var_dir, "sharepoint_mirror.json")


def load_mirror_state(path):
    """状態を読む。未存在・破損・commit 欠落は None(= 初回扱い)。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (FileNotFoundError, ValueError):
        return None
    if not isinstance(state, dict) or not state.get("commit"):
        return None
    return state


def save_mirror_state(path, branch, commit):
    path = os.fspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"branch": branch, "commit": commit}, f, ensure_ascii=False, indent=2)


def _git(*args):
    """git をプロジェクトルートで実行し stdout(str)を返す。失敗は RuntimeError。"""
    out = subprocess.run(["git", *args], cwd=_PROTO, capture_output=True)
    if out.returncode != 0:
        detail = out.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return out.stdout.decode("utf-8", errors="replace")


def _git_blob(sha, rel):
    """コミット sha 中のファイル内容(bytes)。作業ツリーは読まない。"""
    out = subprocess.run(["git", "show", f"{sha}:{rel}"], cwd=_PROTO, capture_output=True)
    if out.returncode != 0:
        detail = out.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git show {sha}:{rel} failed: {detail}")
    return out.stdout


def _git_diff_entries(old_sha, new_sha):
    """name-status diff を -z で安全にパース(日本語パスのクォート回避)。"""
    raw = _git("diff", "--name-status", "-z", old_sha, new_sha)
    tokens = raw.split("\0")
    entries = []
    i = 0
    while i < len(tokens):
        status = tokens[i]
        if not status:
            i += 1
            continue
        if status[:1] in ("R", "C"):
            entries.append((status, tokens[i + 1], tokens[i + 2]))
            i += 3
        else:
            entries.append((status, tokens[i + 1]))
            i += 2
    return entries


def _git_tree_paths(sha):
    raw = _git("ls-tree", "-r", "--name-only", "-z", sha)
    return [p for p in raw.split("\0") if p]


def _mirror_push_bytes(drive_id, remote_file, data, token):
    """メモリ上の blob を遠隔へアップロード(4MB 未満は単純 PUT、以上はセッション分割)。"""
    parent = remote_file.rsplit("/", 1)[0] if "/" in remote_file else ""
    _ensure_remote_path(drive_id, parent, token)
    size = len(data)
    if size < UPLOAD_CHUNK:
        _upload_small(drive_id, remote_file, data, token)
    else:
        enc = urllib.parse.quote(remote_file)
        sess = graph_json(
            "POST",
            f"/drives/{drive_id}/root:/{enc}:/createUploadSession",
            token,
            {"item": {"@microsoft.graph.conflictBehavior": "replace"}},
        )
        upload_url = sess["uploadUrl"]
        for start in range(0, size, UPLOAD_CHUNK):
            chunk = data[start : start + UPLOAD_CHUNK]
            headers = {
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {start}-{start + len(chunk) - 1}/{size}",
            }
            try:
                bc.http_json("PUT", upload_url, headers, chunk, provider=PROVIDER)
            except bc.ProviderHTTPError as e:
                raise SystemExit(bc.fmt_http_error(PROVIDER + " (upload)", e))
    sys.stderr.write(f"  push: {remote_file} ({size} bytes)\n")


def _delete_remote(drive_id, remote_file, token):
    """遠隔ファイルを削除(冪等 — 404 は「すでに無い」として成功扱い)。"""
    url = f"{GRAPH}/drives/{drive_id}/root:/{urllib.parse.quote(remote_file)}"
    try:
        bc.http_raw("DELETE", url, _auth_headers(token), None, provider=PROVIDER)
    except bc.ProviderHTTPError as e:
        if e.code == 404:
            sys.stderr.write(f"  delete: {remote_file}(すでに無し)\n")
            return
        raise SystemExit(bc.fmt_http_error(PROVIDER, e))
    sys.stderr.write(f"  delete: {remote_file}\n")


def cmd_mirror(cfg, args):
    """docs/管理表を git <branch> から SharePoint <remote>/ へ一方向ミラー(ADR-0010)。"""
    _require_enabled(cfg)
    mcfg = mirror_config(cfg)
    branch = mcfg["branch"]
    try:
        sha = _git("rev-parse", branch).strip()
    except RuntimeError as e:
        raise SystemExit(f"error: ブランチ {branch} を解決できません: {e}")

    state_path = mirror_state_path()
    state = load_mirror_state(state_path)
    full = bool(getattr(args, "full", False))
    if not full and state and state.get("branch") == branch and state.get("commit") == sha:
        print(f"mirror: up to date({branch} @ {sha[:12]})")
        return

    actions = None
    if not full and state and state.get("branch") == branch:
        try:
            actions = plan_mirror(_git_diff_entries(state["commit"], sha), mcfg)
        except RuntimeError as e:
            sys.stderr.write(f"warn: 前回 sha からの diff に失敗 → 全量ミラーに切替: {e}\n")
    if actions is not None and not actions:
        # 対象外の変更のみ(コード等)。通信せず状態だけ進める
        save_mirror_state(state_path, branch, sha)
        print(f"mirror: 対象差分なし({branch} @ {sha[:12]})")
        return

    token = get_token(cfg)
    site_id = resolve_site(cfg, token)
    drive_id = resolve_drive(cfg, token, site_id)
    if actions is None:  # 初回 / --full / diff 不能: 全 push + 遠隔余剰の prune
        remote_rels = list(_remote_index(drive_id, mcfg["remote"], token))
        actions = plan_full_mirror(_git_tree_paths(sha), remote_rels, mcfg)

    pushed = deleted = 0
    for action, rel in actions:
        remote_file = f"{mcfg['remote']}/{rel}"
        if action == "push":
            _mirror_push_bytes(drive_id, remote_file, _git_blob(sha, rel), token)
            pushed += 1
        else:
            _delete_remote(drive_id, remote_file, token)
            deleted += 1
    # 全アクション成功時のみ状態を進める(途中失敗は次回 diff で自動的に追いつく)
    save_mirror_state(state_path, branch, sha)
    print(f"mirror 完了: push {pushed} / delete {deleted}({branch} @ {sha[:12]})")


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
        print("\n注: enabled=false。sync/pull/push は SharePoint と通信しません(workspace/ は純ローカル)。")


def _require_enabled(cfg):
    if not cfg.get("enabled"):
        sys.stderr.write(
            "SharePoint 無効(enabled=false)。sync/pull/push/mirror は何もしません。"
            "workspace/ をそのまま使ってください。\n"
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
    "sync": cmd_sync,
    "mirror": cmd_mirror,
    "pull": cmd_pull,
    "push": cmd_push,
    "info": cmd_info,
}


def main():
    # --project を全サブコマンドで「前後どちらにも」置けるよう共通親に持たせる(ADR-0011)。
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--project",
        default=None,
        help="config/workspace/var の基点プロジェクト dir(既定: カレント)。ADR-0011",
    )
    p = argparse.ArgumentParser(
        description="MAGI の入出力を SharePoint と同期するブリッジ", parents=[common]
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("root", parents=[common], help="workspace の絶対パスを出力")
    sub.add_parser("status", parents=[common], help="設定・enabled・root を表示(通信なし)")
    sub.add_parser("test", parents=[common], help="認証 + site/drive 解決を検証")
    sub.add_parser("sync", parents=[common], help="双方向同期(全フォルダ・追加型・newer-wins。ADR-0009)")
    pm = sub.add_parser(
        "mirror", parents=[common],
        help="docs/管理表を git main から Docs/ へ一方向ミラー(削除反映。ADR-0010)",
    )
    pm.add_argument(
        "--full", action="store_true", help="全ファイル push + 遠隔余剰の削除(prune・修復用)"
    )
    pp = sub.add_parser("pull", parents=[common], help="遠隔 → ローカル(選択的リカバリ用。既定: input)")
    pp.add_argument("names", nargs="*", help="folders キー(既定: input)")
    pu = sub.add_parser("push", parents=[common], help="ローカル → 遠隔(既定: reviews deliberations brainstorms persona-tests media-output)")
    pu.add_argument("names", nargs="*", help="folders キー(既定: reviews deliberations brainstorms persona-tests media-output)")
    pi = sub.add_parser("info", parents=[common], help="ローカルミラーパスに対応する SharePoint URL を出力")
    pi.add_argument("path", help="アクティブ root 下のローカルパス")
    args = p.parse_args()
    if args.project:
        set_project(args.project)
    cfg = load_config()
    COMMANDS[args.cmd](cfg, args)


if __name__ == "__main__":
    main()
