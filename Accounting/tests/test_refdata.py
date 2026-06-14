"""core/refdata.py: 前期明細の集計と費目/税区分サジェスト。"""

from core.refdata import UsageIndex, aggregate_usage


def _tx(ex_item, excise, payee, name=""):
    # ネスト({id,name})とフラットの両方を混在させて吸収を検証する。
    return {
        "ex_item": {"id": 1, "name": ex_item},
        "excise_name": excise,
        "partner_name": payee,
        "name": name,
    }


def test_aggregate_and_suggest_by_payee():
    txs = [
        _tx("旅費交通費", "課税仕入10%", "JR東日本"),
        _tx("旅費交通費", "課税仕入10%", "JR東日本"),
        _tx("会議費", "課税仕入10%", "スターバックス"),
    ]
    idx = aggregate_usage(txs)
    assert idx.n == 3
    s = idx.suggest("JR東日本")
    assert s.ex_item == "旅費交通費"
    assert s.excise == "課税仕入10%"
    assert s.confidence == 1.0
    assert "payee" in s.basis


def test_suggest_by_keyword_when_payee_unknown():
    txs = [_tx("通信費", "課税仕入10%", "AWS", name="EC2 サーバ")]
    idx = aggregate_usage(txs)
    # 取引先は未知でも、摘要のキーワード(ec2)で当てる。
    s = idx.suggest("Unknown Vendor", "ec2 instance")
    assert s.ex_item == "通信費"
    assert "keyword" in s.basis
    assert 0 < s.confidence <= 1.0


def test_suggest_no_match_returns_none():
    idx = aggregate_usage([_tx("通信費", "課税仕入10%", "AWS", name="ec2")])
    s = idx.suggest("全く別の店", "無関係な内容")
    assert s.ex_item is None and s.excise is None
    assert s.basis == "no-match"


def test_serialize_roundtrip():
    idx = aggregate_usage([_tx("通信費", "課税仕入10%", "AWS", name="ec2")])
    again = UsageIndex.from_dict(idx.to_dict())
    assert again.n == idx.n
    assert again.suggest("AWS").ex_item == "通信費"


def test_transactions_without_item_are_skipped():
    idx = aggregate_usage([{"partner_name": "X", "name": "no item/excise"}])
    assert idx.n == 0


def test_id_maps_captured_and_roundtrip():
    txs = [{"ex_item": {"id": "EI1", "name": "会議費"},
            "dr_excise": {"id": "EX1", "long_name": "課税仕入 10%"}, "remark": "店"}]
    idx = aggregate_usage(txs)
    assert idx.ex_item_id("会議費") == "EI1"
    assert idx.excise_id("課税仕入 10%") == "EX1"
    again = UsageIndex.from_dict(idx.to_dict())  # 登録に使う ID は往復で保持
    assert again.ex_item_id("会議費") == "EI1"
    assert again.excise_id("課税仕入 10%") == "EX1"


def test_id_from_top_level_fields():
    txs = [{"ex_item": {"name": "通信費"}, "ex_item_id": "TOP1",
            "dr_excise": {"long_name": "対象外"}, "dr_excise_id": "TOP2", "remark": "x"}]
    idx = aggregate_usage(txs)
    assert idx.ex_item_id("通信費") == "TOP1"
    assert idx.excise_id("対象外") == "TOP2"


def test_aggregate_real_mf_schema():
    # 実機(MF 経費)スキーマ: 費目=ex_item.name / 税区分=dr_excise.long_name / 店名=remark。
    txs = [
        {"ex_item": {"id": "a", "name": "会議費"},
         "dr_excise": {"id": "e", "long_name": "課税仕入 10%"},
         "remark": "品川プリンスホテル", "currency": "JPY"}
        for _ in range(3)
    ]
    idx = aggregate_usage(txs)
    assert idx.n == 3
    assert idx.ex_item_totals.get("会議費") == 3
    assert idx.excise_totals.get("課税仕入 10%") == 3
    s = idx.suggest("品川プリンスホテル")  # 店名(remark)で当てる
    assert s.ex_item == "会議費"
    assert s.excise == "課税仕入 10%"
