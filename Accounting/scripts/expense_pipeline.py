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

from core import (  # noqa: E402
    extract,
    gate,
    ingest,
    oauth,
    pdfsplit,
    policy,
    refdata,
    register,
    revise,
)
from scripts import imageproc, mf_expense_api, notify, pdfproc, policy_loader  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]

RAW, EXTRACTED, PROCESSED, DRAFTS, REFDATA = "raw", "extracted", "processed", "drafts", "refdata"
SPLIT = "split"  # 分割スペック(Claude が書く分割サイドカー)の置き場
SPLIT_SRC = "split_src"  # 分割後に退避した元 PDF(削除せず保持=復元可)
PAST = "past"  # 過去分(クラウド経費 既存明細)の証憑DL + MF 現値スナップショット置き場


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


def split_spec_path(raw_name: str) -> Path:
    return sub(SPLIT) / f"{raw_name}.json"


def past_dir() -> Path:
    return sub(PAST)


def past_snapshot_path(tx_id: str) -> Path:
    return past_dir() / f"{tx_id}.mf.json"


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


def current_fy_range(today: datetime.date | None = None) -> tuple[str, str]:
    """今期(7月〜翌6月)の範囲(ISO)。終端は今日と期末(6/30)の早い方。過去分確認の既定範囲。"""
    today = today or datetime.date.today()
    fy_start_year = today.year if today.month >= 7 else today.year - 1
    start = datetime.date(fy_start_year, 7, 1)
    end = datetime.date(fy_start_year + 1, 6, 30)
    return start.isoformat(), min(today, end).isoformat()


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


# --- 複数レシート PDF の分割(1ファイル1レシート化)-------------------------------------

def split_pdfs(*, confirm: bool = False, page_count_fn=None, split_fn=None) -> dict:
    """raw/ の複数レシート PDF を分割スペックに従い「1ファイル1レシート」に分ける。

    対象は **分割スペック**(`var/expense/split/<raw>.json`)があるファイルだけ。ページ数からの
    自動分割はしない(1レシートが複数ページの場合に誤分割しないため)。`confirm=False` は
    ドライラン(計画のみ)。本番は `confirm=True`。分割後の各パートは raw/ に新規ファイルとして置き、
    元 PDF は削除せず `var/expense/split_src/` へ退避する(SharePoint inbox にも原本が残る=復元可)。
    `page_count_fn`/`split_fn` はテスト用に注入できる(無ければ pypdf を使う)。
    """
    page_count_fn = page_count_fn or pdfproc.page_count
    split_fn = split_fn or pdfproc.split_pdf
    raw_dir = sub(RAW)
    results: dict = {"split": [], "skipped": [], "errors": [], "dry_run": not confirm}
    if not raw_dir.is_dir():
        return results

    for raw in sorted(p for p in raw_dir.glob("*") if p.is_file() and not p.name.startswith(".")):
        spec_p = split_spec_path(raw.name)
        if not spec_p.is_file():
            continue  # 分割対象ではない(通常の単一レシート)
        if not pdfproc.is_pdf(raw):
            results["errors"].append({"file": raw.name, "error": "PDF ではありません(分割対象外)"})
            continue
        try:
            plan = pdfsplit.parse_split_sidecar(json.loads(spec_p.read_text(encoding="utf-8")))
        except (ValueError, OSError) as exc:
            results["errors"].append({"file": raw.name, "error": f"分割スペック不正: {exc}"})
            continue
        try:
            n_pages = page_count_fn(raw)
        except Exception as exc:  # pypdf は多様な例外を投げうる
            results["errors"].append(
                {"file": raw.name, "error": f"ページ数取得不可: {_err_str(exc)}"}
            )
            continue
        parts = pdfsplit.expand(plan, n_pages)
        problems = pdfsplit.validate(parts, page_count=n_pages)
        if problems:  # 範囲外(off-by-one)・空・suffix 重複等は実行前に弾く
            results["errors"].append({"file": raw.name, "error": "; ".join(problems)})
            continue
        jobs = [(raw_dir / pdfsplit.output_name(raw.name, part), part.pages) for part in parts]
        existing = [out.name for out, _ in jobs if out.exists()]
        if existing:  # 既に分割済み(再実行)/ 衝突 → 上書きしない(冪等・安全側)
            results["skipped"].append(
                {"file": raw.name, "reason": f"出力が既に存在(分割済み?): {', '.join(existing)}"}
            )
            continue
        part_names = [out.name for out, _ in jobs]
        if not confirm:
            results["skipped"].append({
                "file": raw.name, "reason": "dry-run(--confirm で分割)",
                "pages": n_pages, "parts": part_names,
                "unused_pages": pdfsplit.unused_pages(parts, n_pages),
            })
            continue
        try:
            written = split_fn(raw, jobs)
        except Exception as exc:  # I/O・pypdf
            results["errors"].append({"file": raw.name, "error": _err_str(exc)})
            continue
        archive = sub(SPLIT_SRC)
        archive.mkdir(parents=True, exist_ok=True)
        moved = archive / raw.name
        os.replace(raw, moved)  # 元 PDF は退避(削除しない=復元可)
        results["split"].append({
            "file": raw.name,
            "parts": [Path(p).name for p in written],
            "archived_to": str(moved),
        })

    return results


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
        if e.filename and not img.is_file():  # 過去分の証憑は past/ にある
            img = past_dir() / e.filename
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


# content_type → 拡張子(証憑DL の保存名決定。jpeg は .jpeg を採用)。
_EXT_FROM_CT = {ct: ext for ext, ct in _CONTENT_TYPES.items()}


def _ext_for(mf_file: dict, content_type: str | None = None) -> str:
    """mf_file(name/content_type)から保存拡張子を決める。ファイル名拡張子 → content_type の順。"""
    name = (mf_file or {}).get("name") or ""
    suffix = Path(name).suffix.lower()
    if suffix:
        return suffix
    ct = (content_type or (mf_file or {}).get("content_type") or "").split(";")[0].strip().lower()
    return _EXT_FROM_CT.get(ct, ".bin")


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


def _emit_revised_notify(e: ingest.LedgerEntry, change_dicts: list[dict], *, send_fn) -> bool:
    """補正した過去分明細の詳細を OPERATIONS チャネルへ通知(best-effort)。"""
    fields = ", ".join(c["field"] for c in change_dicts) or "-"
    title = f"クラウド経費を補正: {e.payee}"
    message = f"明細番号 {e.mf_number or '-'} ・ 変更: {fields}"
    facts = _notify_facts(e)
    facts["変更項目"] = fields
    try:
        return bool(send_fn("operations", title, message, facts=facts, severity="good"))
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


# --- 過去分の取込・補正(import-past / revise-past)---------------------------------------

PAST_PREFIX = "past_"


def _is_404(exc: Exception) -> bool:
    return isinstance(exc, urllib.error.HTTPError) and exc.code == 404


def import_past(
    pc,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    list_fn=None,
    download_fn=None,
    get_office_id_fn=None,
    access_token: str | None = None,
    now: str | None = None,
    max_pages: int = 200,
) -> dict:
    """今期(既定 current_fy_range)のクラウド経費明細を取得し、証憑DL + MF 現値スナップショット +
    台帳 upsert(`mf_status="imported"`)。証憑なし明細は「証憑なしWEB確認」フラグ(revise 対象外)。

    `past_<tx_id>` で冪等(再実行で `revised` を `imported` に戻さない)。DL は size 一致でskip。
    `list_fn`/`download_fn`/`get_office_id_fn` は注入可(テストで無ネットワーク化)。
    """
    list_fn = list_fn or mf_expense_api.list_my_ex_transactions
    download_fn = download_fn or mf_expense_api.download_ex_transaction_receipt
    now = now or _now_iso()
    df, dt = current_fy_range()
    date_from, date_to = (date_from or df), (date_to or dt)

    results: dict = {
        "imported": [], "downloaded": 0, "no_file": [], "skipped": [], "errors": [],
        "from": date_from, "to": date_to,
    }
    if access_token is None:
        access_token = oauth.get_access_token(pc)
    gid = get_office_id_fn or mf_expense_api.get_office_id
    office_id = gid(pc, access_token=access_token)
    if not office_id:
        results["errors"].append({"error": "office_id を取得できませんでした"})
        return results

    txs = list_fn(
        pc, office_id, date_from=date_from, date_to=date_to,
        access_token=access_token, max_pages=max_pages,
    )
    led = ingest.Ledger.load(ledger_path())
    pdir = past_dir()
    pdir.mkdir(parents=True, exist_ok=True)

    for tx in txs:
        cur = revise.MFCurrent.from_tx(tx)
        if not cur.tx_id:
            results["errors"].append({"error": "id の無い明細をスキップしました"})
            continue
        past_snapshot_path(cur.tx_id).write_text(
            json.dumps(cur.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        receipt_name, content_hash = "", ""
        if cur.has_file:
            mf_file = cur.raw.get("mf_file") or {}
            dest = pdir / f"{PAST_PREFIX}{cur.tx_id}{_ext_for(mf_file)}"
            want = mf_file.get("byte_size")
            if dest.exists() and want and dest.stat().st_size == int(want):
                results["skipped"].append({"tx_id": cur.tx_id, "reason": "DL済み(サイズ一致)"})
                receipt_name, content_hash = dest.name, ingest.content_hash(dest)
            else:
                try:
                    data, _ct = download_fn(pc, office_id, cur.tx_id, access_token=access_token)
                except Exception as exc:  # 404=証憑消失等は記録して継続
                    results["errors"].append(
                        {"tx_id": cur.tx_id, "error": f"証憑DL失敗: {_err_str(exc)}"}
                    )
                else:
                    dest.write_bytes(data)
                    receipt_name, content_hash = dest.name, ingest.content_hash(dest)
                    results["downloaded"] += 1
        else:
            results["no_file"].append(cur.tx_id)

        rid = f"{PAST_PREFIX}{cur.tx_id}"
        existing = next((e for e in led.entries if e.receipt_id == rid), None)
        status = "revised" if (existing and existing.mf_status == "revised") else "imported"
        corr = policy.correlation_key(cur.date, f"mf{cur.number or cur.tx_id}")
        entry = ingest.LedgerEntry(
            receipt_id=rid, content_hash=content_hash, date=cur.date, payee=cur.payee,
            amount=cur.value, currency=cur.currency, source_file="",
            filename=(receipt_name or (existing.filename if existing else "")),
            original_filename=None, ex_item=cur.ex_item, excise=cur.excise,
            jpy_amount=(cur.value if cur.currency == "JPY" else None), correlation_key=corr,
            draft_path=None, mf_status=status, mf_transaction_id=cur.tx_id, mf_number=cur.number,
            created_at=(existing.created_at if existing else now),
            revised_at=(existing.revised_at if existing else None),
        )
        led.upsert(entry)
        results["imported"].append({
            "tx_id": cur.tx_id, "payee": cur.payee,
            "has_file": cur.has_file, "receipt": receipt_name,
        })

    led.save(ledger_path())
    return results


def revise_past(
    pc,
    *,
    confirm: bool = False,
    tx_id: str | None = None,
    update_fn=None,
    get_office_id_fn=None,
    access_token: str | None = None,
    notify_fn=None,
    now: str | None = None,
    rewrite_remark: bool = False,
) -> dict:
    """取り込んだ過去分に **当期ポリシーを再適用** し、MF 現値との差分を補正(PUT)する。

    事実はサイドカー(`extracted/past_<id>...json`=Claude 再読込)優先、無ければ MF 現値。
    `confirm=False` はドライラン。`--confirm` で **変更フィールドのみ** PUT。証憑なし明細
    (`has_file=false`)は WEB 手動で skip。差分ゼロも skip。`receipt_input` は付けない(再OCR回避)。
    """
    update_fn = update_fn or mf_expense_api.update_ex_transaction
    send_fn = _notifier(notify_fn)
    now = now or _now_iso()
    usage = load_usage()
    fxr = policy_loader.fx_rule()
    ovr = policy_loader.overrides()
    led = ingest.Ledger.load(ledger_path())

    results: dict = {
        "revised": [], "no_change": [], "skipped": [], "errors": [], "dry_run": not confirm,
    }
    targets = [
        e for e in led.entries
        if e.receipt_id.startswith(PAST_PREFIX) and e.mf_status in ("imported", "revised")
    ]
    if tx_id:
        targets = [e for e in targets if tx_id in (e.mf_transaction_id or "")]
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
        tid = e.mf_transaction_id or e.receipt_id[len(PAST_PREFIX):]
        snap_p = past_snapshot_path(tid)
        if not snap_p.is_file():
            results["errors"].append(
                {"tx_id": tid, "error": "MF 現値スナップショットなし(import-past を先に)"}
            )
            continue
        try:
            cur = revise.MFCurrent.from_dict(json.loads(snap_p.read_text(encoding="utf-8")))
        except (ValueError, OSError) as exc:
            results["errors"].append({"tx_id": tid, "error": f"スナップショット不正: {exc}"})
            continue
        if not cur.has_file:  # 証憑なしは WEB 手動(決定 2026-06-15)
            results["skipped"].append({"tx_id": tid, "reason": "証憑なし(WEB手動)"})
            continue

        sc = sidecar_path(e.filename) if e.filename else None
        if sc and sc.is_file():
            try:
                fields = extract.parse_sidecar(json.loads(sc.read_text(encoding="utf-8")))
            except (ValueError, OSError) as exc:
                results["errors"].append({"tx_id": tid, "error": f"サイドカー不正: {exc}"})
                continue
            source = "証憑再読込"
        else:
            fields = cur.to_receipt_fields()
            source = "MF現値(policy-only)"
        problems = fields.validate()
        if problems:
            results["errors"].append({"tx_id": tid, "error": "; ".join(problems)})
            continue

        draft = policy.apply_policy(
            fields, usage=usage, fx_rule=fxr, fx_rate=fields.fx_rate, overrides=ovr,
            receipt_hash=cur.tx_id,
        )
        issues = gate.check(draft, fields)
        if gate.has_errors(issues):
            msg = "; ".join(i.message for i in issues if i.level == "error")
            results["skipped"].append({"tx_id": tid, "reason": f"ゲート error: {msg}"})
            continue

        ex_item_id = usage.ex_item_id(draft.ex_item) if usage else None
        excise_id = usage.excise_id(draft.excise) if usage else None
        proposed_remark = f"{draft.payee} {draft.description}".strip() if rewrite_remark else None
        proposed_memo = register.fx_memo(
            draft, rate_source=fxr.get("rate_source"), base_rule=fxr.get("base_rule")
        )
        changes = revise.diff_entry(
            cur, draft, fields, ex_item_id=ex_item_id, excise_id=excise_id,
            proposed_remark=proposed_remark, proposed_memo=proposed_memo,
            rewrite_remark=rewrite_remark,
        )
        if not changes:
            results["no_change"].append(tid)
            continue
        change_dicts = [c.to_dict() for c in changes]
        if not confirm:
            results["skipped"].append({
                "tx_id": tid, "reason": "dry-run(--confirm で更新)", "source": source,
                "payee": cur.payee, "changes": change_dicts,
            })
            continue
        body = revise.build_update_body(changes, ex_item_id=ex_item_id, excise_id=excise_id)
        if not body.get("ex_transaction"):
            results["no_change"].append(tid)
            continue
        try:
            update_fn(pc, office_id, tid, body, access_token=access_token)
        except (urllib.error.URLError, ValueError, OSError) as exc:
            results["errors"].append({"tx_id": tid, "error": _err_str(exc)})
            continue
        # スナップショットを補正後の現値へ更新(再 revise 時に差分ゼロ=冪等。二重 PUT 防止)。
        snap_p.write_text(
            json.dumps(cur.applied(changes).to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        e.mf_status = "revised"
        e.revised_at = now
        e.ex_item, e.excise = draft.ex_item, draft.excise
        e.amount, e.currency, e.jpy_amount = str(draft.amount), draft.currency, draft.jpy_amount
        led.upsert(e)
        notified = _emit_revised_notify(e, change_dicts, send_fn=send_fn)
        results["revised"].append({"tx_id": tid, "changes": change_dicts, "notified": notified})

    led.save(ledger_path())
    return results


# --- 状態・下書き表示 ---------------------------------------------------------------------

def status() -> dict:
    led = ingest.Ledger.load(ledger_path())
    raw_dir = sub(RAW)
    raw_files = [p.name for p in raw_dir.glob("*") if p.is_file() and not p.name.startswith(".")]
    pending = [n for n in raw_files if not sidecar_path(n).is_file()]
    drafts = list(sub(DRAFTS).glob("*.json")) if sub(DRAFTS).is_dir() else []
    past = [e for e in led.entries if e.receipt_id.startswith(PAST_PREFIX)]
    return {
        "ledger_entries": len(led.entries),
        "raw_files": len(raw_files),
        "pending_extract": pending,
        "drafts": len(drafts),
        "past_imported": len([e for e in past if e.mf_status == "imported"]),
        "past_revised": len([e for e in past if e.mf_status == "revised"]),
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
