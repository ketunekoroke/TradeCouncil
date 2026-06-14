"""取り込み: 内容ハッシュ・リネーム規則・重複判定・処理台帳(zero-dep・純粋寄り)。

ファイル I/O は標準ライブラリ(hashlib/pathlib/json/os)のみ。SharePoint 転送・画像トリミングは
`scripts/` 側(shared / Pillow)に置く(ADR-0011: core は stdlib + 自前のみ)。

台帳(`var/expense/ledger.json`)は処理済み証憑の索引で、重複検知(内容ハッシュ完全一致 / 日付+支払先+
金額の近接)と上書き履歴(supersede)を担う。秘匿性のある生値(口座番号等)は持たせない。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

# Windows / SharePoint で使えないファイル名文字。
_ILLEGAL = set('\\/:*?"<>|')
# 支払先の正規化(近接重複の突合キー): 英字小文字化し英数字以外を除去。
_NORM_STRIP = re.compile(r"[^0-9a-z぀-ヿ一-鿿]+")


def content_hash(path: str | Path, *, chunk: int = 65536) -> str:
    """ファイル内容の SHA-256(16進)。完全同一ファイルの再投入を検知する。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def sanitize_payee(name: str, *, max_len: int = 40) -> str:
    """支払先をファイル名に使える形へ。禁止文字・制御文字を除去し、空白を1つに畳む。

    Windows は末尾のドット/空白を許さないため除去する。空になったら 'unknown'。日本語は保持する。
    """
    s = "".join(ch for ch in (name or "") if ch not in _ILLEGAL and ord(ch) >= 32)
    s = " ".join(s.split())  # 連続空白を1つに
    s = s[:max_len].rstrip(" .")
    return s or "unknown"


def norm_payee(name: str) -> str:
    """近接重複の突合キー(表示は変えない)。小文字化し記号/空白を除去。"""
    return _NORM_STRIP.sub("", (name or "").lower())


def build_filename(
    date: str, payee: str, ext: str, *, original: bool = False, dedup_suffix: str = ""
) -> str:
    """`YYYY-MM-DD_<支払先>.<ext>` を組み立てる。原本は末尾に `_original`。

    `dedup_suffix` は同名衝突時の識別子(短ハッシュ等)を `_` 区切りで挿入する。
    """
    ext = (ext or "").lower().lstrip(".")
    base = f"{date}_{sanitize_payee(payee)}"
    if dedup_suffix:
        base += f"_{dedup_suffix}"
    if original:
        base += "_original"
    return f"{base}.{ext}" if ext else base


def make_receipt_id(date: str, payee: str, content_hash_hex: str) -> str:
    """台帳・下書き・サイドカーで使う安定 ID。"""
    return f"{date}_{sanitize_payee(payee)}_{content_hash_hex[:8]}"


def _amounts_equal(a: str, b: str) -> bool:
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except (InvalidOperation, ValueError):
        return str(a) == str(b)


@dataclass
class LedgerEntry:
    """処理済み証憑1件の索引。生の証憑内容は持たない(件名/金額等のメタのみ)。"""

    receipt_id: str
    content_hash: str
    date: str
    payee: str
    amount: str
    currency: str = "JPY"
    source_file: str = ""  # 取り込み元(SharePoint inbox 上のファイル名)
    filename: str = ""  # 処理後の主ファイル名(SharePoint master 上)
    original_filename: str | None = None
    ex_item: str | None = None  # 費目
    excise: str | None = None  # 税区分
    jpy_amount: str | None = None
    correlation_key: str = ""
    draft_path: str | None = None
    mf_status: str = "draft"  # draft | registered
    mf_transaction_id: str | None = None  # 登録後の MF 明細 ID(内部)
    mf_number: str | None = None  # 登録後の MF 明細番号(WEB 表示)
    created_at: str | None = None  # ISO(呼び出し側が付与。core は now を持たない)
    superseded: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "receipt_id": self.receipt_id,
            "content_hash": self.content_hash,
            "date": self.date,
            "payee": self.payee,
            "amount": str(self.amount),
            "currency": self.currency,
            "source_file": self.source_file,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "ex_item": self.ex_item,
            "excise": self.excise,
            "jpy_amount": self.jpy_amount,
            "correlation_key": self.correlation_key,
            "draft_path": self.draft_path,
            "mf_status": self.mf_status,
            "mf_transaction_id": self.mf_transaction_id,
            "mf_number": self.mf_number,
            "created_at": self.created_at,
            "superseded": list(self.superseded),
        }

    @classmethod
    def from_dict(cls, d: dict) -> LedgerEntry:
        return cls(
            receipt_id=str(d.get("receipt_id") or ""),
            content_hash=str(d.get("content_hash") or ""),
            date=str(d.get("date") or ""),
            payee=str(d.get("payee") or ""),
            amount=str(d.get("amount") or ""),
            currency=str(d.get("currency") or "JPY"),
            source_file=str(d.get("source_file") or ""),
            filename=str(d.get("filename") or ""),
            original_filename=d.get("original_filename") or None,
            ex_item=d.get("ex_item") or None,
            excise=d.get("excise") or None,
            jpy_amount=d.get("jpy_amount") or None,
            correlation_key=str(d.get("correlation_key") or ""),
            draft_path=d.get("draft_path") or None,
            mf_status=str(d.get("mf_status") or "draft"),
            mf_transaction_id=d.get("mf_transaction_id") or None,
            mf_number=d.get("mf_number") or None,
            created_at=d.get("created_at") or None,
            superseded=list(d.get("superseded") or []),
        )


@dataclass
class Ledger:
    """処理台帳。`load`/`save` は JSON。重複検知と上書き履歴を提供する。"""

    path: Path | None = None
    entries: list[LedgerEntry] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> Ledger:
        p = Path(path)
        if not p.is_file():
            return cls(path=p, entries=[])
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return cls(path=p, entries=[])
        entries = [LedgerEntry.from_dict(e) for e in (data.get("entries") or [])]
        return cls(path=p, entries=entries)

    def save(self, path: str | Path | None = None) -> Path:
        p = Path(path or self.path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema": "ac.expense.ledger/v1", "entries": [e.to_dict() for e in self.entries]}
        tmp = p.parent / (p.name + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, p)
        return p

    def by_hash(self, content_hash_hex: str) -> LedgerEntry | None:
        for e in self.entries:
            if e.content_hash and e.content_hash == content_hash_hex:
                return e
        return None

    def find_similar(
        self, date: str, payee: str, amount: str, currency: str = "JPY"
    ) -> list[LedgerEntry]:
        """同一の取引(日付+支払先+金額+通貨)に見える既存エントリ。内容ハッシュは問わない。"""
        key = norm_payee(payee)
        out = []
        for e in self.entries:
            if (
                e.date == date
                and norm_payee(e.payee) == key
                and (e.currency or "JPY") == (currency or "JPY")
                and _amounts_equal(e.amount, amount)
            ):
                out.append(e)
        return out

    def upsert(self, entry: LedgerEntry) -> None:
        for i, e in enumerate(self.entries):
            if e.receipt_id == entry.receipt_id:
                self.entries[i] = entry
                return
        self.entries.append(entry)

    def supersede(self, old: LedgerEntry, new: LedgerEntry, *, at: str | None = None) -> None:
        """`old` を `new` で置き換え、上書き履歴を `new.superseded` に残す(削除はしない発想)。"""
        new.superseded = list(old.superseded) + [
            {
                "content_hash": old.content_hash,
                "filename": old.filename,
                "amount": old.amount,
                "at": at,
            }
        ]
        replaced = False
        for i, e in enumerate(self.entries):
            if e.receipt_id == old.receipt_id:
                self.entries[i] = new
                replaced = True
                break
        if not replaced:
            self.entries.append(new)


def find_duplicate(
    content_hash_hex: str,
    date: str,
    payee: str,
    amount: str,
    currency: str,
    ledger: Ledger,
) -> tuple[str | None, LedgerEntry | None]:
    """重複種別を返す: ('exact', entry) / ('similar', entry) / (None, None)。

    - exact   : 内容ハッシュ完全一致(同じファイルの再投入)。
    - similar : 日付+支払先+金額+通貨が一致(撮り直し等。上書き承認の対象)。
    """
    exact = ledger.by_hash(content_hash_hex)
    if exact is not None:
        return "exact", exact
    similar = ledger.find_similar(date, payee, amount, currency)
    if similar:
        return "similar", similar[0]
    return None, None
