"""Accounting 運用 CLI(`ac`)。正準起動は `python -m scripts.cli`(`ac` シムはブロックされる環境あり)。

サブコマンド:
  ac test                    pytest 実行(足場: smoke / decoupling / docs lint)
  ac hooks install           git フック3種を導入(pre-commit=検査 / post-commit・pre-push=docs ミラー)
  ac sync                    workspace の SharePoint 双方向同期(shared/sharepoint.py)
  ac mirror                  docs を SharePoint へ一方向ミラー(ADR-0010)
  ac mf config [--product accounting|expense] [--check]
                             MoneyForward API 設定の表示・検証(会計/経費の両方。秘密はマスク。--check は未設定で exit 1)
  ac mf login --product <accounting|expense> [--no-listen] [--code <CODE>]
                             認可〜code取得〜token保存(会計=loopback で自動受信 / 経費=OOB で code を貼り付け)
  ac mf refresh --product <accounting|expense>
                             保存トークンを必要に応じて refresh_token で更新
  ac mf token --product <accounting|expense> [--show]
                             保存トークンの状態表示(秘密はマスク)
  ac mf authorize --product <accounting|expense> [--no-open]
                             認可 URL を生成してブラウザを開く(手動で code を取得。expense/ヘッドレス向け)

注: 経費登録・検証ゲートは Phase 1([実装予定])。spike_moneyforward.py / check_compliance.py 参照。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.error
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


def _print_masked(masked: dict) -> None:
    """マスク済みサマリを整形表示する(秘密の値は出さない)。"""
    for key, value in masked.items():
        print(f"  {key:14} : {value}")


def _err(exc: Exception) -> str:
    """例外を人間向けの1行(+詳細)に整形する。"""
    if isinstance(exc, urllib.error.HTTPError):
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        return f"HTTP {exc.code} {exc.reason}\n{detail}"
    if isinstance(exc, urllib.error.URLError):
        return f"接続失敗: {exc.reason}"
    return str(exc)


def _mf_login_manual(args: argparse.Namespace, pc, url: str, state: str) -> int:
    """loopback が使えない経路(経費の OOB・--no-listen・ヘッドレス)の対話ペースト式ログイン。

    ブラウザで認可 → MF が表示した(または リダイレクト先 URL の)`code=` を貼り付け → 即交換・保存。
    `--code` 指定時は対話なし。貼り付けできない環境(ヘッドレス)では従来の .env+spike 手順を案内する。
    """
    import webbrowser

    from core import oauth, token_store

    product = args.product
    print(f"[{product}] {pc.label} 認可 URL(ブラウザで開いて許可してください):\n")
    print(url + "\n")
    if not pc.scopes:
        print("warn: scopes が未設定です(config の products.<product>.oauth.scopes を確認)。\n")
    print(f"state(表示/戻り先 URL の state がこの値と一致するか確認): {state}")
    try:
        webbrowser.open(url)
    except Exception as exc:  # ヘッドレス等では開けないことがある
        print(f"(ブラウザを自動で開けませんでした: {exc}。上の URL を手で開いてください)")

    code = getattr(args, "code", None)
    if not code:
        try:
            code = input("\n認可後に表示された(またはリダイレクト先 URL の)code= を貼り付け: ").strip()
        except (EOFError, OSError):  # ヘッドレス / stdin なし
            code = ""
    if not code:
        print(
            "\ncode の入力がありませんでした。`.env` の "
            f"MONEYFORWARD_{product.upper()}_AUTH_CODE に設定 → "
            f"`python -m scripts.spike_moneyforward --product {product}` でも交換・保存できます。"
        )
        return 0
    try:
        bundle = oauth.exchange_code(pc, code)
    except (urllib.error.URLError, ValueError) as exc:
        print(f"error: トークン交換に失敗: {_err(exc)}", file=sys.stderr)
        return 1
    token_store.save(product, bundle)
    print(f"\n[{product}] ログイン完了。トークンを保存しました(秘密はマスク):")
    _print_masked(bundle.masked())
    return 0


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

    if args.mf_command == "login":
        import secrets
        import webbrowser

        from core import moneyforward as mf
        from core import oauth, token_store
        from scripts.oauth_listener import (
            ListenerUnavailable,
            capture_code,
            is_loopback_redirect,
        )

        pc = mf.load_config().get(args.product)
        if not pc.is_ready():
            print(
                f"[{args.product}] 接続設定が未完了です(`mf config --product {args.product}` で確認)。"
                f" 未設定: {', '.join(pc.missing_required())}",
                file=sys.stderr,
            )
            return 1
        try:
            state = secrets.token_urlsafe(16)
            url = mf.build_authorize_url(pc, state=state)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        # 会計(loopback http)はリスナで自動受信。経費(OOB)/ --no-listen は対話ペースト式。
        if args.no_listen or not is_loopback_redirect(pc.redirect_uri):
            return _mf_login_manual(args, pc, url, state)

        print(f"[{args.product}] {pc.label} 認可 URL(自動で開きます。開かない場合は下記を貼り付け):\n")
        print(url + "\n")
        print(f"state(CSRF 確認用。戻り先 URL の state がこの値と一致するか確認): {state}")
        print("ブラウザで許可してください(loopback で code を自動受信します)…")

        def _open_browser() -> None:
            try:
                webbrowser.open(url)
            except Exception as exc:  # ヘッドレス等では開けないことがある
                print(f"(ブラウザを自動で開けませんでした: {exc}。上の URL を手で開いてください)")

        try:
            cb = capture_code(pc.redirect_uri, state, on_ready=_open_browser)
        except ListenerUnavailable as exc:
            print(f"warn: ローカルリスナを起動できません({exc})。手動フローに切り替えます。\n", file=sys.stderr)
            return _mf_login_manual(args, pc, url, state)
        if cb.error or not cb.code:
            print(f"error: 認可に失敗しました: {cb.error_description or cb.error or '不明'}", file=sys.stderr)
            return 1
        try:
            bundle = oauth.exchange_code(pc, cb.code)
        except (urllib.error.URLError, ValueError) as exc:
            print(f"error: トークン交換に失敗: {_err(exc)}", file=sys.stderr)
            return 1
        token_store.save(args.product, bundle)
        print(f"[{args.product}] ログイン完了。トークンを保存しました(秘密はマスク):")
        _print_masked(bundle.masked())
        return 0

    if args.mf_command == "refresh":
        from core import moneyforward as mf
        from core import oauth, token_store

        pc = mf.load_config().get(args.product)
        try:
            oauth.get_access_token(pc)  # 失効していれば refresh して保存
        except oauth.ReloginRequired as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except (urllib.error.URLError, ValueError) as exc:
            print(f"error: refresh に失敗: {_err(exc)}", file=sys.stderr)
            return 1
        bundle = token_store.load(args.product)
        print(f"[{args.product}] アクセストークン有効(必要なら更新済み):")
        if bundle is not None:
            _print_masked(bundle.masked())
        return 0

    if args.mf_command == "token":
        from core import token_store

        bundle = token_store.load(args.product)
        if bundle is None:
            print(
                f"[{args.product}] 保存トークンなし。"
                f"`python -m scripts.cli mf login --product {args.product}` を実行してください。"
            )
            return 0
        print(f"[{args.product}] 保存トークン(秘密はマスク):")
        _print_masked(bundle.masked())
        if args.show:
            print(f"  path           : {token_store.token_path(args.product)}")
        return 0

    print(
        "usage: ac mf config|login|refresh|token|authorize --product <accounting|expense> [...]",
        file=sys.stderr,
    )
    return 2


def _interactive_overwrite_approver():
    """重複(similar)時に上書き可否を対話で問う関数を返す。ヘッドレスでは False(上書きしない)。"""

    def _ask(existing, fields) -> bool:
        try:
            ans = input(
                f"重複の可能性: 既存 {existing.filename}({existing.amount}{existing.currency})を "
                f"新 {fields.payee}/{fields.amount}{fields.currency} で上書きしますか? [y/N]: "
            ).strip().lower()
        except (EOFError, OSError):
            return False
        return ans in ("y", "yes")

    return _ask


def _print_split_results(results: dict) -> None:
    mode = "DRY-RUN(分割なし)" if results["dry_run"] else "実分割"
    print(
        f"[expense] PDF分割 {mode}: 分割 {len(results['split'])} / "
        f"skip {len(results['skipped'])} / エラー {len(results['errors'])}"
    )
    for s in results["split"]:
        print(f"  分割: {s['file']} → {', '.join(s['parts'])}(原本は split_src へ退避)")
    for s in results["skipped"]:
        extra = ""
        if s.get("parts"):
            extra = f" → {', '.join(s['parts'])}"
            if s.get("unused_pages"):
                extra += f"(未割当ページ {s['unused_pages']})"
        print(f"  {s['file']}: {s['reason']}{extra}")
    for e in results["errors"]:
        print(f"  error: {e['file']} — {e['error']}", file=sys.stderr)


def _print_process_results(results: dict) -> None:
    proc = results["processed"]
    print(
        f"[expense] 処理 {len(proc)} / skip {len(results['skipped'])} / "
        f"抽出待ち {len(results['pending_extract'])} / エラー {len(results['errors'])}"
    )
    for p in proc:
        print(p["summary"] + ("   (上書き)" if p.get("overwrote") else ""))
    for s in results["skipped"]:
        print(f"  skip: {s['file']} — {s['reason']}")
    for name in results["pending_extract"]:
        print(f"  抽出待ち(Claude がサイドカー生成): {name}")
    for e in results["errors"]:
        print(f"  error: {e['file']} — {e['error']}", file=sys.stderr)


def _print_register_results(results: dict) -> None:
    mode = "DRY-RUN(送信なし)" if results["dry_run"] else "本番送信"
    print(
        f"[expense] 登録 {mode}: 成功 {len(results['registered'])} / "
        f"skip {len(results['skipped'])} / エラー {len(results['errors'])}"
    )
    for r in results["registered"]:
        teams = " / Teams通知✓" if r.get("notified") else ""
        mid = r.get("mf_id") or "(なし)"
        print(f"  登録: {r['receipt_id']} → MF {mid} / {r['ex_item']}{teams}")
    for s in results["skipped"]:
        pv = s.get("preview")
        if pv:
            print(
                f"  予定: {s['receipt_id']}  {pv['ex_item']}  {pv['value']}{pv['currency']}"
                f"(¥{pv.get('jpy')})  証憑添付={pv['証憑添付']}"
            )
        else:
            print(f"  skip: {s['receipt_id']} — {s['reason']}")
    for e in results["errors"]:
        print(f"  error: {e.get('receipt_id', '')} — {e['error']}", file=sys.stderr)


def _print_clean_results(results: dict) -> None:
    mode = "DRY-RUN(削除なし)" if results["dry_run"] else "実削除"
    print(
        f"[expense] inbox {mode}: 削除 {len(results['deleted'])} / "
        f"skip {len(results['skipped'])} / エラー {len(results['errors'])}"
    )
    for n in results["deleted"]:
        print(f"  削除: {n}")
    for s in results["skipped"]:
        print(f"  対象: {s['source_file']}({s.get('mf_status')}) — {s['reason']}")
    for e in results["errors"]:
        print(f"  error: {e.get('source_file', '')} — {e['error']}", file=sys.stderr)


def _print_import_past_results(results: dict) -> None:
    print(
        f"[expense] 過去分取込 {results['from']}〜{results['to']}: "
        f"取込 {len(results['imported'])} / 証憑DL {results['downloaded']} / "
        f"証憑なし {len(results['no_file'])} / skip {len(results['skipped'])} / "
        f"エラー {len(results['errors'])}"
    )
    for r in results["imported"]:
        mark = "🧾" if r["has_file"] else "(証憑なし)"
        print(f"  取込: {r['tx_id']}  {r['payee']}  {mark}")
    if results["no_file"]:
        print(f"  証憑なし(WEB手動): {', '.join(results['no_file'])}")
    for e in results["errors"]:
        print(f"  error: {e.get('tx_id', '')} — {e['error']}", file=sys.stderr)


def _fmt_change(c: dict) -> str:
    return f"{c['field']}: {c['before']!r}→{c['after']!r}"


def _print_revise_past_results(results: dict) -> None:
    mode = "DRY-RUN(更新なし)" if results["dry_run"] else "本番更新"
    print(
        f"[expense] 過去分補正 {mode}: 補正 {len(results['revised'])} / "
        f"変更なし {len(results['no_change'])} / skip {len(results['skipped'])} / "
        f"エラー {len(results['errors'])}"
    )
    for r in results["revised"]:
        teams = " / Teams通知✓" if r.get("notified") else ""
        print(f"  補正: {r['tx_id']}  " + " ; ".join(_fmt_change(c) for c in r["changes"]) + teams)
    for s in results["skipped"]:
        changes = s.get("changes")
        if changes:
            src = f"[{s.get('source', '')}] " if s.get("source") else ""
            print(
                f"  予定: {s['tx_id']}  {src}{s.get('payee', '')}  "
                + " ; ".join(_fmt_change(c) for c in changes)
            )
        else:
            print(f"  skip: {s['tx_id']} — {s['reason']}")
    for e in results["errors"]:
        print(f"  error: {e.get('tx_id', '')} — {e['error']}", file=sys.stderr)


def cmd_expense(args: argparse.Namespace) -> int:
    from scripts import expense_pipeline as ep

    cmd = args.expense_command

    if cmd == "refdata":
        from core import moneyforward as mf
        from core import oauth

        pc = mf.load_product(args.product)
        if not pc.is_ready():
            print(
                f"[{args.product}] 接続設定が未完了です(`mf config --product {args.product}`)。"
                f" 未設定: {', '.join(pc.missing_required())}",
                file=sys.stderr,
            )
            return 1
        df, dt = ep.default_refdata_range()
        date_from, date_to = (args.date_from or df), (args.date_to or dt)
        try:
            summary = ep.run_refdata(pc, date_from=date_from, date_to=date_to)
        except oauth.ReloginRequired as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except (urllib.error.URLError, ValueError) as exc:
            print(f"error: 前期実績の取得に失敗: {_err(exc)}", file=sys.stderr)
            return 1
        except SystemExit as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(
            f"[expense] 前期実績 {summary['from']}〜{summary['to']}: "
            f"明細 {summary['raw_count']} 件 / 集計 {summary['n']} 件 → {ep.usage_path()}"
        )
        for title, table in (("費目", summary["ex_items"]), ("税区分", summary["excises"])):
            if table:
                print(f"  {title}(使用実績・上位):")
                for name, c in list(table.items())[:10]:
                    print(f"    {c:>4} : {name}")
        return 0

    if cmd == "masters":
        from core import moneyforward as mf
        from core import oauth

        pc = mf.load_product(args.product)
        if not pc.is_ready():
            print(
                f"[{args.product}] 接続設定が未完了です(`mf config --product {args.product}`)。"
                f" 未設定: {', '.join(pc.missing_required())}",
                file=sys.stderr,
            )
            return 1
        try:
            summary = ep.fetch_masters(pc)
        except oauth.ReloginRequired as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except (urllib.error.URLError, ValueError) as exc:
            print(
                f"error: マスタ取得に失敗: {_err(exc)}"
                "(403 の場合は scope office_setting:write で再認可してください)",
                file=sys.stderr,
            )
            return 1
        except SystemExit as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if summary.get("error"):
            print(f"error: {summary['error']}", file=sys.stderr)
            return 1
        print(
            f"[expense] マスタ取得: 費目 {summary['ex_items']} 件 / 税区分 {summary['excises']} 件 "
            f"→ usage に ID 追加(費目 +{summary['added_ex_item']} / 税区分 +{summary['added_excise']})"
            f" {ep.usage_path()}"
        )
        if args.show:
            print("  費目:", "、".join(summary["ex_item_names"]))
            print("  税区分:", "、".join(summary["excise_names"]))
        return 0

    if cmd == "pull":
        try:
            n = ep.pull_inbox()
        except SystemExit as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"[expense] pull 完了: {n} ファイル → {ep.sub('raw')}")
        pending = ep.status()["pending_extract"]
        if pending:
            print("  抽出待ち(Claude が読んで extracted/<name>.json を生成してください):")
            for name in pending:
                print(f"    - {name}")
            print(
                "  ※ 1つの PDF に複数レシートがある場合は、先に分割サイドカー "
                "split/<name>.json を書いて `expense split --confirm`(1ファイル1レシート化)。"
            )
        return 0

    if cmd == "split":
        results = ep.split_pdfs(confirm=args.confirm)
        _print_split_results(results)
        return 0 if not results["errors"] else 1

    if cmd == "process":
        approver = None
        if not args.approve_overwrite and not args.yes:
            approver = _interactive_overwrite_approver()
        results = ep.process_all(
            approve_overwrite=args.approve_overwrite,
            approver=approver,
            high_value_jpy=(args.high_value or None),
        )
        _print_process_results(results)
        return 0 if not results["errors"] else 1

    if cmd == "push":
        try:
            n = ep.push_master()
        except SystemExit as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"[expense] push 完了: {n} ファイル(SharePoint master を更新)")
        return 0

    if cmd == "sync-var":
        try:
            results = ep.sync_var(core_only=args.core_only)
        except SystemExit as exc:
            print(str(exc), file=sys.stderr)
            return 1
        scope = "状態の核" if args.core_only else "フル"
        print(
            f"[expense] var 同期({scope}) {results['local']} ↔ {results['remote']}: "
            f"push {len(results['pushed'])} / pull {len(results['pulled'])} / skip {results['skipped']}"
        )
        return 0

    if cmd == "status":
        st = ep.status()
        print(
            f"[expense] 台帳 {st['ledger_entries']} 件 / raw {st['raw_files']} 件 / "
            f"下書き {st['drafts']} 件 / 過去分 取込{st['past_imported']}・補正{st['past_revised']}"
        )
        for name in st["pending_extract"]:
            print(f"  抽出待ち: {name}")
        return 0

    if cmd == "drafts":
        from core import register

        drafts = ep.list_drafts(getattr(args, "id", None))
        if not drafts:
            print("[expense] 下書きはありません。")
            return 0
        for d in drafts:
            print(register.to_summary(d))
        return 0

    if cmd == "csv":
        out, n = ep.write_drafts_csv(getattr(args, "out", None))
        print(f"[expense] CSV 書き出し: {n} 件 → {out}")
        return 0

    if cmd == "register":
        from core import moneyforward as mf
        from core import oauth

        pc = mf.load_product("expense")
        if not pc.is_ready():
            print(
                "[expense] 接続設定が未完了です(`mf config --product expense`)。"
                f" 未設定: {', '.join(pc.missing_required())}",
                file=sys.stderr,
            )
            return 1
        cloud_keys = None
        if getattr(args, "cloud_dedup", False):
            led = ep.ingest.Ledger.load(ep.ledger_path())
            dts = [e.date for e in led.entries if e.mf_status != "registered" and e.date]
            df = (min(dts) if dts else ep.current_fy_range()[0])
            dt = (max(dts) if dts else ep.current_fy_range()[1])
            try:
                cloud_keys = ep.cloud_dupe_index(pc, date_from=df, date_to=dt)
            except oauth.ReloginRequired as exc:
                print(str(exc), file=sys.stderr)
                return 1
            except (urllib.error.URLError, ValueError, SystemExit) as exc:
                print(f"error: クラウド突合の取得に失敗: {_err(exc)}", file=sys.stderr)
                return 1
            print(f"[expense] クラウド突合キー {len(cloud_keys)} 件({df}〜{dt})で重複判定")
        try:
            results = ep.register_drafts(
                pc, confirm=args.confirm, receipt_id=getattr(args, "id", None),
                use_original=args.original, cloud_keys=cloud_keys,
            )
        except oauth.ReloginRequired as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except (urllib.error.URLError, ValueError) as exc:
            print(f"error: 登録に失敗: {_err(exc)}", file=sys.stderr)
            return 1
        _print_register_results(results)
        return 0 if not results["errors"] else 1

    if cmd in ("import-past", "revise-past"):
        from core import moneyforward as mf
        from core import oauth

        pc = mf.load_product("expense")
        if not pc.is_ready():
            print(
                "[expense] 接続設定が未完了です(`mf config --product expense`)。"
                f" 未設定: {', '.join(pc.missing_required())}",
                file=sys.stderr,
            )
            return 1
        try:
            if cmd == "import-past":
                results = ep.import_past(
                    pc, date_from=getattr(args, "date_from", None),
                    date_to=getattr(args, "date_to", None),
                )
            else:
                results = ep.revise_past(
                    pc, confirm=args.confirm, tx_id=getattr(args, "id", None),
                    rewrite_remark=getattr(args, "rewrite_remark", False),
                    sidecar_only=getattr(args, "sidecar_only", False),
                )
        except oauth.ReloginRequired as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except (urllib.error.URLError, ValueError) as exc:
            verb = "取込" if cmd == "import-past" else "補正"
            print(f"error: 過去分の{verb}に失敗: {_err(exc)}", file=sys.stderr)
            return 1
        except SystemExit as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if cmd == "import-past":
            _print_import_past_results(results)
        else:
            _print_revise_past_results(results)
        return 0 if not results["errors"] else 1

    if cmd == "clean-inbox":
        results = ep.clean_inbox(confirm=args.confirm, registered_only=not args.processed)
        _print_clean_results(results)
        return 0 if not results["errors"] else 1

    if cmd == "xlsx":
        out = ep.export_xlsx(getattr(args, "out", None), embed_images=not args.no_images)
        print(f"[expense] 明細台帳 xlsx 生成: {out}")
        if args.push:
            try:
                remote = ep.push_xlsx(out)
            except SystemExit as exc:
                print(str(exc), file=sys.stderr)
                return 1
            print(f"  → SharePoint ドキュメント/{remote} に push 完了")
        return 0

    if cmd == "notify":
        results = ep.notify_registered(getattr(args, "id", None))
        print(
            f"[expense] Teams 通知(OPERATIONS): 送信 {len(results['sent'])} / "
            f"未送信 {len(results['skipped'])}"
        )
        for r in results["sent"]:
            print(f"  送信: {r}")
        for r in results["skipped"]:
            print(f"  未送信(URL未設定/送信失敗): {r}", file=sys.stderr)
        return 0

    print(
        "usage: ac expense "
        "refdata|masters|pull|sync-var|split|process|push|register|import-past|revise-past|"
        "clean-inbox|notify|status|drafts|csv|xlsx",
        file=sys.stderr,
    )
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
    pm_login = mf_sub.add_parser(
        "login", help="認可〜code取得〜token保存を自動化(会計は loopback 自動・expense は手動)"
    )
    pm_login.add_argument(
        "--product", choices=["accounting", "expense"], required=True, help="対象プロダクト(必須)"
    )
    pm_login.add_argument(
        "--no-listen", action="store_true", help="loopback リスナを使わず対話ペースト式(経費/ヘッドレス)"
    )
    pm_login.add_argument(
        "--code", help="認可後の code を直接渡す(対話入力を省略。経費の OOB / ヘッドレス向け)"
    )
    pm_refresh = mf_sub.add_parser("refresh", help="保存トークンを必要に応じて更新(refresh_token)")
    pm_refresh.add_argument(
        "--product", choices=["accounting", "expense"], required=True, help="対象プロダクト(必須)"
    )
    pm_token = mf_sub.add_parser("token", help="保存トークンの状態表示(秘密はマスク)")
    pm_token.add_argument(
        "--product", choices=["accounting", "expense"], required=True, help="対象プロダクト(必須)"
    )
    pm_token.add_argument("--show", action="store_true", help="保存先パスも表示(値はマスクのまま)")
    pm_auth = mf_sub.add_parser("authorize", help="認可 URL を生成してブラウザを開く(手動 code 取得)")
    pm_auth.add_argument(
        "--product", choices=["accounting", "expense"], required=True, help="対象プロダクト(必須)"
    )
    pm_auth.add_argument("--no-open", action="store_true", help="ブラウザを開かず URL の表示のみ")
    p_mf.set_defaults(func=cmd_mf)

    p_exp = sub.add_parser(
        "expense", help="経費レシート取込パイプライン(SharePoint master・下書き生成 BL-AC-020)"
    )
    exp_sub = p_exp.add_subparsers(dest="expense_command", required=True)
    pe_refdata = exp_sub.add_parser(
        "refdata", help="前期のクラウド経費実績から費目/税区分の使用実績を集計"
    )
    pe_refdata.add_argument(
        "--product", choices=["expense"], default="expense", help="対象(既定: expense)"
    )
    pe_refdata.add_argument("--from", dest="date_from", help="集計開始日 ISO(既定: 前期7/1)")
    pe_refdata.add_argument("--to", dest="date_to", help="集計終了日 ISO(既定: 前期6/30)")
    pe_masters = exp_sub.add_parser(
        "masters", help="費目/税区分マスタを取得し usage に ID をマージ(要 office_setting:write)"
    )
    pe_masters.add_argument(
        "--product", choices=["expense"], default="expense", help="対象(既定: expense)"
    )
    pe_masters.add_argument(
        "--show", action="store_true", help="取得した費目/税区分の名称一覧も表示"
    )
    exp_sub.add_parser("pull", help="SharePoint の expense-inbox を var/expense/raw へ取得")
    pe_syncvar = exp_sub.add_parser(
        "sync-var",
        help="var を SharePoint(Expense/Var)と双方向同期(別PCで作業継続。既定フル)",
    )
    pe_syncvar.add_argument(
        "--core-only", action="store_true",
        help="状態の核(台帳/サイドカー/refdata/下書き/murc/スナップショット)だけ同期(画像除外・軽量)",
    )
    pe_split = exp_sub.add_parser(
        "split",
        help="複数レシート PDF を1ファイル1レシートに分割(サイドカー必須・既定ドライラン)",
    )
    pe_split.add_argument("--confirm", action="store_true", help="実分割(未指定はドライラン)")
    pe_proc = exp_sub.add_parser(
        "process", help="raw+サイドカーを処理(リネーム/トリミング/重複/ポリシー下書き)"
    )
    pe_proc.add_argument(
        "--approve-overwrite", action="store_true", help="重複時に確認なしで上書き"
    )
    pe_proc.add_argument(
        "--yes", action="store_true", help="対話確認をスキップ(重複は上書きしない)"
    )
    pe_proc.add_argument(
        "--high-value", type=int, default=0, help="高額フラグのしきい値(円。0=既定)"
    )
    exp_sub.add_parser("push", help="var/expense/processed を SharePoint master へ push(上書き)")
    pe_reg = exp_sub.add_parser(
        "register", help="下書きをクラウド経費へ登録(証憑添付=電帳法。既定はドライラン)"
    )
    pe_reg.add_argument("--confirm", action="store_true", help="本番送信(未指定はドライラン)")
    pe_reg.add_argument("--id", help="receipt_id の部分一致で対象を絞る")
    pe_reg.add_argument(
        "--original", action="store_true", help="証憑に原本(_original)を使う(既定: トリミング後)"
    )
    pe_reg.add_argument(
        "--cloud-dedup", action="store_true",
        help="クラウド実体と金額+日付で突合し、同額同日は登録せず『要個別確認』でskip(ローカル台帳でなくクラウドを正)",
    )
    pe_imp = exp_sub.add_parser(
        "import-past", help="今期の既存クラウド経費明細を取込み証憑をDL(過去分確認の前段)"
    )
    pe_imp.add_argument("--from", dest="date_from", help="取得開始日 ISO(既定: 今期7/1)")
    pe_imp.add_argument("--to", dest="date_to", help="取得終了日 ISO(既定: 今日)")
    pe_rev = exp_sub.add_parser(
        "revise-past", help="取込んだ過去分に当期ポリシーを再適用し差分を補正(既定ドライラン)"
    )
    pe_rev.add_argument("--confirm", action="store_true", help="本番更新 PUT(未指定はドライラン)")
    pe_rev.add_argument("--id", help="MF 明細 ID の部分一致で対象を絞る")
    pe_rev.add_argument(
        "--rewrite-remark", action="store_true", help="摘要を店名先頭へ整形(既定は温存)"
    )
    pe_rev.add_argument(
        "--sidecar-only", action="store_true",
        help="サイドカーがある明細だけ補正(未確認分への policy-only 変更を防ぐ)",
    )
    pe_clean = exp_sub.add_parser(
        "clean-inbox", help="登録済みの証憑を SharePoint inbox から削除(既定はドライラン)"
    )
    pe_clean.add_argument("--confirm", action="store_true", help="実削除(未指定はドライラン)")
    pe_clean.add_argument(
        "--processed", action="store_true", help="登録前(processed)も削除対象に(既定は登録済みのみ)"
    )
    pe_xlsx = exp_sub.add_parser(
        "xlsx", help="経費明細台帳の Excel を生成(--push で ドキュメント/Expense/ へ)"
    )
    pe_xlsx.add_argument("--push", action="store_true", help="生成後 SharePoint へ push")
    pe_xlsx.add_argument("--out", help="出力先(既定: var/expense/export/expense_明細台帳.xlsx)")
    pe_xlsx.add_argument("--no-images", action="store_true", help="証憑サムネイルを埋め込まない")
    pe_notify = exp_sub.add_parser(
        "notify", help="登録済み明細の詳細を Teams(OPERATIONS チャネル)へ送信"
    )
    pe_notify.add_argument("--id", help="receipt_id の部分一致で対象を絞る")
    exp_sub.add_parser("status", help="台帳・抽出待ち・下書きの状態表示")
    pe_drafts = exp_sub.add_parser("drafts", help="下書き(人可読要約)を表示")
    pe_drafts.add_argument("--id", help="receipt_id の部分一致で絞る")
    pe_csv = exp_sub.add_parser("csv", help="下書きを CSV に書き出す(Excel 用 UTF-8 BOM)")
    pe_csv.add_argument("--out", help="出力先(既定: var/expense/drafts/expense_drafts.csv)")
    p_exp.set_defaults(func=cmd_expense)

    return parser


def main(argv: list[str] | None = None) -> int:
    configure_output_streams()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
