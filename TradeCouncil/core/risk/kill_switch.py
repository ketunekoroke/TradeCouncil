"""キルスイッチ(不変条項4: 利用者はいつでも全停止できる)。

フラグファイル方式: ファイルが存在すれば全BOTが停止する。
作成手段: `tc kill` / ファイルを手で置く(touch 相当)/ 将来は Discord コマンド。
解除(`tc resume`)は人間専用 — エージェント・自動化からは呼ばない。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path


def _default_path() -> Path:
    from core.config import get_config

    return get_config().kill_flag_path


def is_active(path: Path | None = None) -> bool:
    return (path or _default_path()).exists()


def activate(close_positions: bool = False, path: Path | None = None) -> Path:
    """キルフラグを作成する(冪等)。"""
    flag = path or _default_path()
    flag.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"activated_at: {datetime.now(UTC).isoformat()}"]
    if close_positions:
        lines.append("close_positions: true")
    flag.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return flag


def close_positions_requested(path: Path | None = None) -> bool:
    flag = path or _default_path()
    if not flag.exists():
        return False
    return "close_positions" in flag.read_text(encoding="utf-8")


def deactivate(path: Path | None = None) -> bool:
    """キルフラグを削除する。削除した場合 True(人間専用操作)。"""
    flag = path or _default_path()
    if flag.exists():
        flag.unlink()
        return True
    return False
