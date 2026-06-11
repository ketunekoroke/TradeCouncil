"""DB の整合スナップショット(ADR-0005)。

SQLite の `VACUUM INTO` で、WAL 稼働中でも整合性のある読取専用コピーを作る。
生 DB ファイルを共有フォルダ越しにコピーする破損リスクを避けるための正規手段。
バックアップ兼用。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def snapshot_db(dest: Path, *, source: Path) -> Path:
    """source の DB を dest へ整合性を保ってスナップショットする。

    VACUUM INTO はコミット済みデータ(未チェックポイントの WAL を含む)を反映した
    単一ファイルを生成する。元 DB は変更しない。

    dest は新規パスでなければならない(既存ならエラー)。親ディレクトリは作成する。
    """
    if dest.exists():
        raise FileExistsError(f"スナップショット先が既に存在します: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(str(source))
    try:
        # VACUUM INTO はパラメータバインドに対応(SQLite 3.27+)。
        con.execute("VACUUM INTO ?", (str(dest),))
    finally:
        con.close()
    return dest
