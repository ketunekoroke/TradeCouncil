"""証憑の抽出結果(`ReceiptFields`)とサイドカー JSON の解釈(zero-dep・純粋)。

Claude(または将来の OpenAI ビジョンブリッジ)が証憑画像/PDF を読んで生成する「抽出サイドカー」
(`var/expense/extracted/<id>.json`)を、型と検証付きの `ReceiptFields` にする。本モジュールは
ネットワーク・ファイル I/O・サードパーティに依存しない(ADR-0011: core は stdlib + 自前のみ)。

サイドカーの形(最小):
  {
    "source_file": "IMG_0001.jpg",        # 取り込んだ元ファイル(raw/ 配下の名前)
    "date": "2026-05-30",                  # 取引日(ISO 8601)
    "payee": "Amazon Web Services",        # 支払先
    "amount": "32.10",                     # 金額(通貨単位。文字列で厳密に持つ)
    "currency": "USD",                     # ISO 4217(既定 JPY)
    "description": "EC2 利用料",            # 取引内容/摘要のもと
    "category_hint": "saas",               # 費目ヒント(任意・Claude の推定)
    "invoice_number": "T1234567890123",    # 適格請求書登録番号(あれば)
    "confidence": 0.9,                      # 抽出全体の確信度(0..1)
    "crop_box": [12, 40, 980, 1400],        # 画像トリミング枠 [left, top, right, bottom] px(任意)
    "fx_rate": "150.20",                   # 外貨時の換算レート(任意・操作者入力)
    "notes": ""
  }
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

SIDECAR_SCHEMA = "ac.expense.extract/v1"


@dataclass
class ReceiptFields:
    """1枚の証憑から抽出した構造化フィールド。金額は文字列で厳密に保持する。"""

    source_file: str
    date: str
    payee: str
    amount: str
    currency: str = "JPY"
    description: str = ""
    category_hint: str = ""
    invoice_number: str | None = None
    confidence: float = 1.0
    crop_box: list[int] | None = None
    fx_rate: str | None = None
    ex_item: str | None = None  # 操作者/Claude が確定した費目(あれば policy が最優先で採用)
    excise: str | None = None  # 操作者/Claude が確定した税区分(あれば最優先)
    attendants: list[int] | None = None  # 接待人数 [自社, 社外](あれば登録に同梱)
    notes: str = ""

    def is_foreign(self) -> bool:
        return (self.currency or "JPY").strip().upper() != "JPY"

    def amount_decimal(self) -> Decimal:
        return Decimal(str(self.amount))

    def fx_rate_decimal(self) -> Decimal | None:
        if self.fx_rate in (None, ""):
            return None
        return Decimal(str(self.fx_rate))

    def to_dict(self) -> dict:
        return {
            "schema": SIDECAR_SCHEMA,
            "source_file": self.source_file,
            "date": self.date,
            "payee": self.payee,
            "amount": str(self.amount),
            "currency": (self.currency or "JPY").strip().upper(),
            "description": self.description,
            "category_hint": self.category_hint,
            "invoice_number": self.invoice_number or None,
            "confidence": self.confidence,
            "crop_box": list(self.crop_box) if self.crop_box else None,
            "fx_rate": self.fx_rate or None,
            "ex_item": self.ex_item or None,
            "excise": self.excise or None,
            "attendants": list(self.attendants) if self.attendants else None,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ReceiptFields:
        if not isinstance(d, dict):
            raise ValueError("サイドカーは JSON オブジェクトである必要があります")
        crop = d.get("crop_box")
        if crop is not None:
            crop = [int(x) for x in crop]
        amount = d.get("amount")
        return cls(
            source_file=str(d.get("source_file") or ""),
            date=str(d.get("date") or ""),
            payee=str(d.get("payee") or ""),
            amount="" if amount is None else str(amount),
            currency=str(d.get("currency") or "JPY").strip().upper(),
            description=str(d.get("description") or ""),
            category_hint=str(d.get("category_hint") or ""),
            invoice_number=(str(d["invoice_number"]) if d.get("invoice_number") else None),
            confidence=float(d.get("confidence", 1.0)),
            crop_box=crop,
            fx_rate=(str(d["fx_rate"]) if d.get("fx_rate") not in (None, "") else None),
            ex_item=(str(d["ex_item"]) if d.get("ex_item") else None),
            excise=(str(d["excise"]) if d.get("excise") else None),
            attendants=([int(x) for x in d["attendants"]] if d.get("attendants") else None),
            notes=str(d.get("notes") or ""),
        )

    def validate(self) -> list[str]:
        """内容の妥当性を検査し、問題の一覧を返す(空なら合格)。登録前ゲートとは別の入口検査。"""
        problems: list[str] = []
        if not self.source_file:
            problems.append("source_file が空です")
        if not self.payee.strip():
            problems.append("payee(支払先)が空です")
        if not _is_iso_date(self.date):
            problems.append(f"date が ISO 形式(YYYY-MM-DD)ではありません: {self.date!r}")
        try:
            if self.amount_decimal() <= 0:
                problems.append(f"amount が正の数ではありません: {self.amount!r}")
        except (InvalidOperation, ValueError):
            problems.append(f"amount を数値として解釈できません: {self.amount!r}")
        cur = (self.currency or "").strip()
        if not (len(cur) == 3 and cur.isalpha()):
            problems.append(f"currency が ISO 4217(英字3桁)ではありません: {self.currency!r}")
        if self.fx_rate not in (None, ""):
            try:
                if (self.fx_rate_decimal() or Decimal(0)) <= 0:
                    problems.append(f"fx_rate が正の数ではありません: {self.fx_rate!r}")
            except (InvalidOperation, ValueError):
                problems.append(f"fx_rate を数値として解釈できません: {self.fx_rate!r}")
        if self.crop_box is not None:
            if len(self.crop_box) != 4:
                problems.append("crop_box は [left, top, right, bottom] の4要素です")
            else:
                left, top, right, bottom = self.crop_box
                if right <= left or bottom <= top:
                    problems.append(f"crop_box の範囲が不正です: {self.crop_box}")
        return problems


def _is_iso_date(value: str) -> bool:
    try:
        datetime.date.fromisoformat(value)
        return True
    except (ValueError, TypeError):
        return False


def parse_sidecar(d: dict) -> ReceiptFields:
    """抽出サイドカー(dict)を `ReceiptFields` にする。構造が壊れていれば ValueError。"""
    return ReceiptFields.from_dict(d)
