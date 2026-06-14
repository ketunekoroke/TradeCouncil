"""core/extract.py: 抽出サイドカーの parse / validate / 往復。"""

from core.extract import ReceiptFields, parse_sidecar


def _sidecar(**overrides):
    base = {
        "source_file": "IMG_0001.jpg",
        "date": "2026-05-30",
        "payee": "Amazon Web Services",
        "amount": "32.10",
        "currency": "USD",
        "description": "EC2 利用料",
    }
    base.update(overrides)
    return base


def test_parse_and_roundtrip():
    f = parse_sidecar(_sidecar(crop_box=[1, 2, 30, 40], fx_rate="150.2"))
    assert f.payee == "Amazon Web Services"
    assert f.is_foreign() is True
    assert f.amount_decimal() == __import__("decimal").Decimal("32.10")
    # to_dict → from_dict 往復で同値。
    again = ReceiptFields.from_dict(f.to_dict())
    assert again.crop_box == [1, 2, 30, 40]
    assert again.fx_rate == "150.2"
    assert again.currency == "USD"


def test_confirmed_item_excise_roundtrip():
    f = parse_sidecar(_sidecar(ex_item="会議費", excise="課税仕入 10%"))
    again = ReceiptFields.from_dict(f.to_dict())
    assert again.ex_item == "会議費" and again.excise == "課税仕入 10%"


def test_jpy_default_not_foreign():
    f = parse_sidecar(_sidecar(currency="JPY", amount="1080", fx_rate=None))
    assert f.is_foreign() is False


def test_validate_ok():
    assert parse_sidecar(_sidecar()).validate() == []


def test_validate_catches_bad_fields():
    f = parse_sidecar(_sidecar(date="2026/05/30", amount="-5", currency="US", payee="  "))
    problems = " ".join(f.validate())
    assert "date" in problems
    assert "amount" in problems
    assert "currency" in problems
    assert "payee" in problems


def test_validate_crop_box_range():
    f = parse_sidecar(_sidecar(crop_box=[100, 100, 10, 10]))
    assert any("crop_box" in p for p in f.validate())


def test_validate_bad_fx_rate():
    f = parse_sidecar(_sidecar(fx_rate="abc"))
    assert any("fx_rate" in p for p in f.validate())
