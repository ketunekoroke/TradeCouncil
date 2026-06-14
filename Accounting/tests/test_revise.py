"""core/revise.py: MF 現値の正規化・差分判定・PUT ボディ組立(zero-dep・純粋・無ネットワーク)。"""

from core import revise
from core.extract import ReceiptFields
from core.policy import ExpenseDraft


def _draft(**kw):
    base = dict(
        date="2025-09-10", payee="Cafe del sol", description="打合せ",
        ex_item="会議費", excise="課税仕入 10%", amount="1500", currency="JPY",
        jpy_amount="1500", fx_rate=None, domestic=True, correlation_key="AC-202509-mf946",
        invoice_number=None,
    )
    base.update(kw)
    return ExpenseDraft(**base)


def _fields(**kw):
    base = dict(source_file="past_123", date="2025-09-10", payee="Cafe del sol",
                amount="1500", currency="JPY")
    base.update(kw)
    return ReceiptFields(**base)


def _tx(**kw):
    base = {
        "id": "123", "number": 946, "recognized_at": "2025-09-10",
        "ex_item": {"id": "EI_OLD", "name": "旅費交通費"},
        "dr_excise": {"id": "EX10", "long_name": "課税仕入10%"},
        "remark": "Cafe del sol", "value": 1500, "currency": "JPY",
        "mf_file": {"id": "f1", "name": "r.jpg", "content_type": "image/jpeg", "byte_size": 10},
    }
    base.update(kw)
    return base


def test_mfcurrent_from_tx():
    mc = revise.MFCurrent.from_tx(_tx())
    assert mc.tx_id == "123" and mc.number == "946" and mc.date == "2025-09-10"
    assert mc.payee == "Cafe del sol"
    assert mc.ex_item == "旅費交通費" and mc.excise == "課税仕入10%"
    assert mc.value == "1500" and mc.currency == "JPY"
    assert mc.has_file is True and mc.ex_item_id() == "EI_OLD"


def test_mfcurrent_no_file():
    mc = revise.MFCurrent.from_tx(_tx(mf_file=None, receipt_type="paper"))
    assert mc.has_file is False and mc.receipt_type == "paper"


def test_mfcurrent_snapshot_roundtrip():
    mc = revise.MFCurrent.from_tx(_tx())
    again = revise.MFCurrent.from_dict(mc.to_dict())
    assert again.tx_id == mc.tx_id and again.ex_item == mc.ex_item and again.has_file


def test_to_receipt_fields_leaves_ex_item_unset():
    rf = revise.MFCurrent.from_tx(_tx()).to_receipt_fields()
    assert rf.payee == "Cafe del sol" and rf.amount == "1500"
    assert rf.ex_item is None and rf.excise is None  # ポリシーで再導出させる


def test_diff_identical_is_empty():
    # MF 現値が提案と一致(費目=会議費・税区分は正規化で "課税仕入 10%"=="課税仕入10%")。
    cur = revise.MFCurrent.from_tx(_tx(ex_item={"id": "EI1", "name": "会議費"}))
    changes = revise.diff_entry(
        cur, _draft(), _fields(), ex_item_id="EI1", excise_id="EX10",
        proposed_remark=None, proposed_memo=None,
    )
    assert changes == []


def test_diff_ex_item_change():
    cur = revise.MFCurrent.from_tx(_tx())  # 費目=旅費交通費
    changes = revise.diff_entry(
        cur, _draft(ex_item="会議費"), _fields(), ex_item_id="EI_NEW", excise_id="EX10",
        proposed_remark=None, proposed_memo=None,
    )
    assert len(changes) == 1
    assert changes[0].field == "ex_item" and changes[0].put_key == "ex_item_id"
    assert changes[0].before == "旅費交通費" and changes[0].after == "会議費"


def test_diff_skips_ex_item_when_id_unresolved():
    cur = revise.MFCurrent.from_tx(_tx())
    changes = revise.diff_entry(
        cur, _draft(ex_item="会議費"), _fields(), ex_item_id=None, excise_id="EX10",
        proposed_remark=None, proposed_memo=None,
    )
    assert all(c.field != "ex_item" for c in changes)  # ID 無し → PUT できないので変更にしない


def test_diff_amount_decimal_equiv_no_change():
    cur = revise.MFCurrent.from_tx(_tx(ex_item={"id": "EI1", "name": "会議費"}, value=1500))
    changes = revise.diff_entry(
        cur, _draft(amount="1500.0"), _fields(amount="1500.0"), ex_item_id="EI1", excise_id="EX10",
        proposed_remark=None, proposed_memo=None,
    )
    assert changes == []  # Decimal 1500==1500.0


def test_diff_value_change():
    cur = revise.MFCurrent.from_tx(_tx(ex_item={"id": "EI1", "name": "会議費"}, value=1500))
    changes = revise.diff_entry(
        cur, _draft(amount="1800"), _fields(amount="1800"), ex_item_id="EI1", excise_id="EX10",
        proposed_remark=None, proposed_memo=None,
    )
    assert [c.field for c in changes] == ["value"] and changes[0].after == "1800"


def test_diff_fx_change_and_build_body():
    cur = revise.MFCurrent.from_tx(
        _tx(ex_item={"id": "EI1", "name": "会議費"}, value=10, currency="USD", jpyrate=150)
    )
    draft = _draft(amount="10", currency="USD", jpy_amount="1480", fx_rate="148")
    changes = revise.diff_entry(
        cur, draft, _fields(amount="10", currency="USD", fx_rate="148"),
        ex_item_id="EI1", excise_id="EX10", proposed_remark=None, proposed_memo=None,
    )
    assert {c.field for c in changes} == {"fx_rate"}  # 150→148(通貨/金額は不変)
    body = revise.build_update_body(changes, ex_item_id="EI1", excise_id="EX10")["ex_transaction"]
    assert body["jpyrate"] == 148 and body["use_custom_jpy_rate"] is True


def test_diff_remark_only_when_rewrite():
    cur = revise.MFCurrent.from_tx(_tx(ex_item={"id": "EI1", "name": "会議費"}, remark="古い摘要"))
    common = dict(ex_item_id="EI1", excise_id="EX10",
                  proposed_remark="Cafe del sol 打合せ", proposed_memo=None)
    off = revise.diff_entry(cur, _draft(), _fields(), rewrite_remark=False, **common)
    assert all(c.field != "remark" for c in off)
    on = revise.diff_entry(cur, _draft(), _fields(), rewrite_remark=True, **common)
    assert any(c.field == "remark" and c.after == "Cafe del sol 打合せ" for c in on)


def test_build_update_body_only_changed_keys():
    changes = [
        revise.FieldChange("ex_item", "ex_item_id", "旅費交通費", "会議費"),
        revise.FieldChange("value", "value", "1500", "1800"),
    ]
    body = revise.build_update_body(changes, ex_item_id="EI_NEW", excise_id="EXX")["ex_transaction"]
    assert body == {"ex_item_id": "EI_NEW", "value": 1800}  # 未変更の excise キーは入らない


def test_build_update_body_empty():
    assert revise.build_update_body([])["ex_transaction"] == {}
