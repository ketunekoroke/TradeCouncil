"""core/gate.py: 経費明細ドラフトの検証ゲート。"""

from core.extract import ReceiptFields
from core.gate import check, has_errors
from core.policy import apply_policy
from core.refdata import aggregate_usage


def _fields(**overrides):
    base = dict(source_file="r.jpg", date="2026-05-30", payee="JR東日本", amount="1000",
                currency="JPY", description="特急券")
    base.update(overrides)
    return ReceiptFields(**base)


def _usage():
    return aggregate_usage([
        {"ex_item_name": "旅費交通費", "excise_name": "課税仕入10%", "partner_name": "JR東日本"},
    ])


def _codes(issues):
    return {i.code for i in issues}


def test_clean_draft_has_no_errors():
    d = apply_policy(_fields(), usage=_usage())
    issues = check(d, _fields())
    assert not has_errors(issues)


def test_undetermined_ex_item_is_error():
    f = _fields(payee="知らない店")
    d = apply_policy(f)
    issues = check(d, f)
    assert has_errors(issues)
    assert "ex_item.undetermined" in _codes(issues)


def test_foreign_unconverted_is_error():
    f = _fields(payee="AWS", amount="32.10", currency="USD")
    d = apply_policy(f)  # レート無 → jpy 換算なし
    issues = check(d, f)
    assert "fx.unconverted" in _codes(issues)
    assert has_errors(issues)


def test_attendee_memo_info_for_meeting():
    f = _fields(payee="スタバ", description="打合せ")
    usage = aggregate_usage([
        {"ex_item_name": "会議費", "excise_name": "課税仕入10%", "partner_name": "スタバ"},
    ])
    d = apply_policy(f, usage=usage)
    issues = check(d, f)
    assert "attendee.memo" in _codes(issues)


def test_high_value_warn():
    f = _fields(amount="250000")
    d = apply_policy(f, usage=_usage())
    issues = check(d, f, high_value_jpy=100000)
    assert "amount.high" in _codes(issues)


def test_invoice_absent_is_info_not_error():
    f = _fields()
    d = apply_policy(f, usage=_usage())
    issues = check(d, f)
    info = [i for i in issues if i.code == "invoice.absent"]
    assert info and info[0].level == "info"
