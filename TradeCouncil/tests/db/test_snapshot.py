"""tc snapshot(DB 整合スナップショット)のテスト(ADR-0005)。

VACUUM INTO で WAL 稼働中でも整合性のある読取専用コピーを作る。
元 DB は無傷、コミット済みデータは全て含まれる。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.db.snapshot import snapshot_db


def _make_db(path: Path, *, wal: bool = False) -> None:
    con = sqlite3.connect(str(path))
    try:
        if wal:
            con.execute("PRAGMA journal_mode=WAL")
        con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        con.executemany("INSERT INTO t (name) VALUES (?)", [("a",), ("b",), ("c",)])
        con.commit()
    finally:
        con.close()


def _rows(path: Path) -> list[tuple]:
    con = sqlite3.connect(str(path))
    try:
        return con.execute("SELECT id, name FROM t ORDER BY id").fetchall()
    finally:
        con.close()


def test_snapshot_copies_all_rows(tmp_path: Path) -> None:
    src = tmp_path / "src.db"
    dest = tmp_path / "snap.db"
    _make_db(src)
    result = snapshot_db(dest, source=src)
    assert result == dest
    assert dest.exists()
    assert _rows(dest) == [(1, "a"), (2, "b"), (3, "c")]


def test_source_unchanged_after_snapshot(tmp_path: Path) -> None:
    src = tmp_path / "src.db"
    _make_db(src)
    before = _rows(src)
    snapshot_db(tmp_path / "snap.db", source=src)
    assert src.exists()
    assert _rows(src) == before


def test_snapshot_fails_if_dest_exists(tmp_path: Path) -> None:
    src = tmp_path / "src.db"
    dest = tmp_path / "snap.db"
    _make_db(src)
    dest.write_text("occupied", encoding="utf-8")
    with pytest.raises(FileExistsError):
        snapshot_db(dest, source=src)


def test_snapshot_creates_parent_dir(tmp_path: Path) -> None:
    src = tmp_path / "src.db"
    dest = tmp_path / "nested" / "deeper" / "snap.db"
    _make_db(src)
    snapshot_db(dest, source=src)
    assert dest.exists()


def test_snapshot_includes_committed_wal_data(tmp_path: Path) -> None:
    """WAL モードで未チェックポイントのコミット済みデータも含まれる。"""
    src = tmp_path / "src.db"
    _make_db(src, wal=True)
    # WAL に追記(チェックポイントせずコミットのみ)
    con = sqlite3.connect(str(src))
    try:
        con.execute("INSERT INTO t (name) VALUES ('d')")
        con.commit()
    finally:
        con.close()
    dest = tmp_path / "snap.db"
    snapshot_db(dest, source=src)
    names = [r[1] for r in _rows(dest)]
    assert names == ["a", "b", "c", "d"]
