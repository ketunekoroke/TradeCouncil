"""tc bot new スキャフォールド(scripts/scaffold_bot.py)のテスト。

設計(ADR-0007 §3〜4):
  - 4ファイル(戦略 .py / config YAML / テスト雛形 / 戦略カード)を一括生成
  - 既存ファイルがあれば FileExistsError で「何も書かずに」拒否(部分生成しない)
  - カードは docs/strategies/_template.md から生成(テンプレート二重持ちしない)
  - STRATEGIES レジストリは自動編集しない(生成テスト雛形の登録検査で誘導)
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from bots.base import Strategy
from scripts.scaffold_bot import scaffold_bot

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    """実プロジェクトのカードテンプレートだけを持つ空のプロジェクトルート。"""
    strategies = tmp_path / "docs" / "strategies"
    strategies.mkdir(parents=True)
    shutil.copy(
        PROJECT_ROOT / "docs" / "strategies" / "_template.md",
        strategies / "_template.md",
    )
    return tmp_path


class TestScaffoldGeneration:
    def test_generates_four_files(self, tmp_root: Path) -> None:
        created = scaffold_bot("ma_cross_btc", "ma_cross", root=tmp_root)

        expected = {
            tmp_root / "bots" / "ma_cross.py",
            tmp_root / "config" / "bots" / "ma_cross_btc.yaml",
            tmp_root / "tests" / "bots" / "test_ma_cross.py",
            tmp_root / "docs" / "strategies" / "ma_cross.md",
        }
        assert set(created) == expected
        for path in expected:
            assert path.exists(), f"未生成: {path}"
            text = path.read_text(encoding="utf-8")
            assert "ma_cross" in text

    def test_generated_python_compiles_and_subclasses_strategy(self, tmp_root: Path) -> None:
        scaffold_bot("ma_cross_btc", "ma_cross", root=tmp_root)
        source = (tmp_root / "bots" / "ma_cross.py").read_text(encoding="utf-8")

        namespace: dict = {}
        exec(compile(source, "ma_cross.py", "exec"), namespace)  # noqa: S102 — 生成物の検査
        cls = namespace["MaCross"]
        assert issubclass(cls, Strategy)
        # bots/ の権限分離(原則2)を雛形が破っていない(注意書きの言及は許容し、
        # 実際の import 文のみ禁止 — 実ファイルは tests/risk の性質テストでも検査される)
        for module in ("core.exchange", "core.execution"):
            assert f"from {module}" not in source
            assert f"import {module}" not in source

    def test_generated_yaml_is_valid_and_disabled(self, tmp_root: Path) -> None:
        scaffold_bot("ma_cross_btc", "ma_cross", root=tmp_root)
        data = yaml.safe_load(
            (tmp_root / "config" / "bots" / "ma_cross_btc.yaml").read_text(encoding="utf-8")
        )
        assert data["bot_id"] == "ma_cross_btc"
        assert data["strategy"] == "ma_cross"
        assert data["enabled"] is False  # 意図せず走らせない(fail-closed)
        assert "instrument_id" in data
        assert isinstance(data["params"], dict)

    def test_generated_test_checks_registry(self, tmp_root: Path) -> None:
        """生成されたテスト雛形がレジストリ登録検査を含む(生成直後 red で登録を誘導)。"""
        scaffold_bot("ma_cross_btc", "ma_cross", root=tmp_root)
        text = (tmp_root / "tests" / "bots" / "test_ma_cross.py").read_text(encoding="utf-8")
        assert "STRATEGIES" in text
        assert '"ma_cross"' in text
        compile(text, "test_ma_cross.py", "exec")  # 雛形自体が構文エラーでない

    def test_generated_card_has_frontmatter(self, tmp_root: Path) -> None:
        scaffold_bot("ma_cross_btc", "ma_cross", root=tmp_root)
        text = (tmp_root / "docs" / "strategies" / "ma_cross.md").read_text(encoding="utf-8")
        assert text.startswith("---")
        assert "strategy_key: ma_cross" in text
        assert "status: draft" in text
        assert "bot_ids: [ma_cross_btc]" in text
        # プレースホルダの埋め残しがない
        for placeholder in ("{strategy_key}", "{bot_id}", "{date}"):
            assert placeholder not in text


class TestScaffoldFailClosed:
    def test_refuses_existing_file_and_writes_nothing(self, tmp_root: Path) -> None:
        """1ファイルでも既存なら拒否し、部分生成しない。"""
        conflict = tmp_root / "config" / "bots" / "ma_cross_btc.yaml"
        conflict.parent.mkdir(parents=True)
        conflict.write_text("# 既存設定\n", encoding="utf-8")

        with pytest.raises(FileExistsError):
            scaffold_bot("ma_cross_btc", "ma_cross", root=tmp_root)

        assert conflict.read_text(encoding="utf-8") == "# 既存設定\n"  # 上書きされない
        assert not (tmp_root / "bots" / "ma_cross.py").exists()
        assert not (tmp_root / "tests" / "bots" / "test_ma_cross.py").exists()
        assert not (tmp_root / "docs" / "strategies" / "ma_cross.md").exists()

    @pytest.mark.parametrize(
        "bot_id, strategy_key",
        [
            ("bad-id", "ma_cross"),       # ハイフン
            ("ma_cross_btc", "a/b"),      # パス区切り
            ("1abc", "ma_cross"),         # 数字始まり
            ("ma_cross_btc", ""),         # 空
            ("MA_CROSS", "ma_cross"),     # 大文字(モジュール名規約違反)
        ],
    )
    def test_rejects_invalid_ids(self, tmp_root: Path, bot_id: str, strategy_key: str) -> None:
        with pytest.raises(ValueError):
            scaffold_bot(bot_id, strategy_key, root=tmp_root)
        assert not (tmp_root / "bots").exists()  # 何も作られない

    def test_missing_template_is_clear_error(self, tmp_path: Path) -> None:
        """カードテンプレートが無いルートでは明確なエラー(暗黙のフォールバックをしない)。"""
        with pytest.raises(FileNotFoundError):
            scaffold_bot("ma_cross_btc", "ma_cross", root=tmp_path)
