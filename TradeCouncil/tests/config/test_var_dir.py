"""TC_VAR_DIR サンドボックス(実行時生成物の差し替え)のテスト(ADR-0004)。

仕様: system.yaml の `var/` 接頭辞パス(DB・KILL・ログ)のみを TC_VAR_DIR 配下へ
読み替える。未設定・空なら完全に従来挙動。config/ 系パスは影響を受けない。
環境変数はプロパティ評価時に動的に読む(lru_cache に焼き込まれない)。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.config import PROJECT_ROOT, SystemConfig


def test_default_paths_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TC_VAR_DIR", raising=False)
    cfg = SystemConfig()
    assert cfg.db_path == PROJECT_ROOT / "var" / "tradecouncil.db"
    assert cfg.kill_flag_path == PROJECT_ROOT / "var" / "run" / "KILL"
    assert cfg.log_dir_path == PROJECT_ROOT / "var" / "logs"


def test_empty_env_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TC_VAR_DIR", "   ")
    cfg = SystemConfig()
    assert cfg.db_path == PROJECT_ROOT / "var" / "tradecouncil.db"


def test_absolute_var_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TC_VAR_DIR", str(tmp_path))
    cfg = SystemConfig()
    assert cfg.db_path == tmp_path / "tradecouncil.db"
    assert cfg.kill_flag_path == tmp_path / "run" / "KILL"  # サブ構造維持
    assert cfg.log_dir_path == tmp_path / "logs"


def test_relative_var_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TC_VAR_DIR", "var-sandbox")
    cfg = SystemConfig()
    assert cfg.db_path == PROJECT_ROOT / "var-sandbox" / "tradecouncil.db"
    assert cfg.kill_flag_path == PROJECT_ROOT / "var-sandbox" / "run" / "KILL"


def test_non_var_paths_unaffected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TC_VAR_DIR", str(tmp_path))
    cfg = SystemConfig()
    assert cfg.policies_dir == PROJECT_ROOT / "config" / "policies"
    assert cfg.generated_dir == PROJECT_ROOT / "config" / "generated"
    assert cfg.instruments_dir == PROJECT_ROOT / "config" / "instruments"
    assert cfg.bots_dir == PROJECT_ROOT / "config" / "bots"


def test_yaml_path_outside_var_unaffected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TC_VAR_DIR", str(tmp_path))
    cfg = SystemConfig(db={"path": "data/x.db"})
    assert cfg.db_path == PROJECT_ROOT / "data" / "x.db"


def test_ensure_runtime_dirs_creates_sandbox_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sandbox = tmp_path / "sb"
    monkeypatch.setenv("TC_VAR_DIR", str(sandbox))
    SystemConfig().ensure_runtime_dirs()
    assert (sandbox / "run").is_dir()
    assert (sandbox / "logs").is_dir()


def test_env_is_read_dynamically_not_baked_into_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """lru_cache 済みインスタンスでも、env 変更後のプロパティ評価は新パスを返す。"""
    monkeypatch.delenv("TC_VAR_DIR", raising=False)
    cfg = SystemConfig()
    assert cfg.db_path == PROJECT_ROOT / "var" / "tradecouncil.db"
    monkeypatch.setenv("TC_VAR_DIR", str(tmp_path))
    assert cfg.db_path == tmp_path / "tradecouncil.db"
