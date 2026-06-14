"""Accounting 運用 CLI(`ac`)。正準起動は `python -m scripts.cli`(`ac` シムはブロックされる環境あり)。

サブコマンド:
  ac test                    pytest 実行(足場: smoke / decoupling / docs lint)
  ac hooks install           git フック3種を導入(pre-commit=検査 / post-commit・pre-push=docs ミラー)
  ac sync                    workspace の SharePoint 双方向同期(shared/sharepoint.py)
  ac mirror                  docs を SharePoint へ一方向ミラー(ADR-0010)
  ac mf config [--check]     MoneyForward API 設定の表示・検証(秘密はマスク。--check は未設定なら exit 1)

注: 経費登録・API 疎通・検証ゲートは Phase 1([実装予定])。spike_moneyforward.py / check_compliance.py 参照。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]   # Accounting/
REPO_ROOT = Path(__file__).resolve().parents[2]       # モノレポルート(共有 .venv/.env — ADR-0011)


def configure_output_streams() -> None:
    """stdout/stderr をエンコードエラーで落ちない設定に再構成する(Windows cp932 対策)。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")


def cmd_test(_args: argparse.Namespace) -> int:
    return subprocess.call([sys.executable, "-m", "pytest", "-q"], cwd=PROJECT_ROOT)


def cmd_hooks(args: argparse.Namespace) -> int:
    if args.hooks_command == "install":
        # git フックはリポジトリ単位(shared/hooks が真実源 — ADR-0011)。
        sys.path.insert(0, str(REPO_ROOT))
        from shared.hooks import install_hooks

        for hook_path in install_hooks(REPO_ROOT):
            print(f"git フックを導入: {hook_path}")
        return 0
    print("usage: ac hooks install", file=sys.stderr)
    return 2


def _sharepoint(action: str) -> int:
    """shared/sharepoint.py を本プロジェクトに対して実行する(sync / mirror)。"""
    sharepoint = REPO_ROOT / "shared" / "sharepoint.py"
    return subprocess.call(
        [sys.executable, str(sharepoint), action, "--project", str(PROJECT_ROOT)],
        cwd=REPO_ROOT,
    )


def cmd_sync(_args: argparse.Namespace) -> int:
    return _sharepoint("sync")


def cmd_mirror(_args: argparse.Namespace) -> int:
    return _sharepoint("mirror")


def cmd_mf(args: argparse.Namespace) -> int:
    if args.mf_command == "config":
        from core import moneyforward as mf

        cfg = mf.load_config()
        summary = cfg.masked()
        print("MoneyForward API 設定(秘密はマスク表示):")
        for key, value in summary.items():
            if key in ("ready", "missing"):
                continue
            print(f"  {key:14} : {value}")
        if cfg.is_ready():
            print("  -> ready: 接続に必要な項目は揃っています")
            return 0
        missing = ", ".join(cfg.missing_required())
        print(f"  -> 未設定の必須項目: {missing}")
        print("     秘密は .env(MONEYFORWARD_CLIENT_SECRET 等)、URL は config/moneyforward.config.json に設定します。")
        # --check 指定時のみ未設定を失敗扱いにする(pre-flight / CI 用)。
        return 1 if getattr(args, "check", False) else 0
    print("usage: ac mf config [--check]", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ac", description="Accounting 運用CLI(会計経理支援システム)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_test = sub.add_parser("test", help="テスト実行(足場)")
    p_test.set_defaults(func=cmd_test)

    p_hooks = sub.add_parser("hooks", help="git フックの導入")
    hooks_sub = p_hooks.add_subparsers(dest="hooks_command", required=True)
    hooks_sub.add_parser(
        "install",
        help="git フック3種を導入(pre-commit=検査 / post-commit・pre-push=docs ミラー ADR-0010)",
    )
    p_hooks.set_defaults(func=cmd_hooks)

    p_sync = sub.add_parser("sync", help="workspace の SharePoint 双方向同期")
    p_sync.set_defaults(func=cmd_sync)

    p_mirror = sub.add_parser("mirror", help="docs を SharePoint へ一方向ミラー(ADR-0010)")
    p_mirror.set_defaults(func=cmd_mirror)

    p_mf = sub.add_parser("mf", help="MoneyForward API 連携")
    mf_sub = p_mf.add_subparsers(dest="mf_command", required=True)
    pm_config = mf_sub.add_parser("config", help="API 設定の表示・検証(秘密はマスク)")
    pm_config.add_argument(
        "--check", action="store_true", help="必須項目が未設定なら exit 1(pre-flight / CI 用)"
    )
    p_mf.set_defaults(func=cmd_mf)

    return parser


def main(argv: list[str] | None = None) -> int:
    configure_output_streams()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
