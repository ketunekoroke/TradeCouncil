"""CLI 出力の cp932(Windows 日本語コンソール)耐性のテスト(BL-018)。

Windows ではリダイレクト時・レガシーコンソールで stdout/stderr が ANSI
コードページ(日本語環境では cp932)+ errors="strict" で開かれる。
✓(U+2713)/✗(U+2717)等の cp932 非対応グリフを print すると
UnicodeEncodeError でプロセスごと落ちるため、CLI エントリポイントで
errors="replace" へ再構成する(エンコーディング自体は変えない)。
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

import pytest

from core.config import PROJECT_ROOT
from scripts.cli import configure_output_streams


def _cp932_strict(raw: io.BytesIO) -> io.TextIOWrapper:
    """cp932 コンソール相当の制限付きストリーム(非対応グリフで即例外)。"""
    return io.TextIOWrapper(raw, encoding="cp932", errors="strict")


class TestConfigureOutputStreams:
    def test_unencodable_glyphs_replaced_on_stdout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raw = io.BytesIO()
        monkeypatch.setattr(sys, "stdout", _cp932_strict(raw))
        configure_output_streams()
        print("P-01: ✗ 未決裁 → fail-closed(発注不可)")
        sys.stdout.flush()
        text = raw.getvalue().decode("cp932")
        # 非対応グリフのみ「?」へ置換され、日本語と cp932 対応記号(→)は無傷
        assert "P-01: ? 未決裁 → fail-closed(発注不可)" in text

    def test_unencodable_glyphs_replaced_on_stderr(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raw = io.BytesIO()
        monkeypatch.setattr(sys, "stderr", _cp932_strict(raw))
        configure_output_streams()
        print("✓ 完了", file=sys.stderr)
        sys.stderr.flush()
        assert "? 完了" in raw.getvalue().decode("cp932")

    def test_encoding_itself_is_preserved(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """encoding は変えない(リダイレクト先・パイプ消費側の期待を壊さない)。"""
        raw = io.BytesIO()
        stream = _cp932_strict(raw)
        monkeypatch.setattr(sys, "stdout", stream)
        configure_output_streams()
        assert stream.encoding == "cp932"

    def test_tolerates_streams_without_reconfigure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """StringIO 等 reconfigure を持たないストリームでも落ちない(組込・テスト環境)。"""
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        monkeypatch.setattr(sys, "stderr", io.StringIO())
        configure_output_streams()
        print("ok")
        assert out.getvalue() == "ok\n"


class TestStatusOnCp932Console:
    def test_status_survives_cp932_strict_streams(self, tmp_path: Path) -> None:
        """`tc status` が cp932 厳格ストリームでも完走する(BL-018 の再現条件)。

        PYTHONIOENCODING=cp932 で日本語 Windows のリダイレクト時既定
        (cp932 + strict)を環境非依存に再現する。TC_VAR_DIR で DB 等は隔離。
        """
        env = os.environ | {"PYTHONIOENCODING": "cp932", "TC_VAR_DIR": str(tmp_path)}
        proc = subprocess.run(
            [sys.executable, "-m", "scripts.cli", "status"],
            capture_output=True,
            cwd=PROJECT_ROOT,
            env=env,
            timeout=120,
        )
        stderr = proc.stderr.decode("cp932", errors="replace")
        assert proc.returncode == 0, f"tc status failed:\n{stderr}"
        assert "UnicodeEncodeError" not in stderr
        # 出力全体が cp932 として整合している(strict デコード可能)こと自体も検証
        stdout = proc.stdout.decode("cp932")
        assert "TradeCouncil status" in stdout
