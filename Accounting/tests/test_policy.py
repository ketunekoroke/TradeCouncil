"""core/policy.py: 費目/税区分サジェスト・内外判定・外貨換算・相関キー。"""

from core.extract import ReceiptFields
from core.policy import UNDETERMINED, apply_policy, correlation_key
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


def test_correlation_key_format():
    assert correlation_key("2026-05-30", "abcdef1234") == "AC-202605-abcdef12"


def test_jpy_domestic_uses_usage():
    d = apply_policy(_fields(), usage=_usage())
    assert d.ex_item == "旅費交通費"
    assert d.excise == "課税仕入10%"
    assert d.domestic is True
    assert d.jpy_amount == "1000"
    assert d.correlation_key.startswith("AC-202605-")
    assert d.confidence == 1.0


def test_undetermined_when_no_usage():
    d = apply_policy(_fields(payee="知らない店", description=""))
    assert d.ex_item == UNDETERMINED
    assert d.excise == UNDETERMINED
    assert d.confidence <= 0.3
    assert any("費目" in f for f in d.flags)


def test_confirmed_ex_item_and_excise_win():
    # 操作者/Claude が確定した費目・税区分は実績より優先(新規取引先でも未確定にならない)。
    f = _fields(payee="新しい店", ex_item="接待交際費", excise="対象外")
    d = apply_policy(f, usage=_usage())
    assert d.ex_item == "接待交際費"
    assert d.excise == "対象外"
    assert d.basis["ex_item"] == "confirmed"
    assert d.basis["excise"] == "confirmed"


def test_override_wins_over_usage():
    overrides = [{"match": ["jr", "特急"], "ex_item": "旅費交通費(override)"}]
    d = apply_policy(_fields(), usage=_usage(), overrides=overrides)
    assert d.ex_item == "旅費交通費(override)"
    assert d.basis["ex_item"] == "override"


def test_foreign_with_rate_converts():
    f = _fields(payee="AWS", amount="32.10", currency="USD", description="EC2")
    rule = {"base_rule": "ttm_trade_date", "rate_source": "銀行TTM"}
    d = apply_policy(f, fx_rate="150", fx_rule=rule)
    assert d.jpy_amount == "4815"  # 32.10 * 150 = 4815
    assert d.fx_rate == "150"
    assert d.domestic is None  # 外貨は内外判定を自動確定しない
    assert any("税理士確認" in f for f in d.flags)


def test_foreign_without_rate_flags():
    f = _fields(payee="AWS", amount="32.10", currency="USD")
    d = apply_policy(f)
    assert d.jpy_amount is None
    assert any("レート未入力" in f for f in d.flags)


def test_overseas_hint_marks_domestic_unknown_even_in_jpy():
    f = _fields(payee="海外ベンダー", description="海外利用分", currency="JPY")
    d = apply_policy(f, usage=_usage())
    assert d.domestic is None
    assert any("内外判定" in f for f in d.flags)


def test_jpy_amount_rounds_half_up():
    d = apply_policy(_fields(amount="1080.5"))
    assert d.jpy_amount == "1081"
