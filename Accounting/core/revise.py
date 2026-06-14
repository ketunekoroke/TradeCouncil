"""過去分(クラウド経費 既存明細)の差分判定と PUT 更新ボディ組立(zero-dep・純粋)。

MoneyForward の内蔵 OCR は精度が低く、既存明細の費目・金額・支払先などが誤っている。本モジュールは
「MF の現値(`MFCurrent`)」と「証憑再読込+当期ポリシー適用後のドラフト(`ExpenseDraft`)」を比較し、
**変更フィールドだけ**を `PUT me/ex_transactions/{id}` のボディへ落とす純粋ロジックを提供する。

ネットワーク・I/O・サードパーティに依存しない(ADR-0011: core は stdlib + 自前のみ)。証憑の
バイナリ取得・認証付き PUT・オーケストレーションは `scripts/` 側(mf_expense_api 等)。
`register`(create の権威)は import しない — 摘要/メモは呼び出し側が組み立てて渡す。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation

from core.extract import ReceiptFields
from core.policy import UNDETERMINED, ExpenseDraft
from core.refdata import (
    _EX_ITEM_KEYS,
    _EXCISE_KEYS,
    _PAYEE_KEYS,
    _id_of,
    _label,
)

SNAPSHOT_SCHEMA = "ac.expense.mfcurrent/v1"

# 論理項目 → ExTransactionUpdateInput のキー(単一の真実源)。
PUT_KEY = {
    "date": "recognized_at",
    "ex_item": "ex_item_id",  # 名前で比較し、ID で送る(値は呼び出し側の ex_item_id)
    "excise": "dr_excise_id",  # 同上(dr_excise_id)
    "value": "value",
    "currency": "currency",
    "fx_rate": "jpyrate",
    "invoice_number": "invoice_registration_number",
    "remark": "remark",
    "memo": "memo",
}

_NORM = re.compile(r"[^0-9a-z぀-ヿ一-鿿]+")


def _norm_name(text: str) -> str:
    """費目/税区分名の比較キー(小文字化し記号/空白を除去)。`課税仕入 10%`==`課税仕入10%`。"""
    return _NORM.sub("", (text or "").lower())


def _dec(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _amount_eq(a: object, b: object) -> bool:
    da, db = _dec(a), _dec(b)
    if da is not None and db is not None:
        return da == db
    return str(a or "") == str(b or "")


def _num(value: object) -> int | float:
    """金額/レートを数値へ(整数なら int、端数は float)。MF は value/jpyrate を数値で受ける。"""
    d = Decimal(str(value))
    return int(d) if d == d.to_integral_value() else float(d)


def _text_eq(a: object, b: object) -> bool:
    return str(a or "").strip() == str(b or "").strip()


@dataclass
class MFCurrent:
    """クラウド経費の既存明細(MF 現値)。差分の基準。`raw` は取得した生 dict。"""

    tx_id: str
    number: str | None
    date: str
    payee: str
    ex_item: str | None  # 名前
    excise: str | None  # 名前
    value: str
    currency: str
    fx_rate: str | None
    invoice_number: str | None
    remark: str | None
    memo: str | None
    receipt_type: str | None
    has_file: bool
    raw: dict

    @classmethod
    def from_tx(cls, tx: dict) -> MFCurrent:
        """`me/ex_transactions` の1件(dict)を MFCurrent にする(refdata と同じキー語彙で吸収)。"""
        mf_file = tx.get("mf_file")
        return cls(
            tx_id=str(tx.get("id") or ""),
            number=(str(tx["number"]) if tx.get("number") is not None else None),
            date=str(tx.get("recognized_at") or tx.get("date") or "")[:10],
            payee=_label(tx, _PAYEE_KEYS),
            ex_item=_label(tx, _EX_ITEM_KEYS) or None,
            excise=_label(tx, _EXCISE_KEYS) or None,
            value=("" if tx.get("value") is None else str(tx.get("value"))),
            currency=str(tx.get("currency") or "JPY").upper(),
            fx_rate=(str(tx["jpyrate"]) if tx.get("jpyrate") not in (None, "") else None),
            invoice_number=(
                str(tx["invoice_registration_number"])
                if tx.get("invoice_registration_number")
                else None
            ),
            remark=(str(tx["remark"]) if tx.get("remark") else None),
            memo=(str(tx["memo"]) if tx.get("memo") else None),
            receipt_type=(str(tx["receipt_type"]) if tx.get("receipt_type") else None),
            has_file=isinstance(mf_file, dict) and bool(mf_file.get("id") or mf_file.get("name")),
            raw=tx,
        )

    def ex_item_id(self) -> str:
        return _id_of(self.raw, "ex_item", "ex_item_id")

    def applied(self, changes: list[FieldChange]) -> MFCurrent:
        """補正(PUT)後の現値を反映した新しい MFCurrent を返す(スナップショット更新用)。

        `FieldChange.field` は MFCurrent の属性名と一致する。再 revise 時に差分ゼロ=冪等。
        """
        updates: dict = {}
        for c in changes:
            updates[c.field] = str(c.after) if c.field == "value" else c.after
        return replace(self, **updates)

    def to_dict(self) -> dict:
        return {
            "schema": SNAPSHOT_SCHEMA,
            "tx_id": self.tx_id,
            "number": self.number,
            "date": self.date,
            "payee": self.payee,
            "ex_item": self.ex_item,
            "excise": self.excise,
            "value": self.value,
            "currency": self.currency,
            "fx_rate": self.fx_rate,
            "invoice_number": self.invoice_number,
            "remark": self.remark,
            "memo": self.memo,
            "receipt_type": self.receipt_type,
            "has_file": self.has_file,
            "raw": self.raw,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MFCurrent:
        # 補正後にスナップショットを更新する(applied)ため、保存した上位フィールドを正とする
        # (raw は監査用に保持。再構築には使わない)。
        return cls(
            tx_id=str(d.get("tx_id") or ""),
            number=d.get("number"),
            date=str(d.get("date") or ""),
            payee=str(d.get("payee") or ""),
            ex_item=d.get("ex_item"),
            excise=d.get("excise"),
            value=str(d.get("value") or ""),
            currency=str(d.get("currency") or "JPY"),
            fx_rate=d.get("fx_rate"),
            invoice_number=d.get("invoice_number"),
            remark=d.get("remark"),
            memo=d.get("memo"),
            receipt_type=d.get("receipt_type"),
            has_file=bool(d.get("has_file")),
            raw=dict(d.get("raw") or {}),
        )

    def to_receipt_fields(self) -> ReceiptFields:
        """サイドカー(Claude 再読込)が無い明細の policy-only 補正用に、MF 現値から事実を組む。

        費目/税区分は **確定値として持たせない**(None)— 当期ポリシーで再導出させるため。外貨レートは
        現値を引き継ぐ(操作者がサイドカーで正値を与えなければレートは変えない)。
        """
        return ReceiptFields(
            source_file=f"past_{self.tx_id}",
            date=self.date,
            payee=self.payee,
            amount=self.value or "0",
            currency=self.currency,
            description=self.remark or "",
            invoice_number=self.invoice_number,
            fx_rate=self.fx_rate,
        )


@dataclass
class FieldChange:
    """1フィールドの変更(MF 現値 before → 提案 after)。`put_key` は更新入力のキー。"""

    field: str
    put_key: str
    before: object
    after: object

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "put_key": self.put_key,
            "before": self.before,
            "after": self.after,
        }


def diff_entry(
    current: MFCurrent,
    draft: ExpenseDraft,
    fields: ReceiptFields,
    *,
    ex_item_id: str | None,
    excise_id: str | None,
    proposed_remark: str | None,
    proposed_memo: str | None,
    rewrite_remark: bool = False,
) -> list[FieldChange]:
    """MF 現値とポリシー適用後ドラフトを比較し、**変更されたフィールドだけ**を返す。

    費目/税区分は名前で比較し ID で送る(ID 未解決 / 未確定は変更対象にしない=PUT できない)。
    金額/レートは Decimal 比較、名前は正規化比較、テキストは trim 比較で誤差分を避ける。
    remark は既定で温存し `rewrite_remark=True` のときだけ比較する(既存 remark を保つ)。
    """
    changes: list[FieldChange] = []

    if not _text_eq(current.date, draft.date) and draft.date:
        changes.append(FieldChange("date", PUT_KEY["date"], current.date, draft.date))

    if (
        draft.ex_item
        and draft.ex_item != UNDETERMINED
        and ex_item_id
        and _norm_name(current.ex_item or "") != _norm_name(draft.ex_item)
    ):
        changes.append(FieldChange("ex_item", PUT_KEY["ex_item"], current.ex_item, draft.ex_item))

    if (
        draft.excise
        and draft.excise != UNDETERMINED
        and excise_id
        and _norm_name(current.excise or "") != _norm_name(draft.excise)
    ):
        changes.append(FieldChange("excise", PUT_KEY["excise"], current.excise, draft.excise))

    if not _amount_eq(current.value, draft.amount):
        changes.append(FieldChange("value", PUT_KEY["value"], current.value, str(draft.amount)))

    if (current.currency or "JPY").upper() != (draft.currency or "JPY").upper():
        changes.append(
            FieldChange("currency", PUT_KEY["currency"], current.currency, draft.currency)
        )

    if draft.fx_rate and not _amount_eq(current.fx_rate, draft.fx_rate):
        changes.append(FieldChange("fx_rate", PUT_KEY["fx_rate"], current.fx_rate, draft.fx_rate))

    if draft.invoice_number and not _text_eq(current.invoice_number, draft.invoice_number):
        changes.append(FieldChange(
            "invoice_number", PUT_KEY["invoice_number"],
            current.invoice_number, draft.invoice_number,
        ))

    if proposed_memo and not _text_eq(current.memo, proposed_memo):
        changes.append(FieldChange("memo", PUT_KEY["memo"], current.memo, proposed_memo))

    if rewrite_remark and proposed_remark and not _text_eq(current.remark, proposed_remark):
        changes.append(FieldChange("remark", PUT_KEY["remark"], current.remark, proposed_remark))

    return changes


def build_update_body(
    changes: list[FieldChange], *, ex_item_id: str | None = None, excise_id: str | None = None
) -> dict:
    """変更フィールドだけの `{"ex_transaction": {...}}` を組む(部分更新)。

    費目/税区分は ID を送る(`ex_item_id`/`excise_id`)。為替変更は `jpyrate` に加え
    `use_custom_jpy_rate=True` を併送する。金額/レートは数値化。空なら `{"ex_transaction": {}}`
    (呼び出し側が skip)。`receipt_input` は付けない(再アップロード=再 OCR を避ける)。
    """
    body: dict = {}
    for ch in changes:
        if ch.put_key == "ex_item_id":
            if ex_item_id:
                body["ex_item_id"] = ex_item_id
        elif ch.put_key == "dr_excise_id":
            if excise_id:
                body["dr_excise_id"] = excise_id
        elif ch.put_key == "jpyrate":
            body["jpyrate"] = _num(ch.after)
            body["use_custom_jpy_rate"] = True
        elif ch.put_key == "value":
            body["value"] = _num(ch.after)
        else:
            body[ch.put_key] = ch.after
    return {"ex_transaction": body}
