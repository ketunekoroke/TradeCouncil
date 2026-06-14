"""core/ingest.py: ハッシュ・リネーム・台帳・重複判定。"""

from core import ingest
from core.ingest import Ledger, LedgerEntry


def test_content_hash_stable(tmp_path):
    p = tmp_path / "a.bin"
    p.write_bytes(b"hello world")
    h1 = ingest.content_hash(p)
    h2 = ingest.content_hash(p)
    assert h1 == h2 and len(h1) == 64
    p2 = tmp_path / "b.bin"
    p2.write_bytes(b"hello world!")
    assert ingest.content_hash(p2) != h1


def test_sanitize_payee():
    assert ingest.sanitize_payee("AWS") == "AWS"
    assert ingest.sanitize_payee("a/b:c*d?") == "abcd"
    assert ingest.sanitize_payee("  スターバックス  ") == "スターバックス"
    assert ingest.sanitize_payee("trailing.  ") == "trailing"
    assert ingest.sanitize_payee("") == "unknown"
    assert ingest.sanitize_payee("a" * 80, max_len=10) == "a" * 10


def test_build_filename():
    assert ingest.build_filename("2026-05-30", "AWS", "JPG") == "2026-05-30_AWS.jpg"
    assert ingest.build_filename("2026-05-30", "AWS", ".pdf", original=True) == (
        "2026-05-30_AWS_original.pdf"
    )
    assert ingest.build_filename("2026-05-30", "AWS", "jpg", dedup_suffix="ab12") == (
        "2026-05-30_AWS_ab12.jpg"
    )


def test_ledger_roundtrip(tmp_path):
    led = Ledger(path=tmp_path / "ledger.json")
    led.upsert(
        LedgerEntry(
            receipt_id="r1", content_hash="h1", date="2026-05-30", payee="AWS",
            amount="100", filename="2026-05-30_AWS.pdf", correlation_key="AC-202605-h1",
        )
    )
    led.save()
    again = Ledger.load(tmp_path / "ledger.json")
    assert len(again.entries) == 1
    assert again.entries[0].payee == "AWS"
    assert again.by_hash("h1").receipt_id == "r1"


def test_find_similar_normalizes_payee():
    led = Ledger(entries=[
        LedgerEntry(receipt_id="r1", content_hash="h1", date="2026-05-30",
                    payee="Star Bucks", amount="500"),
    ])
    # 空白/大小の違いは吸収して一致。
    assert led.find_similar("2026-05-30", "starbucks", "500")
    # 金額が違えば不一致。
    assert not led.find_similar("2026-05-30", "starbucks", "600")


def test_find_duplicate_exact_then_similar():
    led = Ledger(entries=[
        LedgerEntry(receipt_id="r1", content_hash="h1", date="2026-05-30",
                    payee="AWS", amount="100"),
    ])
    kind, e = ingest.find_duplicate("h1", "2026-05-30", "AWS", "100", "JPY", led)
    assert kind == "exact" and e.receipt_id == "r1"
    kind, e = ingest.find_duplicate("DIFFERENT", "2026-05-30", "AWS", "100", "JPY", led)
    assert kind == "similar" and e.receipt_id == "r1"
    kind, e = ingest.find_duplicate("DIFFERENT", "2026-05-30", "AWS", "999", "JPY", led)
    assert kind is None and e is None


def test_supersede_records_history():
    old = LedgerEntry(receipt_id="r1", content_hash="h1", date="2026-05-30",
                      payee="AWS", amount="100", filename="old.pdf")
    led = Ledger(entries=[old])
    new = LedgerEntry(receipt_id="r1", content_hash="h2", date="2026-05-30",
                      payee="AWS", amount="120", filename="new.pdf")
    led.supersede(old, new, at="2026-06-14T10:00:00")
    assert len(led.entries) == 1
    e = led.entries[0]
    assert e.content_hash == "h2"
    assert e.superseded[0]["content_hash"] == "h1"
    assert e.superseded[0]["at"] == "2026-06-14T10:00:00"
