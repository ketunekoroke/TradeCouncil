"""経費明細ドラフトの生成(zero-dep・純粋)。クラウド経費 API 形に近い dict + 人可読要約。

**この段階では実 API 書込はしない**(下書きのみ — 決定 2026-06-14)。実登録はクラウド経費 REST
(`POST .../me/upload_receipt` / `me/ex_transactions`、`transaction:write`)で別途行う。
ここで作る dict はリクエスト本体に近い形。項目名は登録実装で確定する。秘匿値は持たせない。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal

from core.extract import ReceiptFields
from core.gate import Issue
from core.policy import ExpenseDraft

DRAFT_SCHEMA = "ac.expense.draft/v1"


@dataclass
class ReceiptRef:
    """下書きが指す証憑ファイル(SharePoint master 上の名前)。"""

    processed_file: str = ""
    original_file: str | None = None
    content_hash: str = ""
    source_file: str = ""


def build_expense_draft(
    draft: ExpenseDraft,
    fields: ReceiptFields,
    *,
    receipt: ReceiptRef | None = None,
    issues: list[Issue] | None = None,
) -> dict:
    """レビュー可能な経費明細下書き(dict)を組み立てる。

    `ex_transaction` ブロックはクラウド経費 `me/ex_transactions` の登録本体に近い形
    (項目名は登録実装で確定)。摘要(remark)には相関キーを必ず載せる。
    """
    receipt = receipt or ReceiptRef(source_file=fields.source_file)
    remark = _remark(draft)
    foreign = fields.is_foreign()
    # MF 実機スキーマ準拠: value=原通貨額・currency=原通貨・jpyrate で円換算は MF 側。
    ex_transaction = {
        "recognized_at": draft.date,  # 取引日(MF の項目名は登録時に確定)
        "ex_item_name": None if draft.ex_item in ("", "未確定") else draft.ex_item,
        "excise_name": None if draft.excise in ("", "未確定") else draft.excise,
        "value": str(draft.amount) if foreign else (draft.jpy_amount or str(draft.amount)),
        "currency": draft.currency if foreign else "JPY",
        "jpy_rate": draft.fx_rate,  # 外貨のとき MF jpyrate 相当(円/通貨)
        "jpy_value": draft.jpy_amount,  # 円換算(税込。国内は value と同じ)
        "remark": remark,  # 摘要(相関キーを含む)
        "number": draft.invoice_number,  # 登録番号(あれば)
    }
    return {
        "schema": DRAFT_SCHEMA,
        "correlation_key": draft.correlation_key,
        "status": "draft",  # draft → (確認後) registered
        "receipt": {
            "source_file": receipt.source_file,
            "processed_file": receipt.processed_file,
            "original_file": receipt.original_file,
            "content_hash": receipt.content_hash,
        },
        "ex_transaction": ex_transaction,
        "policy": {
            "payee": draft.payee,
            "description": draft.description,
            "amount": str(draft.amount),
            "currency": draft.currency,
            "jpy_amount": draft.jpy_amount,
            "fx_rate": draft.fx_rate,
            "domestic": draft.domestic,
            "ex_item": draft.ex_item,
            "excise": draft.excise,
            "flags": list(draft.flags),
            "basis": dict(draft.basis),
        },
        "gate": [i.to_dict() for i in (issues or [])],
        "confidence": draft.confidence,
        "_note": "下書き。実登録はクラウド経費 REST(transaction:write)で確認後に行う。",
    }


def _remark(draft: ExpenseDraft) -> str:
    """摘要(支払先・内容)を組み立てる: **店名/支払先を先頭** + 内容 + 相関キー。"""
    parts = [draft.payee.strip()]
    if draft.description.strip():
        parts.append(draft.description.strip())
    parts.append(f"[{draft.correlation_key}]")
    return " ".join(p for p in parts if p)


def fx_memo(
    draft: ExpenseDraft, *, rate_source: str | None = None, base_rule: str | None = None
) -> str | None:
    """外貨明細の memo(為替レート適用の記録)。JPY / レート無は None。"""
    if not draft.fx_rate or (draft.currency or "JPY").upper() == "JPY":
        return None
    src = rate_source or "レート源未設定"
    basis = "前月末仲値を当月適用" if base_rule == "prev_month_end_ttm" else (base_rule or "")
    tail = f"・{basis}" if basis else ""
    return f"為替: 1 {draft.currency} = {draft.fx_rate}円({src}{tail})。円換算 ¥{draft.jpy_amount}"


def to_json(draft_dict: dict) -> str:
    return json.dumps(draft_dict, ensure_ascii=False, indent=2)


def to_summary(draft_dict: dict) -> str:
    """人が読む1件サマリ(ターミナル表示・秘匿値なし)。"""
    p = draft_dict.get("policy", {})
    ex = draft_dict.get("ex_transaction", {})
    gate = draft_dict.get("gate", [])
    errors = [g for g in gate if g.get("level") == "error"]
    head = f"{p.get('payee', '?')} / {p.get('amount', '?')} {p.get('currency', '')}"
    jpy = p.get("jpy_amount")
    money = f"¥{jpy}" if jpy else "(円換算なし)"
    lines = [
        f"- {ex.get('recognized_at', '?')}  {head}  → {money}",
        f"    費目: {p.get('ex_item')}   税区分: {p.get('excise')}",
        f"    相関キー: {draft_dict.get('correlation_key')}",
    ]
    if p.get("flags"):
        lines.append("    フラグ: " + " / ".join(p["flags"]))
    if errors:
        lines.append("    ❌ " + " / ".join(g["message"] for g in errors))
    return "\n".join(lines)


CSV_COLUMNS = (
    "correlation_key",
    "date",
    "payee",
    "ex_item",
    "excise",
    "amount",
    "currency",
    "jpy_amount",
    "status",
)


def _num(value: object) -> int | float:
    """金額/レートを数値へ(整数なら int、端数があれば float)。"""
    d = Decimal(str(value))
    return int(d) if d == d.to_integral_value() else float(d)


def build_ex_transaction_create(
    draft: ExpenseDraft,
    fields: ReceiptFields,
    *,
    ex_item_id: str,
    dr_excise_id: str | None = None,
    receipt_content_b64: str | None = None,
    content_type: str | None = None,
    filename: str | None = None,
    attendants: tuple[int, int] | None = None,  # (own_count, other_count)
    memo: str | None = None,  # メモ欄(為替レート適用など)
) -> dict:
    """クラウド経費 `POST me/ex_transactions` の本体 `{"ex_transaction": {...}}` を組み立てる。

    `receipt_*` を渡すと `receipt_input`(証憑画像 base64)を同梱 — **1コールで登録 + 証憑添付**
    (CSV 取込では不可・電帳法対応)。value は原通貨額(数値)、外貨は jpyrate + use_custom_jpy_rate。
    費目は `ex_item_id` 必須(空なら ValueError)。摘要には相関キーを載せる。
    """
    if not ex_item_id:
        raise ValueError("ex_item_id(費目ID)が必要です — refdata の名前→ID マップで解決")
    foreign = fields.is_foreign()
    ex: dict = {
        "recognized_at": draft.date,
        "value": _num(draft.amount),
        "currency": draft.currency if foreign else "JPY",
        "remark": _remark(draft),
        "ex_item_id": ex_item_id,
    }
    if dr_excise_id:
        ex["dr_excise_id"] = dr_excise_id
    if foreign and draft.fx_rate:
        ex["jpyrate"] = _num(draft.fx_rate)
        ex["use_custom_jpy_rate"] = True
    if draft.invoice_number:
        ex["invoice_registration_number"] = draft.invoice_number
    if memo:
        ex["memo"] = memo
    if attendants is not None:
        own, other = attendants
        ex["ex_transaction_attendant_count_attributes"] = {
            "own_count": int(own),
            "other_count": int(other),
        }
    if receipt_content_b64 and content_type and filename:
        ex["receipt_input"] = {
            "content": receipt_content_b64,
            "content_type": content_type,
            "filename": filename,
        }
    return {"ex_transaction": ex}


def to_csv_row(draft_dict: dict) -> list[str]:
    """1件を CSV 行(`CSV_COLUMNS` 順)にする。"""
    p = draft_dict.get("policy", {})
    ex = draft_dict.get("ex_transaction", {})
    values = {
        "correlation_key": draft_dict.get("correlation_key", ""),
        "date": ex.get("recognized_at", ""),
        "payee": p.get("payee", ""),
        "ex_item": p.get("ex_item", ""),
        "excise": p.get("excise", ""),
        "amount": p.get("amount", ""),
        "currency": p.get("currency", ""),
        "jpy_amount": p.get("jpy_amount") or "",
        "status": draft_dict.get("status", ""),
    }
    return [str(values[c]) for c in CSV_COLUMNS]
