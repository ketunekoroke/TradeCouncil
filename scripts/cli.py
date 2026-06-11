"""TradeCouncil 運用 CLI(`tc`)。Makefile の代替(ADR-0001 §1)。

サブコマンド:
  tc db init                 スキーマ作成 + 実行時ディレクトリ準備
  tc test [--fast|--risk]    pytest 実行(--risk はカバレッジ90%ゲート付き)
  tc kill [--close-positions] キルスイッチ ON(フラグファイル作成)
  tc resume                  キルスイッチ解除(人間専用)
  tc status                  キルフラグ/必須ポリシー/heartbeat/建玉の一覧
  tc policy list|show|sync|record  ポリシーレジストリ操作
  tc approve|reject|defer    決裁キュー(proposals)への決裁
  tc paper --bot <id>        ペーパーBOT起動(常駐)
  tc watchdog                heartbeat 監視(常駐)
  tc kpi                     KPI集計と decision_id 連鎖検証
  tc snapshot [--output P]   DB の整合スナップショット(VACUUM INTO・バックアップ兼用)

注意: 実弾(live)系コマンドは存在しない(Phase 0)。
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def cmd_db(args: argparse.Namespace) -> int:
    if args.db_command == "init":
        from core.db import init_db

        init_db()
        from core.config import get_config

        print(f"DB initialized: {get_config().db_path}")
        return 0
    print("usage: tc db init", file=sys.stderr)
    return 2


def cmd_test(args: argparse.Namespace) -> int:
    cmd = [sys.executable, "-m", "pytest"]
    if args.fast:
        cmd += ["-x", "-q", "tests"]
    elif args.risk:
        cmd += [
            "tests/risk",
            "--cov=core.risk",
            "--cov-branch",
            "--cov-fail-under=90",
            "-q",
        ]
    else:
        cmd += ["-q"]
    return subprocess.call(cmd)


def cmd_kill(args: argparse.Namespace) -> int:
    from core.risk.kill_switch import activate

    path = activate(close_positions=args.close_positions)
    print(f"KILL switch ACTIVATED: {path}")
    print("全BOTは次の tick で停止します。解除は tc resume(人間専用)。")
    return 0


def cmd_resume(_args: argparse.Namespace) -> int:
    from core.risk.kill_switch import deactivate

    if deactivate():
        print("KILL switch deactivated.")
    else:
        print("KILL switch was not active.")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    from scripts.cli_status import print_status

    return print_status()


def cmd_policy(args: argparse.Namespace) -> int:
    from scripts.cli_policy import run_policy_command

    return run_policy_command(args)


def cmd_decide(args: argparse.Namespace) -> int:
    from scripts.cli_policy import run_decide_command

    return run_decide_command(args)


def cmd_hooks(args: argparse.Namespace) -> int:
    if args.hooks_command == "install":
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        hook_path = root / ".git" / "hooks" / "pre-commit"
        python = root / ".venv" / "Scripts" / "python.exe"
        script = root / "scripts" / "hooks" / "pre_commit.py"
        hook_path.write_text(
            "#!/bin/sh\n"
            f'"{python}" "{script}"\n',
            encoding="utf-8",
        )
        print(f"git pre-commit フックを導入: {hook_path}")
        return 0
    print("usage: tc hooks install", file=sys.stderr)
    return 2


def cmd_council(args: argparse.Namespace) -> int:
    if args.council_command == "log":
        from datetime import UTC, datetime

        from core.db import get_session_factory, init_db
        from core.db.models import CouncilSession

        init_db()
        with get_session_factory()() as session:
            existing = session.get(CouncilSession, args.session_id)
            if existing is not None:
                existing.minutes_path = args.minutes or existing.minutes_path
            else:
                session.add(
                    CouncilSession(
                        session_id=args.session_id,
                        kind=args.kind,
                        started_at=datetime.now(UTC).replace(tzinfo=None),
                        minutes_path=args.minutes,
                    )
                )
            session.commit()
        print(f"council_sessions に記録: {args.session_id} ({args.kind})")
        return 0
    print("usage: tc council log --session-id <id> --kind <kind> [--minutes <path>]", file=sys.stderr)
    return 2


def cmd_paper(args: argparse.Namespace) -> int:
    from core.runner.bot_runner import run_paper_bot

    return run_paper_bot(args.bot)


def cmd_watchdog(_args: argparse.Namespace) -> int:
    from core.runner.watchdog import run_watchdog

    return run_watchdog()


def cmd_kpi(_args: argparse.Namespace) -> int:
    from feedback.kpi import print_kpi_report

    return print_kpi_report()


def cmd_snapshot(args: argparse.Namespace) -> int:
    from datetime import UTC, datetime
    from pathlib import Path

    from core.config import get_config
    from core.db import snapshot_db

    source = get_config().db_path
    if not source.exists():
        print(f"DB が見つかりません: {source}(先に tc db init)", file=sys.stderr)
        return 1
    if args.output:
        dest = Path(args.output)
    else:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        dest = source.parent / "snapshots" / f"tradecouncil-{stamp}.db"
    try:
        result = snapshot_db(dest, source=source)
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"snapshot 作成: {result}(source: {source})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tc", description="TradeCouncil 運用CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_db = sub.add_parser("db", help="DB操作")
    p_db.add_argument("db_command", choices=["init"])
    p_db.set_defaults(func=cmd_db)

    p_test = sub.add_parser("test", help="テスト実行")
    g = p_test.add_mutually_exclusive_group()
    g.add_argument("--fast", action="store_true", help="高速サブセット(-x -q)")
    g.add_argument("--risk", action="store_true", help="riskテスト+カバレッジ90%ゲート")
    p_test.set_defaults(func=cmd_test)

    p_kill = sub.add_parser("kill", help="キルスイッチON(全BOT停止)")
    p_kill.add_argument("--close-positions", action="store_true", help="全ポジション成行クローズも要求")
    p_kill.set_defaults(func=cmd_kill)

    p_resume = sub.add_parser("resume", help="キルスイッチ解除(人間専用)")
    p_resume.set_defaults(func=cmd_resume)

    p_status = sub.add_parser("status", help="システム状態の一覧")
    p_status.set_defaults(func=cmd_status)

    p_policy = sub.add_parser("policy", help="ポリシーレジストリ操作")
    policy_sub = p_policy.add_subparsers(dest="policy_command", required=True)
    policy_sub.add_parser("list", help="全ポリシーの一覧")
    pp_show = policy_sub.add_parser("show", help="ポリシーの詳細表示")
    pp_show.add_argument("policy_id")
    policy_sub.add_parser("sync", help="実行用ビュー(config/generated/)を再生成")
    pp_record = policy_sub.add_parser("record", help="決裁レコードの適用(唯一の適用経路)")
    pp_record.add_argument("--file", required=True, help="決裁レコードYAML")
    p_policy.set_defaults(func=cmd_policy)

    for action in ("approve", "reject", "defer"):
        p_act = sub.add_parser(action, help=f"決裁キューの提案を{action}")
        p_act.add_argument("proposal_id")
        if action == "approve":
            p_act.add_argument("--file", help="決裁レコードYAML(ポリシー変更を伴う場合)")
        p_act.set_defaults(func=cmd_decide, decide_action=action)

    p_hooks = sub.add_parser("hooks", help="git フックの導入")
    hooks_sub = p_hooks.add_subparsers(dest="hooks_command", required=True)
    hooks_sub.add_parser("install", help="pre-commit フック(秘密検査・ポリシー検査)を導入")
    p_hooks.set_defaults(func=cmd_hooks)

    p_council = sub.add_parser("council", help="会議の開催記録")
    council_sub = p_council.add_subparsers(dest="council_command", required=True)
    pc_log = council_sub.add_parser("log", help="council_sessions へ開催記録を残す")
    pc_log.add_argument("--session-id", required=True)
    pc_log.add_argument("--kind", required=True, choices=["kickoff", "weekly", "monthly", "adhoc"])
    pc_log.add_argument("--minutes", help="議事録ファイルのパス")
    p_council.set_defaults(func=cmd_council)

    p_paper = sub.add_parser("paper", help="ペーパーBOT起動(常駐)")
    p_paper.add_argument("--bot", required=True, help="bot_id(config/bots/<id>.yaml)")
    p_paper.set_defaults(func=cmd_paper)

    p_watchdog = sub.add_parser("watchdog", help="heartbeat監視(常駐)")
    p_watchdog.set_defaults(func=cmd_watchdog)

    p_kpi = sub.add_parser("kpi", help="KPI集計と根拠連鎖の検証")
    p_kpi.set_defaults(func=cmd_kpi)

    p_snapshot = sub.add_parser("snapshot", help="DBの整合スナップショット(VACUUM INTO)")
    p_snapshot.add_argument("--output", help="出力先パス(既定: var/snapshots/tradecouncil-<時刻>.db)")
    p_snapshot.set_defaults(func=cmd_snapshot)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
