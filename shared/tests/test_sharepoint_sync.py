"""workspace 統合と双方向 sync(ADR-0009)のテスト。

ネットワーク不使用:
  - plan_sync は純関数(相対パス→更新時刻の索引を比較し push/pull/skip を判定)
  - root 解決は enabled の真偽によらず常に workspace/(local/sharepoint 切替の廃止)
"""

from __future__ import annotations

import json
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


class TestRemoteRootResolution:
    """root(遠隔基点)は per-project config が共有 env より優先される(ADR-0011)。"""

    def _write_cfg(self, project: Path, root: str) -> None:
        project.mkdir(parents=True, exist_ok=True)
        (project / "sharepoint.config.json").write_text(
            json.dumps({"enabled": True, "root": root, "folders": {}}),
            encoding="utf-8",
        )

    def test_config_root_wins_over_shared_env(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        # 共有 .env が単一の SHAREPOINT_ROOT を持っていても、各プロジェクトの
        # config root が勝ち、同期先が衝突しないことを確認する。
        monkeypatch.setattr(sp.bc, "setting", lambda name: "Workspace"
                            if name == "SHAREPOINT_ROOT" else None)
        original = sp.project_dir()
        try:
            magi = tmp_path / "Magi"
            tc = tmp_path / "TradeCouncil"
            self._write_cfg(magi, "Magi/Workspace")
            self._write_cfg(tc, "TradeCouncil/Workspace")

            sp.set_project(magi)
            assert sp.load_config()["root"] == "Magi/Workspace"
            sp.set_project(tc)
            assert sp.load_config()["root"] == "TradeCouncil/Workspace"
        finally:
            sp.set_project(original)

    def test_env_is_fallback_when_config_root_empty(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr(sp.bc, "setting", lambda name: "Shared"
                            if name == "SHAREPOINT_ROOT" else None)
        original = sp.project_dir()
        try:
            self._write_cfg(tmp_path, "")  # config が root 未設定 → env フォールバック
            sp.set_project(tmp_path)
            assert sp.load_config()["root"] == "Shared"
        finally:
            sp.set_project(original)


class TestPerProjectConnection:
    """接続(site_url/client_id/secret)を per-project で変えられる(ADR-0011)。"""

    def _write(self, project: Path, cfg: dict) -> None:
        project.mkdir(parents=True, exist_ok=True)
        (project / "sharepoint.config.json").write_text(json.dumps(cfg), encoding="utf-8")

    def test_project_env_prefix_wins_over_shared(self, tmp_path: Path, monkeypatch) -> None:
        env = {
            "SHAREPOINT_SITE_URL": "https://shared",      # 共有(全プロジェクト既定)
            "SHAREPOINT_MAGI_SITE_URL": "https://magi",   # プロジェクト別(prefix=MAGI)
            "SHAREPOINT_MAGI_CLIENT_SECRET": "magi-secret",
            "SHAREPOINT_CLIENT_SECRET": "shared-secret",
        }
        monkeypatch.setattr(sp.bc, "get_setting", lambda *names: next(
            (env[n] for n in names if n in env), None))
        original = sp.project_dir()
        try:
            self._write(tmp_path, {"enabled": True, "env_prefix": "MAGI", "folders": {}})
            sp.set_project(tmp_path)
            cfg = sp.load_config()
            assert cfg["site_url"] == "https://magi"       # 共有より prefix が勝つ
            assert sp.client_secret(cfg) == "magi-secret"  # 秘密もプロジェクト別が勝つ
        finally:
            sp.set_project(original)

    def test_config_identifier_then_shared_env_fallback(self, tmp_path: Path, monkeypatch) -> None:
        env = {"SHAREPOINT_CLIENT_SECRET": "shared-secret"}
        monkeypatch.setattr(sp.bc, "get_setting", lambda *names: next(
            (env[n] for n in names if n in env), None))
        original = sp.project_dir()
        try:
            # client_id は config に直書き(非秘密)、secret は共有 env にフォールバック
            self._write(tmp_path, {
                "enabled": True, "env_prefix": "MAGI",
                "client_id": "config-client", "folders": {},
            })
            sp.set_project(tmp_path)
            cfg = sp.load_config()
            assert cfg["client_id"] == "config-client"
            assert sp.client_secret(cfg) == "shared-secret"  # prefix 未設定 → 共有へ
        finally:
            sp.set_project(original)

    def test_placeholder_site_url_is_ignored(self, tmp_path: Path, monkeypatch) -> None:
        env = {"SHAREPOINT_SITE_URL": "https://shared"}
        monkeypatch.setattr(sp.bc, "get_setting", lambda *names: next(
            (env[n] for n in names if n in env), None))
        original = sp.project_dir()
        try:
            self._write(tmp_path, {
                "enabled": True, "env_prefix": "MAGI",
                "site_url": "https://<tenant>.sharepoint.com/sites/<site>", "folders": {},
            })
            sp.set_project(tmp_path)
            assert sp.load_config()["site_url"] == "https://shared"  # placeholder → 共有 env
        finally:
            sp.set_project(original)
