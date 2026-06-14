"""core/register.py: 経費明細下書きの生成・要約・CSV・登録ボディ。"""

import pytest

from core.extract import ReceiptFields
from core.gate import check
from core.policy import apply_policy
from core.refdata import aggregate_usage
from core.register import (
    CSV_COLUMNS,
    ReceiptRef,
    build_ex_transaction_create,
    build_expense_draft,
    fx_memo,
    to_csv_row,
    to_summary,
)


def _fields(**overrides):
    base = dict(source_file="IMG.jpg", date="2026-05-30", payee="JR東日本", amount="1000",
                currency="JPY", description="特急券")
    base.update(overrides)
    return ReceiptFields(**base)


def _usage():
    return aggregate_usage([
        {"ex_item_name": "旅費交通費", "excise_name": "課税仕入10%", "partner_name": "JR東日本"},
    ])


def test_build_draft_carries_correlation_key_in_remark():
    f = _fields()
    d = apply_policy(f, usage=_usage())
    ref = ReceiptRef(processed_file="2026-05-30_JR東日本.jpg", content_hash="h1",
                     source_file="IMG.jpg")
    out = build_expense_draft(d, f, receipt=ref, issues=check(d, f))
    assert out["correlation_key"].startswith("AC-202605-")
    assert out["correlation_key"] in out["ex_transaction"]["remark"]
    assert out["ex_transaction"]["ex_item_name"] == "旅費交通費"
    assert out["receipt"]["processed_file"] == "2026-05-30_JR東日本.jpg"
    assert out["status"] == "draft"


def test_foreign_draft_keeps_original_value_and_rate():
    # 外貨は value=原通貨額・currency=原通貨・jpy_rate/jpy_value を別に持つ(MF 実機スキーマ準拠)。
    f = _fields(payee="AWS", amount="32.10", currency="USD", description="EC2")
    d = apply_policy(f, fx_rate="150")
    ex = build_expense_draft(d, f)["ex_transaction"]
    assert ex["value"] == "32.10"
    assert ex["currency"] == "USD"
    assert ex["jpy_rate"] == "150"
    assert ex["jpy_value"] == "4815"


def test_undetermined_item_serialized_as_none():
    f = _fields(payee="知らない店")
    d = apply_policy(f)
    out = build_expense_draft(d, f)
    assert out["ex_transaction"]["ex_item_name"] is None  # 未確定は API 形では None


def test_csv_row_matches_columns():
    f = _fields()
    d = apply_policy(f, usage=_usage())
    out = build_expense_draft(d, f)
    row = to_csv_row(out)
    assert len(row) == len(CSV_COLUMNS)
    assert row[CSV_COLUMNS.index("payee")] == "JR東日本"
    assert row[CSV_COLUMNS.index("ex_item")] == "旅費交通費"


def test_summary_is_human_readable():
    f = _fields()
    d = apply_policy(f, usage=_usage())
    out = build_expense_draft(d, f, issues=check(d, f))
    text = to_summary(out)
    assert "JR東日本" in text
    assert "旅費交通費" in text


def test_remark_starts_with_payee():
    f = _fields()  # 支払先 JR東日本
    d = apply_policy(f, usage=_usage())
    assert build_expense_draft(d, f)["ex_transaction"]["remark"].startswith("JR東日本")


def test_fx_memo_foreign_and_jpy():
    f = _fields(payee="AWS", amount="32.10", currency="USD")
    d = apply_policy(f, fx_rate="150")
    memo = fx_memo(d, rate_source="銀行TTM", base_rule="prev_month_end_ttm")
    assert "150" in memo and "USD" in memo and "前月末仲値を当月適用" in memo
    assert fx_memo(apply_policy(_fields(), usage=_usage()), rate_source="x") is None  # JPY は None


def test_build_ex_transaction_memo_included():
    f = _fields(payee="AWS", amount="32.10", currency="USD")
    d = apply_policy(f, fx_rate="150")
    tx = build_ex_transaction_create(d, f, ex_item_id="EI1", memo="為替メモ")["ex_transaction"]
    assert tx["memo"] == "為替メモ"


def test_build_ex_transaction_create_foreign_with_receipt():
    f = _fields(payee="AWS", amount="32.10", currency="USD", description="EC2")
    d = apply_policy(f, fx_rate="150")
    body = build_ex_transaction_create(
        d, f, ex_item_id="EI1", dr_excise_id="EX1",
        receipt_content_b64="QUJD", content_type="image/jpeg", filename="r.jpg",
    )
    tx = body["ex_transaction"]
    assert tx["ex_item_id"] == "EI1" and tx["dr_excise_id"] == "EX1"
    assert tx["value"] == 32.1 and tx["currency"] == "USD"  # 原通貨額(数値)
    assert tx["jpyrate"] == 150 and tx["use_custom_jpy_rate"] is True
    assert tx["receipt_input"] == {
        "content": "QUJD", "content_type": "image/jpeg", "filename": "r.jpg",
    }
    assert d.correlation_key in tx["remark"]


def test_build_ex_transaction_create_jpy_no_rate_no_receipt():
    f = _fields()
    d = apply_policy(f, usage=_usage())
    tx = build_ex_transaction_create(d, f, ex_item_id="EI1")["ex_transaction"]
    assert tx["currency"] == "JPY"
    assert "jpyrate" not in tx and "receipt_input" not in tx


def test_build_ex_transaction_requires_ex_item_id():
    f = _fields()
    d = apply_policy(f, usage=_usage())
    with pytest.raises(ValueError):
        build_ex_transaction_create(d, f, ex_item_id="")


def test_build_ex_transaction_attendants():
    f = _fields()
    d = apply_policy(f, usage=_usage())
    tx = build_ex_transaction_create(d, f, ex_item_id="EI1", attendants=(1, 3))["ex_transaction"]
    assert tx["ex_transaction_attendant_count_attributes"] == {"own_count": 1, "other_count": 3}
