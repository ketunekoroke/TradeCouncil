"""経費取込パイプラインのオーケストレーション(scripts 層)。

純粋な core(extract/ingest/refdata/policy/gate/register)を、I/O(SharePoint=shared・画像=Pillow・
前期実績=mf_expense_api)とつなぐ。**Claude が書いたサイドカー JSON**
(`var/expense/extracted/<raw>.json`)を継ぎ目にして、決定的な処理(リネーム・重複・ポリシー・下書き)を
回す。将来はサイドカーをビジョンブリッジが機械生成すればヘッドレス化できる。

ローカルは `var/expense/`(gitignore)を作業領域、SharePoint をマスタとする:
  raw/ ← pull, extracted/ ← Claude, processed/(+_original)→ push, drafts/, refdata/, ledger.json
"""

from __future__ import annotations

import base64
import csv
import datetime
import json
import mimetypes
import os
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Accounting/

from core import extract, gate, ingest, oauth, policy, refdata, register  # noqa: E402
from scripts import imageproc, mf_expense_api, notify, policy_loader  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]

RAW, EXTRACTED, PROCESSED, DRAFTS, REFDATA = "raw", "extracted", "processed", "drafts", "refdata"


# --- 置き場所(var/expense・EXPENSE_VAR_DIR で上書き可)----------------------------------

def expense_root() -> Path:
    override = os.environ.get("EXPENSE_VAR_DIR")
    return Path(override) if override else (PROJECT_ROOT / "var" / "expense")


def sub(name: str) -> Path:
    return expense_root() / name


def ledger_path() -> Path:
    return expense_root() / "ledger.json"


def usage_path() -> Path:
    return sub(REFDATA) / "expense_usage.json"


def sidecar_path(raw_name: str) -> Path:
    return sub(EXTRACTED) / f"{raw_name}.json"


# --- 前期実績(usage)----------------------------------------------------------------------

def load_usage() -> refdata.UsageIndex | None:
    p = usage_path()
    if not p.is_file():
        return None
    try:
        return refdata.UsageIndex.from_dict(json.loads(p.read_text(encoding="utf-8")))
    except (ValueError, OSError):
        return None


def save_usage(idx: refdata.UsageIndex) -> Path:
    p = usage_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(idx.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def prior_fy_range(today: datetime.date | None = None) -> tuple[str, str]:
    """CloudBloom の前期(7月〜翌6月)の日付範囲(ISO)。today 既定は実日付。"""
    today = today or datetime.date.today()
    fy_start_year = today.year if today.month >= 7 else today.year - 1  # 今期の開始年
    start = datetime.date(fy_start_year - 1, 7, 1)  # 前期 7/1
    end = datetime.date(fy_start_year, 6, 30)  # 前期 6/30
    return start.isoformat(), end.isoformat()


def default_refdata_range(today: datetime.date | None = None) -> tuple[str, str]:
    """usage 学習の既定範囲: 前期の開始(7/1)〜今日。前期+今期を通して実績を拾う
    (新設法人など前期が空でも当期の使用実績を学習できるように)。"""
    today = today or datetime.date.today()
    start, _ = prior_fy_range(today)
    return start, today.isoformat()


def run_refdata(
    pc, *, date_from: str, date_to: str, list_fn=None, access_token: str | None = None
) -> dict:
    """前期の経費明細を取得 → 集計 → usage を保存。サマリを返す。"""
    list_fn = list_fn or mf_expense_api.list_my_ex_transactions
    txs = list_fn(pc, date_from=date_from, date_to=date_to, access_token=access_token)
    idx = refdata.aggregate_usage(txs)
    save_usage(idx)
    return {
        "raw_count": len(txs),
        "n": idx.n,
        "ex_items": dict(sorted(idx.ex_item_totals.items(), key=lambda kv: -kv[1])),
        "excises": dict(sorted(idx.excise_totals.items(), key=lambda kv: -kv[1])),
        "from": date_from,
        "to": date_to,
    }


# --- 取り込み処理(raw + サイドカー → processed + draft + ledger)--------------------------

def _now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _dedup_suffix(proc_dir: Path, date: str, payee: str, ext: str, content_hash: str) -> str:
    """同名(日付_支払先.ext)が既にあれば短ハッシュ接尾辞、無ければ空。"""
    base = ingest.build_filename(date, payee, ext)
    return content_hash[:6] if (proc_dir / base).exists() else ""


def process_all(
    *,
    approve_overwrite: bool = False,
    approver=None,
    now: str | None = None,
    process_image=None,
    high_value_jpy: int | None = None,
) -> dict:
    """raw/ の各証憑(サイドカーあり)を処理する。重複は承認の上で上書き(削除はしない)。

    `approver(existing_entry, fields) -> bool` で similar 重複の上書き可否を問う(対話/テスト注入)。
    `process_image` は imageproc.process_receipt(注入可)。返り値は処理結果のサマリ。
    """
    process_image = process_image or imageproc.process_receipt
    now = now or _now_iso()
    if high_value_jpy is None:
        high_value_jpy = policy_loader.high_value_jpy()

    usage = load_usage()
    fxr = policy_loader.fx_rule()
    ovr = policy_loader.overrides()
    led = ingest.Ledger.load(ledger_path())

    raw_dir, proc_dir, draft_dir = sub(RAW), sub(PROCESSED), sub(DRAFTS)
    proc_dir.mkdir(parents=True, exist_ok=True)
    draft_dir.mkdir(parents=True, exist_ok=True)

    results: dict = {"processed": [], "skipped": [], "pending_extract": [], "errors": []}

    for raw in sorted(p for p in raw_dir.glob("*") if p.is_file()):
        if raw.name.startswith("."):
            continue
        sc = sidecar_path(raw.name)
        if not sc.is_file():
            results["pending_extract"].append(raw.name)
            continue
        try:
            fields = extract.parse_sidecar(json.loads(sc.read_text(encoding="utf-8")))
        except (ValueError, OSError) as exc:
            results["errors"].append({"file": raw.name, "error": f"サイドカー不正: {exc}"})
            continue
        problems = fields.validate()
        if problems:
            results["errors"].append({"file": raw.name, "error": "; ".join(problems)})
            continue

        h = ingest.content_hash(raw)
        kind, existing = ingest.find_duplicate(
            h, fields.date, fields.payee, fields.amount, fields.currency, led
        )
        if kind == "exact":
            results["skipped"].append({"file": raw.name, "reason": "完全重複(処理済み)"})
            continue
        overwrite = False
        if kind == "similar":
            approved = approve_overwrite
            if not approved and approver:
                approved = bool(approver(existing, fields))
            if not approved:
                results["skipped"].append(
                    {"file": raw.name, "reason": f"重複・未承認(既存 {existing.filename})"}
                )
                continue
            overwrite = True

        ext = raw.suffix
        if overwrite and existing and existing.filename:
            primary_name = existing.filename
            original_name = existing.original_filename or ingest.build_filename(
                fields.date, fields.payee, ext, original=True
            )
        else:
            suffix = _dedup_suffix(proc_dir, fields.date, fields.payee, ext, h)
            primary_name = ingest.build_filename(
                fields.date, fields.payee, ext, dedup_suffix=suffix
            )
            original_name = ingest.build_filename(
                fields.date, fields.payee, ext, original=True, dedup_suffix=suffix
            )

        box = tuple(fields.crop_box) if (fields.crop_box and imageproc.is_image(raw)) else None
        process_image(raw, proc_dir / primary_name, proc_dir / original_name, box)

        draft = policy.apply_policy(
            fields, usage=usage, fx_rule=fxr, fx_rate=fields.fx_rate, overrides=ovr, receipt_hash=h
        )
        issues = gate.check(draft, fields, high_value_jpy=high_value_jpy)
        rid = ingest.make_receipt_id(fields.date, fields.payee, h)
        draft_dict = register.build_expense_draft(
            draft,
            fields,
            receipt=register.ReceiptRef(
                processed_file=primary_name, original_file=original_name,
                content_hash=h, source_file=raw.name,
            ),
            issues=issues,
        )
        draft_path = draft_dir / f"{rid}.json"
        draft_path.write_text(register.to_json(draft_dict), encoding="utf-8")

        entry = ingest.LedgerEntry(
            receipt_id=rid, content_hash=h, date=fields.date, payee=fields.payee,
            amount=str(fields.amount), currency=fields.currency, source_file=raw.name,
            filename=primary_name, original_filename=original_name, ex_item=draft.ex_item,
            excise=draft.excise, jpy_amount=draft.jpy_amount, correlation_key=draft.correlation_key,
            draft_path=draft_path.name, mf_status="draft", created_at=now,
        )
        if overwrite and existing:
            led.supersede(existing, entry, at=now)
        else:
            led.upsert(entry)

        results["processed"].append(
            {
                "file": raw.name,
                "processed_file": primary_name,
                "summary": register.to_summary(draft_dict),
                "errors": [i.to_dict() for i in issues if i.level == "error"],
                "overwrote": overwrite,
            }
        )

    led.save(ledger_path())
    return results


# --- 経費明細台帳の Excel 生成 -----------------------------------------------------------

EXPORT = "export"


def export_dir() -> Path:
    return sub(EXPORT)


def _load_draft_file(name: str | None) -> dict:
    if not name:
        return {}
    p = sub(DRAFTS) / name
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def export_xlsx(out_path: str | Path | None = None, *, embed_images: bool = True) -> Path:
    """ledger + draft から経費明細台帳 xlsx を生成(各行に証憑サムネイルを埋込)。出力先を返す。"""
    from scripts import expense_xlsx

    led = ingest.Ledger.load(ledger_path())
    rows: list[dict] = []
    images: dict[str, str] = {}
    for e in led.entries:
        draft = _load_draft_file(e.draft_path)
        pol = draft.get("policy", {})
        ex = draft.get("ex_transaction", {})
        rows.append({
            "mf_number": e.mf_number or "",
            "date": e.date,
            "payee": e.payee,
            "ex_item": e.ex_item or "",
            "excise": e.excise or "",
            "amount": e.amount,
            "currency": e.currency,
            "fx_rate": pol.get("fx_rate") or "",
            "jpy_amount": e.jpy_amount or e.amount,
            "invoice_number": ex.get("number") or "",
            "description": pol.get("description") or "",
            "correlation_key": e.correlation_key,
            "filename": e.filename,
            "mf_status": e.mf_status,
            "mf_transaction_id": e.mf_transaction_id or "",
        })
        img = sub(PROCESSED) / e.filename
        if embed_images and e.filename and img.is_file() and imageproc.is_image(img):
            images[e.correlation_key] = str(img)
    out = Path(out_path) if out_path else (export_dir() / "expense_明細台帳.xlsx")
    out.parent.mkdir(parents=True, exist_ok=True)
    expense_xlsx.build_xlsx(rows, out, images=images, row_key="correlation_key")
    return out


# --- クラウド経費への登録(POST ex_transactions + receipt_input=証憑/電帳法)--------------

_CONTENT_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".pdf": "application/pdf",
    ".gif": "image/gif", ".webp": "image/webp", ".heic": "image/heic", ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def _content_type(path: Path) -> str:
    return _CONTENT_TYPES.get(path.suffix.lower()) or mimetypes.guess_type(str(path))[0] or (
        "application/octet-stream"
    )


def _extract_mf_id(resp: object) -> str | None:
    if isinstance(resp, dict):
        if resp.get("id"):
            return str(resp["id"])
        for key in ("ex_transaction", "data"):
            inner = resp.get(key)
            if isinstance(inner, dict) and inner.get("id"):
                return str(inner["id"])
    return None


def _extract_mf_number(resp: object) -> str | None:
    if isinstance(resp, dict):
        if resp.get("number") is not None:
            return str(resp["number"])
        for key in ("ex_transaction", "data"):
            inner = resp.get(key)
            if isinstance(inner, dict) and inner.get("number") is not None:
                return str(inner["number"])
    return None


def _err_str(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
        except OSError:
            detail = ""
        return f"HTTP {exc.code} {exc.reason} {detail}".strip()
    return str(exc)[:300]


def _notify_facts(e: ingest.LedgerEntry) -> dict:
    """登録通知用の FactSet(Teams)。"""
    return {
        "明細番号": e.mf_number or "-",
        "日付": e.date,
        "支払先": e.payee,
        "経費科目": e.ex_item or "-",
        "税区分": e.excise or "-",
        "金額": f"{e.amount} {e.currency}",
        "円換算": f"¥{e.jpy_amount}" if e.jpy_amount else "-",
        "証憑": "添付あり(電帳法)",
        "相関キー": e.correlation_key,
        "MF-ID": e.mf_transaction_id or "-",
    }


def _notifier(notify_fn):
    """通知関数を返す。注入が無ければ notify.send(env_prefix は system.yaml から)を使う。"""
    if notify_fn is not None:
        return notify_fn
    prefix = policy_loader.notify_env_prefix()

    def _send(channel, title, message, *, facts=None, severity="info"):
        return notify.send(
            channel, title, message, facts=facts, severity=severity, env_prefix=prefix
        )

    return _send


def _emit_registered_notify(e: ingest.LedgerEntry, *, send_fn) -> bool:
    """登録済み明細の詳細を OPERATIONS チャネルへ通知(best-effort)。"""
    title = f"クラウド経費に登録: {e.payee}"
    message = f"明細番号 {e.mf_number or '(未取得)'} ・ {e.ex_item or ''}".strip()
    try:
        return bool(send_fn("operations", title, message, facts=_notify_facts(e), severity="good"))
    except Exception:
        return False


def register_drafts(
    pc,
    *,
    confirm: bool = False,
    receipt_id: str | None = None,
    use_original: bool = False,
    create_fn=None,
    get_office_id_fn=None,
    access_token: str | None = None,
    notify_fn=None,
) -> dict:
    """ゲート合格の下書きをクラウド経費へ登録(POST ex_transactions + receipt_input=証憑/電帳法)。

    `confirm=False` はドライラン(送信せずプレビュー)。本番送信は `confirm=True` 必須。サイドカーから
    ポリシーを再適用し、費目/税区分は usage の名前→ID で解決(ID 無は skip → refdata 実行 or WEB)。
    成功した明細は ledger を `registered` に更新し MF 明細 ID を保存する。
    """
    create_fn = create_fn or mf_expense_api.create_ex_transaction
    send_fn = _notifier(notify_fn)
    usage = load_usage()
    fxr = policy_loader.fx_rule()
    ovr = policy_loader.overrides()
    led = ingest.Ledger.load(ledger_path())

    results: dict = {"registered": [], "skipped": [], "errors": [], "dry_run": not confirm}
    targets = [e for e in led.entries if e.mf_status != "registered"]
    if receipt_id:
        targets = [e for e in targets if receipt_id in e.receipt_id]
    if not targets:
        return results

    office_id = None
    if confirm:
        if access_token is None:
            access_token = oauth.get_access_token(pc)
        gid = get_office_id_fn or mf_expense_api.get_office_id
        office_id = gid(pc, access_token=access_token)
        if not office_id:
            results["errors"].append({"error": "office_id を取得できませんでした"})
            return results

    for e in targets:
        sc = sidecar_path(e.source_file)
        if not sc.is_file():
            results["errors"].append(
                {"receipt_id": e.receipt_id, "error": f"サイドカーなし: {e.source_file}"}
            )
            continue
        try:
            fields = extract.parse_sidecar(json.loads(sc.read_text(encoding="utf-8")))
        except (ValueError, OSError) as exc:
            results["errors"].append(
                {"receipt_id": e.receipt_id, "error": f"サイドカー不正: {exc}"}
            )
            continue
        draft = policy.apply_policy(
            fields, usage=usage, fx_rule=fxr, fx_rate=fields.fx_rate, overrides=ovr,
            receipt_hash=e.content_hash,
        )
        issues = gate.check(draft, fields)
        if gate.has_errors(issues):
            msg = "; ".join(i.message for i in issues if i.level == "error")
            results["skipped"].append(
                {"receipt_id": e.receipt_id, "reason": f"ゲート error: {msg}"}
            )
            continue
        ex_item_id = usage.ex_item_id(draft.ex_item) if usage else None
        if not ex_item_id:
            results["skipped"].append({
                "receipt_id": e.receipt_id,
                "reason": f"費目ID未解決『{draft.ex_item}』(refdata 実行 or WEB)",
            })
            continue
        excise_id = usage.excise_id(draft.excise) if usage else None
        img = sub(PROCESSED) / ((e.original_filename or e.filename) if use_original else e.filename)
        if not img.is_file():
            results["errors"].append(
                {"receipt_id": e.receipt_id, "error": f"証憑ファイルなし: {img.name}"}
            )
            continue
        attendants = tuple(fields.attendants) if fields.attendants else None
        memo = register.fx_memo(
            draft, rate_source=fxr.get("rate_source"), base_rule=fxr.get("base_rule")
        )
        body = register.build_ex_transaction_create(
            draft, fields, ex_item_id=ex_item_id, dr_excise_id=excise_id,
            receipt_content_b64=base64.b64encode(img.read_bytes()).decode("ascii"),
            content_type=_content_type(img), filename=e.filename, attendants=attendants, memo=memo,
        )
        if not confirm:
            tx = body["ex_transaction"]
            results["skipped"].append({
                "receipt_id": e.receipt_id, "reason": "dry-run(--confirm で送信)",
                "preview": {
                    "ex_item": draft.ex_item, "ex_item_id": ex_item_id, "excise": draft.excise,
                    "value": tx["value"], "currency": tx["currency"], "jpy": draft.jpy_amount,
                    "証憑添付": "receipt_input" in tx, "receipt": e.filename,
                },
            })
            continue
        try:
            resp = create_fn(pc, office_id, body, access_token=access_token)
        except (urllib.error.URLError, ValueError, OSError) as exc:
            results["errors"].append({"receipt_id": e.receipt_id, "error": _err_str(exc)})
            continue
        e.mf_status = "registered"
        e.mf_transaction_id = _extract_mf_id(resp)
        e.mf_number = _extract_mf_number(resp)
        led.upsert(e)
        notified = _emit_registered_notify(e, send_fn=send_fn)
        results["registered"].append({
            "receipt_id": e.receipt_id, "mf_id": e.mf_transaction_id,
            "ex_item": draft.ex_item, "notified": notified,
        })

    led.save(ledger_path())
    return results


def notify_registered(receipt_id: str | None = None, *, notify_fn=None) -> dict:
    """登録済みエントリの詳細を Teams(OPERATIONS)へ送信(再送・既存分の通知にも使える)。"""
    send_fn = _notifier(notify_fn)
    led = ingest.Ledger.load(ledger_path())
    targets = [e for e in led.entries if e.mf_status == "registered"]
    if receipt_id:
        targets = [e for e in targets if receipt_id in e.receipt_id]
    results: dict = {"sent": [], "skipped": []}
    for e in targets:
        ok = _emit_registered_notify(e, send_fn=send_fn)
        (results["sent"] if ok else results["skipped"]).append(e.receipt_id)
    return results


# --- 状態・下書き表示 ---------------------------------------------------------------------

def status() -> dict:
    led = ingest.Ledger.load(ledger_path())
    raw_dir = sub(RAW)
    raw_files = [p.name for p in raw_dir.glob("*") if p.is_file() and not p.name.startswith(".")]
    pending = [n for n in raw_files if not sidecar_path(n).is_file()]
    drafts = list(sub(DRAFTS).glob("*.json")) if sub(DRAFTS).is_dir() else []
    return {
        "ledger_entries": len(led.entries),
        "raw_files": len(raw_files),
        "pending_extract": pending,
        "drafts": len(drafts),
    }


def list_drafts(receipt_id: str | None = None) -> list[dict]:
    d = sub(DRAFTS)
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.glob("*.json")):
        if receipt_id and receipt_id not in f.stem:
            continue
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            continue
    return out


def write_drafts_csv(out_path: str | Path | None = None) -> tuple[Path, int]:
    """全下書きを1つの CSV に書き出す(Excel 用に UTF-8 BOM)。(出力先, 件数)を返す。"""
    from core import register

    drafts = list_drafts()
    out = Path(out_path) if out_path else (sub(DRAFTS) / "expense_drafts.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(register.CSV_COLUMNS)
        for d in drafts:
            writer.writerow(register.to_csv_row(d))
    return out, len(drafts)


# --- SharePoint(shared)pull/push ---------------------------------------------------------

def _shared_sp():
    sys.path.insert(0, str(REPO_ROOT))
    from shared import sharepoint as sp

    return sp


def _sp_drive(sp):
    sp.set_project(str(PROJECT_ROOT))
    cfg = sp.load_config()
    if not cfg.get("enabled"):
        raise SystemExit(
            "error: SharePoint が無効です(SHAREPOINT_AC_ENABLED / sharepoint.config.json を確認)"
        )
    token = sp.get_token(cfg)
    site_id = sp.resolve_site(cfg, token)
    drive_id = sp.resolve_drive(cfg, token, site_id)
    return sp, cfg, token, drive_id


def expense_remote(cfg: dict, key: str, default: str) -> str:
    """経費の SharePoint リモートパス(drive 直下相対)。config の `expense.{inbox,master}`。

    workspace/root は使わず、ドキュメント直下からの相対パスをそのまま使う(例 `Expense/Inbox`)。
    """
    exp = cfg.get("expense") or {}
    return (exp.get(key) or default).strip("/")


def pull_inbox() -> int:
    """SharePoint 経費 inbox(ドキュメント/Expense/Inbox)→ var/expense/raw に pull。件数を返す。"""
    sp, cfg, token, drive_id = _sp_drive(_shared_sp())
    raw = sub(RAW)
    raw.mkdir(parents=True, exist_ok=True)
    remote = expense_remote(cfg, "inbox", "Expense/Inbox")
    return sp.pull_folder(drive_id, remote, str(raw), token)


def push_master() -> int:
    """var/expense/processed → 経費 master(ドキュメント/Expense/Master)へ push。件数を返す。"""
    sp, cfg, token, drive_id = _sp_drive(_shared_sp())
    remote = expense_remote(cfg, "master", "Expense/Master")
    return sp.push_folder(drive_id, str(sub(PROCESSED)), remote, token)


def push_xlsx(local_xlsx: str | Path) -> str:
    """xlsx を ドキュメント/Expense/ 直下へ push(単一ファイル)。リモートパスを返す。"""
    local_xlsx = Path(local_xlsx)
    sp, cfg, token, drive_id = _sp_drive(_shared_sp())
    root = expense_remote(cfg, "root", "Expense")
    sp._ensure_remote_path(drive_id, root, token)
    remote_file = f"{root}/{local_xlsx.name}"
    with open(local_xlsx, "rb") as f:
        sp._upload_small(drive_id, remote_file, f.read(), token)
    return remote_file


def _sp_delete(sp, drive_id, remote_path: str, token) -> None:
    """SharePoint のファイルを削除。DELETE は 204(本文なし)を返すため JSON parse しない。"""
    import urllib.parse

    url = sp.GRAPH + f"/drives/{drive_id}/root:/{urllib.parse.quote(remote_path)}"
    try:
        sp.bc.http_raw("DELETE", url, sp._auth_headers(token), None, provider=sp.PROVIDER)
    except sp.bc.ProviderHTTPError as exc:
        if "404" in str(exc):  # 既に存在しない = 成功扱い(冪等)
            return
        raise


def clean_inbox(*, confirm: bool = False, registered_only: bool = True, delete_fn=None) -> dict:
    """処理済み(既定は登録済み)の証憑を SharePoint inbox から削除する(処理後の inbox 整理)。

    `confirm=False` はドライラン。`registered_only=True` は mf_status=registered のみ削除する
    (証憑が MF に入った後だけ inbox から消す=電帳法の原本担保)。SharePoint のごみ箱から復元可。
    """
    led = ingest.Ledger.load(ledger_path())
    targets = [
        e for e in led.entries
        if e.source_file and (e.mf_status == "registered" or not registered_only)
    ]
    results: dict = {"deleted": [], "skipped": [], "errors": [], "dry_run": not confirm}
    if not targets:
        return results
    if not confirm:
        for e in targets:
            results["skipped"].append({
                "source_file": e.source_file, "mf_status": e.mf_status,
                "reason": "dry-run(--confirm で削除)",
            })
        return results
    if delete_fn is None:  # 実 SharePoint へ接続(注入時は接続しない=テスト/オフライン可)
        sp, cfg, token, drive_id = _sp_drive(_shared_sp())
        inbox = expense_remote(cfg, "inbox", "Expense/Inbox")

        def delete_fn(name):
            _sp_delete(sp, drive_id, f"{inbox}/{name}", token)

    cleaned: set = set()
    for e in targets:
        try:
            delete_fn(e.source_file)
            results["deleted"].append(e.source_file)
            cleaned.add(e.receipt_id)
        except Exception as exc:  # 外部 I/O は多様な例外 → まとめて記録
            results["errors"].append({"source_file": e.source_file, "error": _err_str(exc)})
    if cleaned:  # 削除済みは再対象化しない(冪等)
        for e in led.entries:
            if e.receipt_id in cleaned:
                e.source_file = ""
        led.save(ledger_path())
    return results
