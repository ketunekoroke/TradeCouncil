"""scripts/expense_pipeline.py + ac expense CLI(無ネットワーク・SharePoint/PIL 注入)。"""

import datetime
import json
import os

import pytest

from core import config, ingest
from core.moneyforward import ProductConfig
from scripts import expense_pipeline as ep


@pytest.fixture(autouse=True)
def _expense_env(monkeypatch, tmp_path):
    """作業領域を tmp に固定。実 .env / Teams URL を遮断し、通知は no-op にする。"""
    monkeypatch.setenv("EXPENSE_VAR_DIR", str(tmp_path / "expense"))
    monkeypatch.setattr(config, "_root_env", lambda: {})
    monkeypatch.setattr(config, "_settings_local_env", lambda: {})
    for key in list(os.environ):
        if key.startswith(("MONEYFORWARD", "TEAMS")):
            monkeypatch.delenv(key, raising=False)
    yield


def _write_raw(name: str, data: bytes = b"%PDF-1.4 fake"):
    raw = ep.sub("raw")
    raw.mkdir(parents=True, exist_ok=True)
    (raw / name).write_bytes(data)


def _write_sidecar(raw_name: str, **fields):
    base = {
        "source_file": raw_name, "date": "2026-05-30", "payee": "JR東日本",
        "amount": "1000", "currency": "JPY", "description": "特急券",
    }
    base.update(fields)
    ep.sub("extracted").mkdir(parents=True, exist_ok=True)
    ep.sidecar_path(raw_name).write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")


def _seed_usage():
    from core import refdata

    idx = refdata.aggregate_usage(
        [{"ex_item_name": "旅費交通費", "excise_name": "課税仕入10%", "partner_name": "JR東日本"}]
    )
    ep.save_usage(idx)


def _pc_expense():
    return ProductConfig(
        product="expense", label="クラウド経費", enabled=True, client_id="c", client_secret="s",
        authorize_url=None, token_url="https://t", redirect_uri=None, scopes=["transaction:write"],
        api_base="https://e/api", offices_url="https://e/api/external/v1/offices",
    )


def _seed_usage_with_ids():
    from core import refdata

    idx = refdata.aggregate_usage([
        {"ex_item": {"id": "EI_TAXI", "name": "旅費交通費"},
         "dr_excise": {"id": "EX10", "long_name": "課税仕入 10%"}, "remark": "JR東日本"},
    ])
    ep.save_usage(idx)


def test_register_drafts_dry_run_then_confirm():
    _seed_usage_with_ids()
    _write_raw("a.pdf")
    _write_sidecar("a.pdf", ex_item="旅費交通費", excise="課税仕入 10%")
    ep.process_all()
    pc = _pc_expense()

    res = ep.register_drafts(pc, confirm=False)  # ドライラン: 送信しない
    assert res["dry_run"] is True and not res["registered"]
    assert res["skipped"][0]["preview"]["ex_item_id"] == "EI_TAXI"
    assert res["skipped"][0]["preview"]["証憑添付"] is True

    seen = {}

    def fake_create(pc, office_id, body, access_token=None):
        seen.update(body=body, office=office_id)
        return {"ex_transaction": {"id": "EXT999"}}

    res2 = ep.register_drafts(
        pc, confirm=True, create_fn=fake_create,
        get_office_id_fn=lambda pc, access_token: "of1", access_token="tok",
    )
    assert res2["registered"][0]["mf_id"] == "EXT999"
    assert seen["body"]["ex_transaction"]["ex_item_id"] == "EI_TAXI"
    assert "receipt_input" in seen["body"]["ex_transaction"]  # 証憑添付(電帳法)
    led = ingest.Ledger.load(ep.ledger_path())
    assert led.entries[0].mf_status == "registered"
    assert led.entries[0].mf_transaction_id == "EXT999"

    res3 = ep.register_drafts(  # 再実行: 登録済みは対象外
        pc, confirm=True, create_fn=fake_create,
        get_office_id_fn=lambda pc, access_token: "of1", access_token="tok",
    )
    assert not res3["registered"]


def test_register_foreign_includes_memo_and_payee_remark():
    from core import refdata

    idx = refdata.aggregate_usage([
        {"ex_item": {"id": "EI_M", "name": "会議費"},
         "dr_excise": {"id": "EX_X", "long_name": "対象外"}, "remark": "AWS"},
    ])
    ep.save_usage(idx)
    _write_raw("b.pdf")
    _write_sidecar("b.pdf", payee="AWS", amount="32.10", currency="USD",
                   description="EC2", ex_item="会議費", excise="対象外", fx_rate="150")
    ep.process_all()
    seen = {}

    def fake_create(pc, office_id, body, access_token=None):
        seen["body"] = body
        return {"id": "X"}

    ep.register_drafts(
        _pc_expense(), confirm=True, create_fn=fake_create,
        get_office_id_fn=lambda pc, access_token: "of1", access_token="tok",
    )
    tx = seen["body"]["ex_transaction"]
    assert tx["remark"].startswith("AWS")  # 店名を先頭
    assert "memo" in tx and "150" in tx["memo"]  # レート適用メモ
    assert tx["value"] == 32.1 and tx["currency"] == "USD"


def test_register_notifies_operations():
    _seed_usage_with_ids()
    _write_raw("a.pdf")
    _write_sidecar("a.pdf", ex_item="旅費交通費", excise="課税仕入 10%")
    ep.process_all()
    calls = []

    def fake_notify(channel, title, message, *, facts=None, severity="info"):
        calls.append({"channel": channel, "facts": facts, "severity": severity})
        return True

    def fake_create(pc, oid, body, access_token=None):
        return {"ex_transaction": {"id": "X", "number": 950}}

    ep.register_drafts(
        _pc_expense(), confirm=True, create_fn=fake_create,
        get_office_id_fn=lambda pc, access_token: "of1", access_token="tok", notify_fn=fake_notify,
    )
    assert calls and calls[0]["channel"] == "operations"
    assert calls[0]["facts"]["明細番号"] == "950"
    assert calls[0]["facts"]["支払先"] == "JR東日本"
    assert calls[0]["facts"]["証憑"].startswith("添付あり")


def test_register_skips_when_ex_item_id_unresolved():
    _seed_usage()  # 名前のみ(ID 無し)
    _write_raw("a.pdf")
    _write_sidecar("a.pdf")
    ep.process_all()
    res = ep.register_drafts(_pc_expense(), confirm=False)
    assert res["skipped"] and "費目ID未解決" in res["skipped"][0]["reason"]


def test_clean_inbox_only_registered():
    _seed_usage_with_ids()
    _write_raw("a.pdf")
    _write_sidecar("a.pdf", ex_item="旅費交通費", excise="課税仕入 10%")
    ep.process_all()
    assert not ep.clean_inbox(confirm=False)["skipped"]  # 未登録 → 対象なし
    ep.register_drafts(
        _pc_expense(), confirm=True, create_fn=lambda *a, **k: {"id": "X"},
        get_office_id_fn=lambda pc, access_token: "of1", access_token="tok",
    )
    res = ep.clean_inbox(confirm=False)  # 登録後 → dry-run で対象に出る
    assert res["dry_run"] and res["skipped"][0]["source_file"] == "a.pdf"
    deleted = []
    res2 = ep.clean_inbox(confirm=True, delete_fn=lambda name: deleted.append(name))
    assert deleted == ["a.pdf"] and res2["deleted"] == ["a.pdf"]


def test_prior_fy_range():
    assert ep.prior_fy_range(datetime.date(2026, 6, 14)) == ("2024-07-01", "2025-06-30")
    assert ep.prior_fy_range(datetime.date(2026, 7, 1)) == ("2025-07-01", "2026-06-30")


def test_default_refdata_range_spans_prior_fy_to_today():
    # 前期開始〜今日(前期が空でも当期の実績を学習できる)。
    assert ep.default_refdata_range(datetime.date(2026, 6, 14)) == ("2024-07-01", "2026-06-14")


def test_expense_remote_paths():
    # drive 直下相対(root/workspace を付けない)。config が空なら既定。前後の / は除去。
    cfg = {"expense": {"inbox": "Expense/Inbox"}}
    assert ep.expense_remote(cfg, "inbox", "X") == "Expense/Inbox"
    assert ep.expense_remote({}, "inbox", "Expense/Inbox") == "Expense/Inbox"
    assert ep.expense_remote({"expense": {"master": "/Foo/Bar/"}}, "master", "X") == "Foo/Bar"


def test_run_refdata_aggregates_and_saves():
    pc = ProductConfig(
        product="expense", label="クラウド経費", enabled=True, client_id="c", client_secret="s",
        authorize_url=None, token_url="https://t", redirect_uri=None, scopes=["transaction:write"],
        api_base="https://e/api", offices_url="https://e/api/external/v1/offices",
    )

    def fake_list(pc, *, date_from, date_to, access_token):
        assert (date_from, date_to) == ("2024-07-01", "2025-06-30")
        return [{"ex_item_name": "通信費", "excise_name": "課税仕入10%", "partner_name": "AWS"}]

    summary = ep.run_refdata(pc, date_from="2024-07-01", date_to="2025-06-30", list_fn=fake_list)
    assert summary["n"] == 1
    assert ep.usage_path().is_file()
    assert ep.load_usage().suggest("AWS").ex_item == "通信費"


def test_pending_extract_when_no_sidecar():
    _write_raw("a.pdf")
    res = ep.process_all()
    assert res["pending_extract"] == ["a.pdf"]
    assert not res["processed"]


def test_process_creates_draft_and_ledger():
    _seed_usage()
    _write_raw("a.pdf")
    _write_sidecar("a.pdf")
    res = ep.process_all()
    assert len(res["processed"]) == 1
    assert (ep.sub("processed") / "2026-05-30_JR東日本.pdf").exists()
    assert (ep.sub("processed") / "2026-05-30_JR東日本_original.pdf").exists()
    drafts = ep.list_drafts()
    assert drafts[0]["ex_transaction"]["ex_item_name"] == "旅費交通費"
    assert drafts[0]["correlation_key"] in drafts[0]["ex_transaction"]["remark"]
    led = ingest.Ledger.load(ep.ledger_path())
    assert len(led.entries) == 1 and led.entries[0].ex_item == "旅費交通費"


def test_image_box_passed_to_processor():
    _seed_usage()
    _write_raw("b.jpg", b"\xff\xd8\xff fake")
    _write_sidecar("b.jpg", crop_box=[1, 2, 30, 40])
    seen = {}

    def fake_proc(src, primary, original, box):
        seen["box"] = box
        from pathlib import Path

        Path(primary).write_bytes(b"x")
        Path(original).write_bytes(b"y")
        return {"primary": str(primary), "original": str(original), "cropped": box is not None}

    ep.process_all(process_image=fake_proc)
    assert seen["box"] == (1, 2, 30, 40)


def test_exact_duplicate_skipped_on_rerun():
    _seed_usage()
    _write_raw("a.pdf")
    _write_sidecar("a.pdf")
    ep.process_all()
    res2 = ep.process_all()
    assert res2["skipped"] and res2["skipped"][0]["reason"].startswith("完全重複")
    assert not res2["processed"]


def test_similar_duplicate_needs_approval_then_overwrites():
    _seed_usage()
    _write_raw("a.pdf", b"content-A")
    _write_sidecar("a.pdf", amount="1000")
    ep.process_all()
    # 同じ日付+支払先+金額だが中身が違う(撮り直し)→ similar 重複。
    _write_raw("a.pdf", b"content-B-different-bytes")
    res = ep.process_all(approve_overwrite=False)  # approver なし → 上書きせず skip
    assert res["skipped"] and "未承認" in res["skipped"][0]["reason"]
    res2 = ep.process_all(approve_overwrite=True)
    assert res2["processed"] and res2["processed"][0]["overwrote"] is True
    led = ingest.Ledger.load(ep.ledger_path())
    assert len(led.entries) == 1
    assert led.entries[0].superseded  # 上書き履歴が残る


def test_check_compliance_scan_drafts_flags_errors():
    from scripts import check_compliance

    # usage を撒かない → 費目未確定 → ゲート error → scan_drafts が拾う。
    _write_raw("x.pdf")
    _write_sidecar("x.pdf", payee="名も無き店", description="不明な品目")
    ep.process_all()
    problems = check_compliance.scan_drafts()
    assert problems and any("未確定" in p for p in problems)


def test_export_xlsx_from_ledger():
    import pytest

    pytest.importorskip("openpyxl")
    pimage = pytest.importorskip("PIL.Image")
    _seed_usage_with_ids()
    raw = ep.sub("raw")
    raw.mkdir(parents=True, exist_ok=True)
    pimage.new("RGB", (120, 160), (200, 200, 200)).save(raw / "r.png")
    _write_sidecar("r.png", payee="JR東日本", ex_item="旅費交通費", excise="課税仕入 10%")
    ep.process_all()
    out = ep.export_xlsx()
    assert out.is_file()
    import openpyxl

    ws = openpyxl.load_workbook(out).active
    assert ws.cell(1, 4).value == "支払先"
    assert ws.cell(2, 4).value == "JR東日本"
    assert len(ws._images) == 1  # 証憑サムネイル


def test_cli_status_and_process_dispatch(capsys):
    from scripts import cli

    _seed_usage()
    _write_raw("a.pdf")
    _write_sidecar("a.pdf")
    assert cli.main(["expense", "process", "--yes"]) == 0
    out = capsys.readouterr().out
    assert "処理 1" in out
    assert cli.main(["expense", "status"]) == 0
    out = capsys.readouterr().out
    assert "台帳 1 件" in out
