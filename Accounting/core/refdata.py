"""前期実績(クラウド経費 me/ex_transactions)から費目・税区分の使用実績を集計(zero-dep・純粋)。

`scripts/mf_expense_api.py` が取得した経費明細(dict のリスト)を注入し、「取引先/キーワード →
よく使う費目・税区分」の索引(`UsageIndex`)を作る。ネットワーク・I/O・サードパーティに依存しない。

会計の勘定科目は扱わない(クラウド経費で承認→会計登録時に MF がマトリクスで自動変換するため)。
本パイプラインの語彙は **経費の費目(ex_item)・税区分(excise)** に閉じる(設計決定 2026-06-14)。

明細の項目名は API/バージョンで揺れるため、候補キーで吸収する(`{"id":..,"name":..}` のネストも可)。
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

# 経費明細から各要素を取り出す候補キー(先頭から順に試す)。実機スキーマ(MF 経費)で確認:
#   費目=ex_item.name / 税区分=dr_excise.long_name / 取引先・店名=remark(専用フィールドなし)。
_EX_ITEM_KEYS = ("ex_item", "ex_item_name", "item", "item_name")
_EXCISE_KEYS = ("dr_excise", "excise", "excise_name", "tax", "tax_name", "tax_type")
_PAYEE_KEYS = ("partner_name", "partner", "remark", "dr_name", "recipient", "supplier", "payee")
_DESC_KEYS = ("remark", "memo", "name", "note", "description")

_TOKEN = re.compile(r"[0-9a-z]{2,}|[぀-ヿ一-鿿]+")
_NORM = re.compile(r"[^0-9a-z぀-ヿ一-鿿]+")

USAGE_SCHEMA = "ac.expense.usage/v1"


def _label(d: dict, keys: tuple[str, ...]) -> str:
    """候補キーから表示ラベルを取り出す。値が `{"id":..,"name":..}` なら name を使う。"""
    for k in keys:
        v = d.get(k)
        if isinstance(v, dict):
            name = v.get("name") or v.get("long_name") or v.get("label")
            if name:
                return str(name).strip()
        elif isinstance(v, (str, int)) and str(v).strip():
            return str(v).strip()
    return ""


def _id_of(d: dict, dict_key: str, id_key: str) -> str:
    """明細から ID を取り出す。`<dict_key>.id` を優先し、無ければ top-level `<id_key>`。"""
    v = d.get(dict_key)
    if isinstance(v, dict) and v.get("id"):
        return str(v["id"])
    if d.get(id_key):
        return str(d[id_key])
    return ""


def _norm(text: str) -> str:
    return _NORM.sub("", (text or "").lower())


def _tokens(*texts: str) -> list[str]:
    out: list[str] = []
    for t in texts:
        out.extend(_TOKEN.findall((t or "").lower()))
    return out


@dataclass
class Suggestion:
    """1件のレシートに対する費目・税区分の推定(根拠つき)。確証が無ければ None。"""

    ex_item: str | None = None
    excise: str | None = None
    confidence: float = 0.0
    basis: str = ""


@dataclass
class UsageIndex:
    """前期実績から作る費目/税区分の使用索引。取引先一致 → キーワード一致 の順で推定する。"""

    n: int = 0
    by_payee: dict[str, dict] = field(default_factory=dict)  # norm_payee→{label,ex_item,excise}
    by_token: dict[str, dict] = field(default_factory=dict)  # token→{ex_item,excise}
    ex_item_totals: dict[str, int] = field(default_factory=dict)
    excise_totals: dict[str, int] = field(default_factory=dict)
    ex_item_ids: dict[str, str] = field(default_factory=dict)  # 費目名→ID(登録用)
    excise_ids: dict[str, str] = field(default_factory=dict)  # 税区分名→ID(登録用)

    def ex_item_id(self, name: str) -> str | None:
        return self.ex_item_ids.get(name)

    def excise_id(self, name: str) -> str | None:
        return self.excise_ids.get(name)

    def merge_ids(
        self,
        *,
        ex_item_ids: dict[str, str] | None = None,
        excise_ids: dict[str, str] | None = None,
    ) -> dict[str, int]:
        """マスタ由来の name→ID を取り込む(登録時の ID 解決用)。

        **学習済みの対応は上書きしない**(実績の方が現場の使い分けに忠実なため)。新規追加した
        件数を返す。前期実績に出ない費目(支払手数料 等)・税区分(課税仕入 8% 等)を解決可能にする。
        """
        added = {"ex_item": 0, "excise": 0}
        for name, rid in (ex_item_ids or {}).items():
            if name and rid and name not in self.ex_item_ids:
                self.ex_item_ids[name] = str(rid)
                added["ex_item"] += 1
        for name, rid in (excise_ids or {}).items():
            if name and rid and name not in self.excise_ids:
                self.excise_ids[name] = str(rid)
                added["excise"] += 1
        return added

    def suggest(self, payee: str, description: str = "") -> Suggestion:
        """取引先(優先)→ キーワード重なり の順で費目・税区分を推定する。"""
        key = _norm(payee)
        bucket = self.by_payee.get(key)
        if bucket:
            ex, exc = bucket.get("ex_item", {}), bucket.get("excise", {})
            ei, ei_conf = _top(ex)
            xi, _ = _top(exc)
            return Suggestion(ex_item=ei, excise=xi, confidence=ei_conf, basis=f"payee:{payee}")

        # キーワード(取引先+摘要のトークン)で集計を合算する。
        ex_acc: Counter = Counter()
        exc_acc: Counter = Counter()
        hits = 0
        for tok in set(_tokens(payee, description)):
            tb = self.by_token.get(tok)
            if not tb:
                continue
            hits += 1
            ex_acc.update(tb.get("ex_item", {}))
            exc_acc.update(tb.get("excise", {}))
        if ex_acc:
            ei, ei_conf = _top(dict(ex_acc))
            xi, _ = _top(dict(exc_acc))
            return Suggestion(
                ex_item=ei, excise=xi, confidence=round(ei_conf * 0.8, 3), basis=f"keyword×{hits}"
            )
        return Suggestion(basis="no-match")

    def to_dict(self) -> dict:
        return {
            "schema": USAGE_SCHEMA,
            "n": self.n,
            "by_payee": self.by_payee,
            "by_token": self.by_token,
            "ex_item_totals": self.ex_item_totals,
            "excise_totals": self.excise_totals,
            "ex_item_ids": self.ex_item_ids,
            "excise_ids": self.excise_ids,
        }

    @classmethod
    def from_dict(cls, d: dict) -> UsageIndex:
        return cls(
            n=int(d.get("n", 0)),
            by_payee=dict(d.get("by_payee") or {}),
            by_token=dict(d.get("by_token") or {}),
            ex_item_totals=dict(d.get("ex_item_totals") or {}),
            excise_totals=dict(d.get("excise_totals") or {}),
            ex_item_ids=dict(d.get("ex_item_ids") or {}),
            excise_ids=dict(d.get("excise_ids") or {}),
        )


def _top(counts: dict) -> tuple[str | None, float]:
    """件数 dict から最頻値とシェア(0..1)を返す。空なら (None, 0.0)。"""
    if not counts:
        return None, 0.0
    total = sum(counts.values())
    name, cnt = max(counts.items(), key=lambda kv: kv[1])
    return name, (round(cnt / total, 3) if total else 0.0)


def _bump(table: dict, key: str, dim: str, label: str) -> None:
    bucket = table.setdefault(key, {})
    counts = bucket.setdefault(dim, {})
    counts[label] = counts.get(label, 0) + 1


def aggregate_usage(transactions: list[dict]) -> UsageIndex:
    """経費明細のリストを集計して `UsageIndex` を作る(純粋・ネットワーク非依存)。"""
    idx = UsageIndex()
    for tx in transactions or []:
        if not isinstance(tx, dict):
            continue
        ex_item = _label(tx, _EX_ITEM_KEYS)
        excise = _label(tx, _EXCISE_KEYS)
        payee = _label(tx, _PAYEE_KEYS)
        desc = _label(tx, _DESC_KEYS)
        if not (ex_item or excise):
            continue  # 費目も税区分も取れない明細は実績にならない
        idx.n += 1
        if ex_item:
            idx.ex_item_totals[ex_item] = idx.ex_item_totals.get(ex_item, 0) + 1
            eid = _id_of(tx, "ex_item", "ex_item_id")
            if eid:
                idx.ex_item_ids.setdefault(ex_item, eid)
        if excise:
            idx.excise_totals[excise] = idx.excise_totals.get(excise, 0) + 1
            xid = _id_of(tx, "dr_excise", "dr_excise_id")
            if xid:
                idx.excise_ids.setdefault(excise, xid)

        pkey = _norm(payee)
        if pkey:
            bucket = idx.by_payee.setdefault(pkey, {"label": payee, "ex_item": {}, "excise": {}})
            if ex_item:
                bucket["ex_item"][ex_item] = bucket["ex_item"].get(ex_item, 0) + 1
            if excise:
                bucket["excise"][excise] = bucket["excise"].get(excise, 0) + 1

        for tok in set(_tokens(payee, desc)):
            if ex_item:
                _bump(idx.by_token, tok, "ex_item", ex_item)
            if excise:
                _bump(idx.by_token, tok, "excise", excise)
    return idx


# --- マスタ(ex_items / excises)→ name→ID マップ(登録時の ID 解決用)----------------------
# マスタの項目名キー候補。費目=name、税区分=long_name(詳細名)を優先しつつ name も拾う。
_MASTER_NAME_KEYS = ("name", "long_name", "label", "display_name")


def _master_names(rec: dict) -> list[str]:
    """1マスタレコードから ID 解決に使う名称候補を集める(重複なし・空除外)。"""
    out: list[str] = []
    for k in _MASTER_NAME_KEYS:
        v = rec.get(k)
        if isinstance(v, (str, int)) and str(v).strip():
            s = str(v).strip()
            if s not in out:
                out.append(s)
    return out


def master_id_map(records: list[dict]) -> dict[str, str]:
    """マスタ配列(`{"id","name",...}`)を name→ID 辞書にする。

    税区分は `name`(例 "課税仕入 8%")と `long_name` の双方をキーにして、ドラフトの税区分
    表記がどちらでも解決できるようにする。先に出た対応を優先(setdefault)。
    """
    out: dict[str, str] = {}
    for rec in records or []:
        if not isinstance(rec, dict):
            continue
        rid = rec.get("id")
        if not rid:
            continue
        for name in _master_names(rec):
            out.setdefault(name, str(rid))
    return out
