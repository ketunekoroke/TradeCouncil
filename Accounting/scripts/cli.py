"""Accounting 運用 CLI(`ac`)。正準起動は `python -m scripts.cli`(`ac` シムはブロックされる環境あり)。

サブコマンド:
  ac test                    pytest 実行(足場: smoke / decoupling / docs lint)
  ac hooks install           git フック3種を導入(pre-commit=検査 / post-commit・pre-push=docs ミラー)
  ac sync                    workspace の SharePoint 双方向同期(shared/sharepoint.py)
  ac mirror                  docs を SharePoint へ一方向ミラー(ADR-0010)
  ac mf config [--product accounting|expense] [--check]
                             MoneyForward API 設定の表示・検証(会計/経費の両方。秘密はマスク。--check は未設定で exit 1)
  ac mf authorize --product <accounting|expense> [--no-open]
                             認可 URL(client_id 入り)を生成してブラウザを開く(認可コード取得)

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
        targets = [args.product] if getattr(args, "product", None) else list(mf.PRODUCTS)

        print("MoneyForward API 設定(秘密はマスク表示):")
        for product in targets:
            pc = cfg.get(product)
            summary = pc.masked()
            print(f"\n[{product}] {pc.label}")
            for key, value in summary.items():
                if key in ("ready", "missing", "label"):
                    continue
                print(f"  {key:14} : {value}")
            if pc.is_ready():
                print("  -> ready: 接続に必要な項目は揃っています")
            else:
                missing = ", ".join(pc.missing_required())
                print(f"  -> 未設定の必須項目: {missing}")
                print(
                    f"     秘密は .env(MONEYFORWARD_{product.upper()}_CLIENT_SECRET 等)、"
                    "URL/scopes は config/moneyforward.config.json に設定します。"
                )

        # --check の合否: --product 指定時はそのプロダクト、未指定時は「いずれか1つ以上 ready」。
        if getattr(args, "check", False):
            if args.product:
                return 0 if cfg.get(args.product).is_ready() else 1
            return 0 if cfg.ready_products() else 1
        return 0

    if args.mf_command == "authorize":
        import secrets
        import webbrowser

        from core import moneyforward as mf

        pc = mf.load_config().get(args.product)
        try:
            state = secrets.token_urlsafe(8)
            url = mf.build_authorize_url(pc, state=state)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"[{args.product}] {pc.label} 認可 URL(ブラウザで開いて許可してください):\n")
        print(url + "\n")
        if not pc.scopes:
            print(
                "warn: scopes が未設定です。使う API のスコープを config の "
                f"products.{args.product}.oauth.scopes に設定してください(空のままだと認可が拒否されることがあります)。\n"
            )
        print(f"state(CSRF 確認用。戻り先 URL の state がこの値と一致するか確認): {state}")
        print(
            "許可後にリダイレクト先 URL の `code=` の値を控え、`.env` の "
            f"MONEYFORWARD_{args.product.upper()}_AUTH_CODE に設定 → "
            f"`python scripts\\spike_moneyforward.py --product {args.product}` でトークン交換。"
        )
        if not args.no_open:
            try:
                webbrowser.open(url)
                print("\nブラウザを開きました(開かない場合は上の URL を貼り付けてください)。")
            except Exception as exc:  # ヘッドレス等では開けないことがある
                print(f"\n(ブラウザを自動で開けませんでした: {exc}。上の URL を手で開いてください)")
        return 0

    print("usage: ac mf config [--product accounting|expense] [--check] | ac mf authorize --product <..>",
          file=sys.stderr)
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

    p_mf = sub.add_parser("mf", help="MoneyForward API 連携(会計 / 経費)")
    mf_sub = p_mf.add_subparsers(dest="mf_command", required=True)
    pm_config = mf_sub.add_parser("config", help="API 設定の表示・検証(秘密はマスク)")
    pm_config.add_argument(
        "--product", choices=["accounting", "expense"], help="対象プロダクト(既定: 両方表示)"
    )
    pm_config.add_argument(
        "--check", action="store_true",
        help="未設定なら exit 1(--product 指定時はそのプロダクト、未指定時はいずれか1つ以上 ready)",
    )
    pm_auth = mf_sub.add_parser("authorize", help="認可 URL を生成してブラウザを開く(認可コード取得)")
    pm_auth.add_argument(
        "--product", choices=["accounting", "expense"], required=True, help="対象プロダクト(必須)"
    )
    pm_auth.add_argument("--no-open", action="store_true", help="ブラウザを開かず URL の表示のみ")
    p_mf.set_defaults(func=cmd_mf)

    return parser


def main(argv: list[str] | None = None) -> int:
    configure_output_streams()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
