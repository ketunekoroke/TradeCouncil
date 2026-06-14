"""MoneyForward トークンの永続化(zero-dep)。プロダクト別の JSON を gitignore の var/ 配下に保存。

保存先: `MONEYFORWARD_TOKEN_DIR`(env)→ なければ `PROJECT_ROOT/var/moneyforward`(TradeCouncil の
`TC_VAR_DIR`/`var/` 規約に倣う)。`var/` はリポジトリ `.gitignore` で追跡外。

**秘匿情報(access/refresh token)を含む**。git にコミットしない・ログに値を残さない・POSIX では 0600 に
する(Windows では概ね無効 → `var/` の gitignore とユーザープロファイル ACL に依存)。
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from core.config import PROJECT_ROOT, get_setting
from core.oauth import TokenBundle

_DEFAULT_DIR = PROJECT_ROOT / "var" / "moneyforward"


def token_dir() -> Path:
    """トークン保存ディレクトリ。`MONEYFORWARD_TOKEN_DIR`(絶対 or PROJECT_ROOT 相対)で上書き可。"""
    override = get_setting("MONEYFORWARD_TOKEN_DIR")
    if override:
        p = Path(override)
        return p if p.is_absolute() else (PROJECT_ROOT / p)
    return _DEFAULT_DIR


def token_path(product: str) -> Path:
    return token_dir() / f"moneyforward.{product}.json"


def save(product: str, bundle: TokenBundle) -> Path:
    """トークンを原子的に書き込む(tmp → os.replace)。POSIX は best-effort で 0600。"""
    directory = token_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = token_path(product)
    tmp = path.parent / (path.name + ".tmp")
    tmp.write_text(json.dumps(bundle.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600(Windows では概ね無効)
    except OSError:
        pass
    return path


def load(product: str) -> TokenBundle | None:
    """保存トークンを読む。欠落・破損は None(例外にしない)。"""
    path = token_path(product)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return TokenBundle.from_dict(data)
    except (ValueError, KeyError, TypeError, OSError):
        return None


def clear(product: str) -> bool:
    """保存トークンを削除する。存在しなければ False。"""
    path = token_path(product)
    if path.is_file():
        path.unlink()
        return True
    return False
