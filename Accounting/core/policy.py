"""会計ポリシーの機械適用(zero-dep・純粋・dict 注入)。

会計の判断方針の正本は docs/accounting-policy.md。本モジュールは「機械的に当てられる部分」だけを、
注入された設定(前期実績 `UsageIndex`・`fx_rule`・任意の手動 override)に基づいて適用する:

  - 費目(ex_item)/ 税区分(excise): 前期実績のサジェスト(override があれば優先)
  - 内外判定: 外貨/海外ヒントは自動確定せずフラグ(国際課税の最終判断は税理士 — company-specific.md)
  - 外貨換算: 取引日レートで円換算(レート未入力ならフラグ。継続適用・源泉妥当性は税理士確認)
  - 相関キー / 摘要: 後段の会計連携で突合するキーを摘要に載せる

**確定できないものは推測で確定せず `未確定` としてフラグ**(accounts.yaml の方針)。会計の勘定科目は
扱わない(クラウド経費 → 会計登録時に MF が自動変換)。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from core.extract import ReceiptFields
from core.refdata import Suggestion, UsageIndex

UNDETERMINED = "未確定"
DRAFT_SCHEMA = "ac.expense.policy/v1"

# 海外取引(国外消費=対象外/不課税)を疑うヒント。確定はしない(フラグのみ)。
_OVERSEAS_HINTS = ("海外", "国外", "overseas", "abroad", "foreign")


@dataclass
class ExpenseDraft:
    """ポリシー適用後の経費明細ドラフト(クラウド経費の語彙)。"""

    date: str
    payee: str
    description: str
    ex_item: str  # 費目(未確定なら UNDETERMINED)
    excise: str  # 税区分(未確定なら UNDETERMINED)
    amount: str  # 原通貨の金額
    currency: str
    jpy_amount: str | None  # 円換算(JPY はそのまま整数、外貨はレート換算)
    fx_rate: str | None
    domestic: bool | None  # True=国内 / None=要確認(自動確定しない)
    correlation_key: str
    invoice_number: str | None = None
    confidence: float = 0.0
    flags: list[str] = field(default_factory=list)
    basis: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "schema": DRAFT_SCHEMA,
            "date": self.date,
            "payee": self.payee,
            "description": self.description,
            "ex_item": self.ex_item,
            "excise": self.excise,
            "amount": str(self.amount),
            "currency": self.currency,
            "jpy_amount": self.jpy_amount,
            "fx_rate": self.fx_rate,
            "domestic": self.domestic,
            "correlation_key": self.correlation_key,
            "invoice_number": self.invoice_number,
            "confidence": self.confidence,
            "flags": list(self.flags),
            "basis": dict(self.basis),
        }


def correlation_key(date: str, token: str) -> str:
    """摘要に載せる相関キー `AC-<yyyymm>-<token8>`。会計連携で mf_journal_id と突合する。"""
    yyyymm = (date or "")[:7].replace("-", "")
    return f"AC-{yyyymm}-{token[:8]}"


def _override_ex_item(text: str, overrides: list[dict] | None) -> str | None:
    """手動 override をキーワード一致で当てる(accounts.yaml 由来の {match, ex_item|account})。"""
    if not overrides:
        return None
    low = (text or "").lower()
    for rule in overrides:
        match = rule.get("match") or []
        if any(str(kw).lower() in low for kw in match):
            return rule.get("ex_item") or rule.get("account") or None
    return None


def _to_jpy(amount: Decimal, rate: Decimal) -> str:
    """外貨額 × レート → 円(整数・四捨五入)。"""
    return str((amount * rate).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def apply_policy(
    fields: ReceiptFields,
    *,
    usage: UsageIndex | None = None,
    fx_rule: dict | None = None,
    fx_rate: str | None = None,
    overrides: list[dict] | None = None,
    receipt_hash: str | None = None,
) -> ExpenseDraft:
    """`ReceiptFields` にポリシーを当てて `ExpenseDraft` を作る(純粋)。

    費目/税区分は override → 前期実績サジェスト の順。確定できなければ `未確定`。
    外貨はレートで円換算(レート無はフラグ)。内外判定は自動確定せず要確認フラグを立てる。
    """
    fx_rule = fx_rule or {}
    flags: list[str] = []
    basis: dict = {}
    text = " ".join([fields.payee, fields.description, fields.category_hint]).strip()

    # --- 費目・税区分(確定値 → override → 前期実績 → 未確定)---
    suggestion = usage.suggest(fields.payee, fields.description) if usage else Suggestion()
    if fields.ex_item:
        ex_item = fields.ex_item
        basis["ex_item"] = "confirmed"
    elif ov := _override_ex_item(text, overrides):
        ex_item = ov
        basis["ex_item"] = "override"
    elif suggestion.ex_item:
        ex_item = suggestion.ex_item
        basis["ex_item"] = suggestion.basis
    else:
        ex_item = UNDETERMINED
        basis["ex_item"] = "none"
        flags.append("費目を実績から特定できません(未確定 → 要確認)")

    if fields.excise:
        excise = fields.excise
        basis["excise"] = "confirmed"
    elif suggestion.excise:
        excise = suggestion.excise
        basis["excise"] = suggestion.basis
    else:
        excise = UNDETERMINED
        flags.append("税区分を実績から特定できません(未確定 → 要確認)")

    # --- 内外判定(自動確定しない)---
    overseas_hint = any(h in text.lower() for h in _OVERSEAS_HINTS)
    if fields.is_foreign() or overseas_hint:
        domestic: bool | None = None
        flags.append("内外判定が要確認です(国外消費なら対象外/不課税。company-specific.md)")
    else:
        domestic = True

    # --- 外貨換算 ---
    if not fields.is_foreign():
        jpy = _normalize_jpy(fields.amount)
        rate_str = None
    else:
        rate_dec = _parse_decimal(fx_rate) or fields.fx_rate_decimal()
        rate_str = str(rate_dec) if rate_dec is not None else None
        amount_dec = _parse_decimal(fields.amount)
        if rate_dec is not None and amount_dec is not None:
            jpy = _to_jpy(amount_dec, rate_dec)
            basis["fx"] = fx_rule.get("base_rule") or "ttm_trade_date"
            src = fx_rule.get("rate_source")
            flags.append(
                "外貨換算: レート源の継続適用・税務妥当性は税理士確認"
                + (f"(源: {src})" if src else "(源: 未設定)")
            )
        else:
            jpy = None
            flags.append(f"外貨レート未入力のため円換算できません({fields.currency})")

    # --- 相関キー ---
    token = (receipt_hash or hashlib.sha256(
        f"{fields.date}|{fields.payee}|{fields.amount}".encode()
    ).hexdigest())
    corr = correlation_key(fields.date, token)

    confidence = round(min(fields.confidence, suggestion.confidence or fields.confidence), 3)
    if ex_item == UNDETERMINED:
        confidence = min(confidence, 0.3)

    return ExpenseDraft(
        date=fields.date,
        payee=fields.payee,
        description=fields.description,
        ex_item=ex_item,
        excise=excise,
        amount=str(fields.amount),
        currency=(fields.currency or "JPY").upper(),
        jpy_amount=jpy,
        fx_rate=rate_str,
        domestic=domestic,
        correlation_key=corr,
        invoice_number=fields.invoice_number,
        confidence=confidence,
        flags=flags,
        basis=basis,
    )


def _parse_decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _normalize_jpy(amount: object) -> str:
    """JPY 金額を整数文字列へ(端数があれば四捨五入)。"""
    dec = _parse_decimal(amount)
    if dec is None:
        return str(amount)
    return str(dec.quantize(Decimal(1), rounding=ROUND_HALF_UP))
