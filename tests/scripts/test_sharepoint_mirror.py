"""docs ミラー(git main → SharePoint 一方向。ADR-0010)のテスト。

ネットワーク・git 不使用:
  - plan_mirror / plan_full_mirror は純関数(git diff/ls-tree の結果 → アクション列)
  - 状態ファイルは tmp_path で round-trip
  - hooks install は tmp_path の擬似リポジトリへ書き込んで検査
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import sharepoint as sp
from scripts.cli import install_hooks

MCFG = sp.mirror_config(
    {
        "git_mirror": {
            "branch": "main",
            "remote": "Docs",
            "paths": ["docs"],
            "files": ["README.md", "BACKLOG.md"],
        }
    }
)


class TestMirrorTarget:
    def test_paths_match_subtree_only(self) -> None:
        assert sp.mirror_target("docs/01_要件定義書.md", MCFG)
        assert sp.mirror_target("docs/adr/0010-docs-sharepoint-mirror.md", MCFG)
        assert not sp.mirror_target("docs2/evil.md", MCFG)  # 前方一致でなく階層一致
        assert not sp.mirror_target("core/config.py", MCFG)

    def test_files_match_exactly(self) -> None:
        assert sp.mirror_target("README.md", MCFG)
        assert not sp.mirror_target("pyproject.toml", MCFG)
        assert not sp.mirror_target("scenarios/README.md", MCFG)  # 完全一致のみ


class TestPlanMirror:
    def test_add_modify_typechange_are_pushed(self) -> None:
        actions = sp.plan_mirror(
            [("A", "docs/new.md"), ("M", "README.md"), ("T", "docs/x.md")], MCFG
        )
        assert actions == [
            ("push", "docs/new.md"),
            ("push", "README.md"),
            ("push", "docs/x.md"),
        ]

    def test_delete_is_propagated(self) -> None:
        """workspace 双方向(削除非伝播)と違い、ミラーは削除を反映する。"""
        actions = sp.plan_mirror([("D", "docs/old.md")], MCFG)
        assert actions == [("delete", "docs/old.md")]

    def test_rename_becomes_delete_plus_push(self) -> None:
        actions = sp.plan_mirror([("R100", "docs/old.md", "docs/new.md")], MCFG)
        assert actions == [("delete", "docs/old.md"), ("push", "docs/new.md")]

    def test_rename_out_of_scope_only_deletes(self) -> None:
        """対象内 → 対象外へのリネームは遠隔の旧ファイル削除のみ。"""
        actions = sp.plan_mirror([("R90", "docs/x.md", "core/x.md")], MCFG)
        assert actions == [("delete", "docs/x.md")]

    def test_copy_pushes_destination(self) -> None:
        actions = sp.plan_mirror([("C75", "docs/a.md", "docs/b.md")], MCFG)
        assert actions == [("push", "docs/b.md")]

    def test_non_targets_are_filtered(self) -> None:
        actions = sp.plan_mirror(
            [("M", "core/risk/guard.py"), ("A", "pyproject.toml")], MCFG
        )
        assert actions == []

    def test_empty_diff(self) -> None:
        assert sp.plan_mirror([], MCFG) == []


class TestPlanFullMirror:
    def test_full_pushes_targets_and_prunes_remote_extras(self) -> None:
        tree = ["docs/a.md", "docs/sub/b.md", "README.md", "core/skip.py"]
        remote = ["docs/a.md", "docs/stale.md", "manual-upload.txt"]
        actions = sp.plan_full_mirror(tree, remote, MCFG)
        # 木の対象は全 push(遠隔に在っても上書き)・木に無い遠隔は削除
        assert ("push", "docs/a.md") in actions
        assert ("push", "docs/sub/b.md") in actions
        assert ("push", "README.md") in actions
        assert ("push", "core/skip.py") not in actions
        assert ("delete", "docs/stale.md") in actions
        assert ("delete", "manual-upload.txt") in actions
        assert ("delete", "docs/a.md") not in actions

    def test_full_with_clean_remote_has_no_deletes(self) -> None:
        actions = sp.plan_full_mirror(["docs/a.md"], ["docs/a.md"], MCFG)
        assert actions == [("push", "docs/a.md")]


class TestMirrorConfig:
    def test_defaults_when_section_missing(self) -> None:
        mcfg = sp.mirror_config({})
        assert mcfg["branch"] == "main"
        assert mcfg["remote"] == "Docs"
        assert "docs" in mcfg["paths"]
        assert "README.md" in mcfg["files"]

    def test_partial_section_is_merged(self) -> None:
        mcfg = sp.mirror_config({"git_mirror": {"branch": "release"}})
        assert mcfg["branch"] == "release"
        assert mcfg["remote"] == "Docs"  # 未指定キーは既定値


class TestMirrorState:
    def test_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "sharepoint_mirror.json"
        sp.save_mirror_state(path, "main", "abc123")
        state = sp.load_mirror_state(path)
        assert state == {"branch": "main", "commit": "abc123"}

    def test_missing_file_is_none(self, tmp_path: Path) -> None:
        assert sp.load_mirror_state(tmp_path / "nope.json") is None

    def test_corrupt_json_is_none(self, tmp_path: Path) -> None:
        path = tmp_path / "sharepoint_mirror.json"
        path.write_text("{broken", encoding="utf-8")
        assert sp.load_mirror_state(path) is None

    def test_state_path_respects_tc_var_dir(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv("TC_VAR_DIR", str(tmp_path))
        assert Path(sp.mirror_state_path()) == tmp_path / "sharepoint_mirror.json"

    def test_save_creates_parent_dir(self, tmp_path: Path) -> None:
        path = tmp_path / "var-sandbox" / "sharepoint_mirror.json"
        sp.save_mirror_state(path, "main", "abc123")
        assert json.loads(path.read_text(encoding="utf-8"))["commit"] == "abc123"


class TestHooksInstall:
    def test_installs_three_hooks(self, tmp_path: Path) -> None:
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        written = install_hooks(tmp_path)
        names = sorted(p.name for p in written)
        assert names == ["post-commit", "pre-commit", "pre-push"]
        for p in written:
            assert p.exists()
            body = p.read_text(encoding="utf-8")
            assert "python" in body.lower()
        # 各フックが対応するスクリプトを指す
        hooks_dir = tmp_path / ".git" / "hooks"
        assert "pre_commit.py" in (hooks_dir / "pre-commit").read_text(encoding="utf-8")
        assert "post_commit.py" in (hooks_dir / "post-commit").read_text(encoding="utf-8")
        assert "pre_push.py" in (hooks_dir / "pre-push").read_text(encoding="utf-8")

    def test_reinstall_is_idempotent(self, tmp_path: Path) -> None:
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        install_hooks(tmp_path)
        written = install_hooks(tmp_path)  # 再実行で上書き・例外なし
        assert len(written) == 3
