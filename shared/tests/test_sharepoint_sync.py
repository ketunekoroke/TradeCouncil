"""workspace 統合と双方向 sync(ADR-0009)のテスト。

ネットワーク不使用:
  - plan_sync は純関数(相対パス→更新時刻の索引を比較し push/pull/skip を判定)
  - root 解決は enabled の真偽によらず常に workspace/(local/sharepoint 切替の廃止)
"""

from __future__ import annotations

from pathlib import Path

from shared import sharepoint as sp


class TestPlanSync:
    def test_only_local_is_pushed(self) -> None:
        actions = dict(sp.plan_sync({"a/x.md": 100.0}, {}))
        assert actions == {"a/x.md": "push"}

    def test_only_remote_is_pulled(self) -> None:
        actions = dict(sp.plan_sync({}, {"a/x.md": 100.0}))
        assert actions == {"a/x.md": "pull"}

    def test_local_newer_wins(self) -> None:
        actions = dict(sp.plan_sync({"x.md": 200.0}, {"x.md": 100.0}))
        assert actions == {"x.md": "push"}

    def test_remote_newer_wins(self) -> None:
        actions = dict(sp.plan_sync({"x.md": 100.0}, {"x.md": 200.0}))
        assert actions == {"x.md": "pull"}

    def test_within_skew_is_skipped(self) -> None:
        """SharePoint のタイムスタンプは秒精度 → 許容誤差内は同一とみなす。"""
        actions = dict(sp.plan_sync({"x.md": 100.0}, {"x.md": 101.5}, skew_sec=2.0))
        assert actions == {"x.md": "skip"}
        # 境界の外は同期される
        actions = dict(sp.plan_sync({"x.md": 100.0}, {"x.md": 102.5}, skew_sec=2.0))
        assert actions == {"x.md": "pull"}

    def test_no_deletion_propagation(self) -> None:
        """追加型: 片側に無い = 削除ではなくコピー対象(削除は伝播しない)。"""
        actions = dict(
            sp.plan_sync({"only_local.md": 100.0}, {"only_remote.md": 100.0})
        )
        assert actions == {"only_local.md": "push", "only_remote.md": "pull"}
        assert "delete" not in actions.values()

    def test_excluded_files_not_planned(self) -> None:
        local = {
            "council/.gitkeep": 100.0,
            "README.md": 100.0,          # workspace 直下の README は同期しない
            "reviews/draft.tmp": 100.0,
            "reviews/real.md": 100.0,
        }
        actions = dict(sp.plan_sync(local, {}))
        assert actions == {"reviews/real.md": "push"}

    def test_subfolder_readme_is_synced(self) -> None:
        """除外は workspace 直下の README.md のみ(成果物の README は同期対象)。"""
        actions = dict(sp.plan_sync({"reviews/README.md": 100.0}, {}))
        assert actions == {"reviews/README.md": "push"}


class TestRootResolution:
    def test_root_is_project_workspace(self, tmp_path: Path) -> None:
        """root は常に <project>/workspace(enabled の真偽によらず — ADR-0009/0011)。"""
        original = sp.project_dir()
        try:
            sp.set_project(tmp_path)
            for enabled in (True, False):
                cfg = {"enabled": enabled, "folders": {}}
                assert sp.active_root_name(cfg) == "workspace"
                assert Path(sp.active_root_path(cfg)) == tmp_path / "workspace"
        finally:
            sp.set_project(original)

    def test_config_path_follows_project(self, tmp_path: Path) -> None:
        original = sp.project_dir()
        try:
            sp.set_project(tmp_path)
            assert Path(sp.config_path()) == tmp_path / "sharepoint.config.json"
        finally:
            sp.set_project(original)
