"""設定解決(zero-dep): 環境変数 → ルート共有 .env → .claude/settings.local.json の env。

TradeCouncil の `core/config.py` と同じく **ルート共有 `.env` を上方向探索で読む**(モノレポ — ADR-0011)。
ただし Accounting/core は **標準ライブラリのみ** に依存する方針(DEVELOPMENT.md)のため、dotenv/pydantic を
使わず自前で実装する。秘匿情報はここから読み、コード・コミットに書かない。
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

# 値の後ろのインラインコメント(空白 + #...)を検出する。クォートされていない値にのみ適用。
_INLINE_COMMENT = re.compile(r"\s+#")

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # Accounting/


def repo_root() -> Path:
    """`.git` を持つリポジトリルートを上方向探索する(共有 .venv/.env の在処)。"""
    for parent in (PROJECT_ROOT, *PROJECT_ROOT.parents):
        if (parent / ".git").exists():
            return parent
    return PROJECT_ROOT


def _parse_env_file(path: Path) -> dict[str, str]:
    """単純な KEY=VALUE 形式の .env を読む(コメント・空行・前後クォートを除去)。"""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, _, value = s.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]  # クォート内はそのまま(インラインコメントも除去しない)
        else:
            m = _INLINE_COMMENT.search(value)  # 値の後ろの " # コメント" を除去
            if m:
                value = value[: m.start()].rstrip()
        if key:
            out[key] = value
    return out


@lru_cache(maxsize=1)
def _root_env() -> dict[str, str]:
    return _parse_env_file(repo_root() / ".env")


@lru_cache(maxsize=1)
def _settings_local_env() -> dict[str, str]:
    """`.claude/settings.local.json` の `env`(後方互換の解決元)。"""
    path = PROJECT_ROOT / ".claude" / "settings.local.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    env = data.get("env")
    return {str(k): str(v) for k, v in env.items()} if isinstance(env, dict) else {}


def _is_placeholder(value: str) -> bool:
    """`<tenant>` / `REPLACE_ME` 等のテンプレ値を実値として採用しない。"""
    return ("REPLACE" in value) or ("<" in value)


def get_setting(*names: str) -> str | None:
    """名前を優先順に解決する。各名前について 環境変数 → ルート .env → settings.local.json を見る。

    空文字・プレースホルダはスキップして次の候補へ。`get_setting("A", "B")` は A を全ソースで探し、
    無ければ B を探す(名前の優先度がソースの優先度より上 — SharePoint の per-project 解決と同じ意図)。
    """
    sources = (os.environ, _root_env(), _settings_local_env())
    for name in names:
        for src in sources:
            value = src.get(name)
            if value and value.strip() and not _is_placeholder(value):
                return value.strip()
    return None


def clear_setting_cache() -> None:
    """テスト用: .env / settings.local の読み込みキャッシュを破棄する。"""
    _root_env.cache_clear()
    _settings_local_env.cache_clear()
