"""検証ゲート(zero-dep・純粋): 経費明細ドラフトの機械チェック。

docs/compliance-checklist.md の登録前ゲートを、ドラフト1件に対して機械検査する。
`scripts/check_compliance.py` からも呼べる。LLM/抽出の出力をそのまま API に流さない(人手ゲート)。
design.md の方針に従い、error が残る間は登録に進めない設計とする。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from core.extract import ReceiptFields
from core.policy import UNDETERMINED, ExpenseDraft

# 高額フラグの既定しきい値(円)。閾値の最終確定は運用/税理士(accounting-policy.md)。
DEFAULT_HIGH_VALUE_JPY = 100000
# 参加者メモ(クラウド経費WEBで登録)を促す費目。
_ATTENDEE_ITEMS = ("会議費", "交際費")
_ATTENDEE_HINTS = ("会議", "打合せ", "接待", "meeting")


@dataclass
class Issue:
    """ゲートの指摘。level: error(登録不可)/ warn(要確認)/ info(参考)。"""

    level: str
    code: str
    message: str

    def to_dict(self) -> dict:
        return {"level": self.level, "code": self.code, "message": self.message}


def check(
    draft: ExpenseDraft, fields: ReceiptFields, *, high_value_jpy: int = DEFAULT_HIGH_VALUE_JPY
) -> list[Issue]:
    """ドラフトを検査して指摘の一覧を返す(空なら合格)。"""
    issues: list[Issue] = []

    # 証憑3項目(電帳法 検索要件): 日付・金額・取引先。
    if not draft.date:
        issues.append(Issue("error", "evidence.date", "日付がありません(証憑3項目)"))
    if not draft.payee.strip():
        issues.append(Issue("error", "evidence.payee", "支払先がありません(証憑3項目)"))
    if not str(draft.amount).strip():
        issues.append(Issue("error", "evidence.amount", "金額がありません(証憑3項目)"))

    # 費目・税区分。
    if not draft.ex_item or draft.ex_item == UNDETERMINED:
        issues.append(Issue("error", "ex_item.undetermined", "費目が未確定です(要確認)"))
    if not draft.excise or draft.excise == UNDETERMINED:
        issues.append(Issue("warn", "excise.undetermined", "税区分が未確定です(要確認)"))

    # 外貨は円換算済みであること。
    if fields.is_foreign():
        if not draft.jpy_amount:
            issues.append(
                Issue("error", "fx.unconverted", f"外貨が円換算されていません({draft.currency})")
            )
        if not draft.fx_rate:
            issues.append(Issue("warn", "fx.norate", "換算レートが記録されていません"))
        if draft.domestic is None:
            issues.append(
                Issue("warn", "domestic.unknown", "内外判定が要確認です(国外なら対象外/不課税)")
            )

    # 相関キー。
    if not draft.correlation_key:
        issues.append(Issue("error", "correlation.missing", "相関キーがありません(摘要に付与)"))

    # 適格請求書登録番号(2割特例では控除に影響しないが、あれば記録)。
    if not draft.invoice_number:
        issues.append(
            Issue("info", "invoice.absent", "登録番号なし(2割特例では控除に影響なし。記録のみ)")
        )

    # 接待/会議費は参加者メモが必要(クラウド経費WEBで登録 — 自動化対象外)。
    text = f"{draft.ex_item} {draft.payee} {draft.description}"
    if draft.ex_item in _ATTENDEE_ITEMS or any(h in text for h in _ATTENDEE_HINTS):
        issues.append(
            Issue(
                "info",
                "attendee.memo",
                "接待/会議費の参加者メモはクラウド経費WEBで登録してください",
            )
        )

    # 高額フラグ。
    jpy = _to_int(draft.jpy_amount) or _to_int(draft.amount)
    if jpy is not None and jpy >= high_value_jpy:
        issues.append(Issue("warn", "amount.high", f"高額(¥{jpy:,})— 要確認"))

    return issues


def has_errors(issues: list[Issue]) -> bool:
    return any(i.level == "error" for i in issues)


def summarize(issues: list[Issue]) -> str:
    counts = {"error": 0, "warn": 0, "info": 0}
    for i in issues:
        counts[i.level] = counts.get(i.level, 0) + 1
    return f"error={counts['error']} warn={counts['warn']} info={counts['info']}"


def _to_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return None
