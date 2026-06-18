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


def _write_split_spec(raw_name, parts, mode="explicit"):
    ep.sub("split").mkdir(parents=True, exist_ok=True)
    spec = {"source_file": raw_name, "mode": mode, "parts": parts}
    ep.split_spec_path(raw_name).write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")


def _fake_split(src, jobs):
    """各ジョブの出力先に最小 PDF を書く(pypdf を使わない注入用)。"""
    from pathlib import Path

    out = []
    for p, _pages in jobs:
        p = Path(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"%PDF-1.4 " + p.name.encode())
        out.append(p)
    return out


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


def test_split_pdfs_dry_run_then_confirm():
    _write_raw("multi.pdf", b"%PDF-1.4 fake")
    _write_split_spec("multi.pdf", [{"pages": [1], "suffix": "a"}, {"pages": [2], "suffix": "b"}])

    dry = ep.split_pdfs(confirm=False, page_count_fn=lambda p: 2, split_fn=_fake_split)
    assert dry["dry_run"] and dry["skipped"][0]["parts"] == ["multi_a.pdf", "multi_b.pdf"]
    assert not (ep.sub("raw") / "multi_a.pdf").exists()  # ドライランでは書かない

    res = ep.split_pdfs(confirm=True, page_count_fn=lambda p: 2, split_fn=_fake_split)
    assert res["split"][0]["parts"] == ["multi_a.pdf", "multi_b.pdf"]
    assert (ep.sub("raw") / "multi_a.pdf").exists() and (ep.sub("raw") / "multi_b.pdf").exists()
    assert not (ep.sub("raw") / "multi.pdf").exists()  # 原本は raw から退避
    assert (ep.sub("split_src") / "multi.pdf").exists()  # 退避先に残る(復元可)

    # 再実行: 原本は退避済み → 対象なし(冪等)。
    res2 = ep.split_pdfs(confirm=True, page_count_fn=lambda p: 2, split_fn=_fake_split)
    assert not res2["split"] and not res2["errors"]


def test_split_pdfs_catches_off_by_one():
    _write_raw("multi.pdf", b"%PDF-1.4 fake")
    _write_split_spec("multi.pdf", [{"pages": [3], "suffix": "a"}])  # 全2ページに3 → 範囲外
    res = ep.split_pdfs(confirm=True, page_count_fn=lambda p: 2, split_fn=_fake_split)
    assert res["errors"] and "範囲外" in res["errors"][0]["error"]
    assert (ep.sub("raw") / "multi.pdf").exists()  # 失敗時は退避しない


def test_split_pdfs_skips_existing_outputs():
    _write_raw("multi.pdf", b"%PDF-1.4 fake")
    _write_raw("multi_a.pdf", b"already")  # 既に分割済み相当
    _write_split_spec("multi.pdf", [{"pages": [1], "suffix": "a"}])
    res = ep.split_pdfs(confirm=True, page_count_fn=lambda p: 1, split_fn=_fake_split)
    assert res["skipped"] and "既に存在" in res["skipped"][0]["reason"]


def test_split_then_process_each_part():
    # 分割 → 各パートに抽出サイドカー → process が1レシートずつ処理。
    _seed_usage()
    _write_raw("multi.pdf", b"%PDF-1.4 fake")
    _write_split_spec("multi.pdf", [{"pages": [1], "suffix": "a"}, {"pages": [2], "suffix": "b"}])
    ep.split_pdfs(confirm=True, page_count_fn=lambda p: 2, split_fn=_fake_split)
    _write_sidecar("multi_a.pdf", payee="SAN KYU", amount="500")
    _write_sidecar("multi_b.pdf", payee="2nd STREET", amount="800")
    res = ep.process_all()
    assert len(res["processed"]) == 2
    names = {p["processed_file"] for p in res["processed"]}
    assert any("SAN KYU" in n for n in names) and any("2nd STREET" in n for n in names)


def test_cli_split_dispatch(capsys, monkeypatch):
    from scripts import cli, pdfproc

    _write_raw("multi.pdf", b"%PDF-1.4 fake")
    _write_split_spec("multi.pdf", [{"pages": [1], "suffix": "a"}, {"pages": [2], "suffix": "b"}])
    monkeypatch.setattr(pdfproc, "page_count", lambda p: 2)  # pypdf を呼ばせない(dry-run)
    assert cli.main(["expense", "split"]) == 0
    out = capsys.readouterr().out
    assert "PDF分割" in out and "DRY-RUN" in out and "multi_a.pdf" in out


def _tx_full(tx_id, *, date="2025-09-10", payee="Cafe del sol", ex_item="旅費交通費",
             value=1500, has_file=True):
    tx = {
        "id": tx_id, "number": int(tx_id), "recognized_at": date,
        "ex_item": {"id": "EI_OLD", "name": ex_item},
        "dr_excise": {"id": "EX10", "long_name": "課税仕入10%"},
        "remark": payee, "value": value, "currency": "JPY",
    }
    if has_file:
        tx["mf_file"] = {"id": f"f{tx_id}", "name": "r.jpg",
                         "content_type": "image/jpeg", "byte_size": 3}
    return tx


def _office(pc, access_token):
    return "of1"


def test_import_past_downloads_and_seeds_ledger():
    txs = [
        _tx_full("100", date="2025-09-10"),                  # 在FY + 証憑
        _tx_full("200", date="2025-10-01", has_file=False),  # 紙(証憑なし)
        _tx_full("300", date="2024-08-01"),                  # 期外(前期)
    ]

    def fake_list(pc, office_id, *, date_from, date_to, access_token, max_pages):
        return [t for t in txs if date_from <= t["recognized_at"] <= date_to]

    dl = []

    def fake_dl(pc, office_id, tx_id, *, access_token):
        dl.append(tx_id)
        return (b"img", "image/jpeg")

    res = ep.import_past(
        _pc_expense(), date_from="2025-07-01", date_to="2026-06-15",
        list_fn=fake_list, download_fn=fake_dl, get_office_id_fn=_office, access_token="tok",
    )
    assert {r["tx_id"] for r in res["imported"]} == {"100", "200"}  # 300 は期外
    assert res["no_file"] == ["200"] and res["downloaded"] == 1 and dl == ["100"]
    assert (ep.past_dir() / "past_100.jpg").exists()
    assert ep.past_snapshot_path("100").is_file()
    led = ingest.Ledger.load(ep.ledger_path())
    e = next(x for x in led.entries if x.receipt_id == "past_100")
    assert e.mf_status == "imported" and e.mf_transaction_id == "100" and e.mf_number == "100"

    # 再実行: DL済み(サイズ一致)でスキップ=冪等。
    dl.clear()
    res2 = ep.import_past(
        _pc_expense(), date_from="2025-07-01", date_to="2026-06-15",
        list_fn=fake_list, download_fn=fake_dl, get_office_id_fn=_office, access_token="tok",
    )
    assert dl == [] and any("DL済み" in s["reason"] for s in res2["skipped"])


def test_revise_past_dry_run_then_confirm():
    _seed_usage_with_ids()  # 旅費交通費→EI_TAXI, 課税仕入 10%→EX10
    tx = _tx_full("100", ex_item="通信費")  # MF の OCR が誤って通信費

    def fake_list(pc, office_id, *, date_from, date_to, access_token, max_pages):
        return [tx]

    ep.import_past(
        _pc_expense(), date_from="2025-07-01", date_to="2026-06-15", list_fn=fake_list,
        download_fn=lambda *a, **k: (b"img", "image/jpeg"),
        get_office_id_fn=_office, access_token="tok",
    )
    # Claude 再読込: 正しい費目/税区分のサイドカー(past 受領ファイル名で)。
    _write_sidecar("past_100.jpg", payee="JR東日本", amount="1500",
                   ex_item="旅費交通費", excise="課税仕入 10%", date="2025-09-10")

    res = ep.revise_past(_pc_expense(), confirm=False)  # ドライラン
    assert res["dry_run"] and not res["revised"]
    prev = next(s for s in res["skipped"] if s.get("changes"))
    assert any(c["field"] == "ex_item" and c["after"] == "旅費交通費" for c in prev["changes"])

    seen = {}

    def fake_update(pc, office_id, tx_id, body, access_token=None):
        seen.update(tx_id=tx_id, body=body)
        return {"id": tx_id}

    res2 = ep.revise_past(
        _pc_expense(), confirm=True, update_fn=fake_update,
        get_office_id_fn=_office, access_token="tok",
    )
    assert res2["revised"] and res2["revised"][0]["tx_id"] == "100"
    assert seen["body"]["ex_transaction"]["ex_item_id"] == "EI_TAXI"
    assert "receipt_input" not in seen["body"]["ex_transaction"]  # 再アップロードしない
    led = ingest.Ledger.load(ep.ledger_path())
    e = next(x for x in led.entries if x.receipt_id == "past_100")
    assert e.mf_status == "revised" and e.revised_at and e.ex_item == "旅費交通費"

    # 再実行: スナップショット更新済み → 差分ゼロ(二重PUT防止)。
    res3 = ep.revise_past(
        _pc_expense(), confirm=True, update_fn=fake_update,
        get_office_id_fn=_office, access_token="tok",
    )
    assert res3["no_change"] == ["100"] and not res3["revised"]


def test_revise_past_skips_no_file_entry():
    _seed_usage_with_ids()
    tx = _tx_full("400", ex_item="通信費", has_file=False)  # 紙(証憑なし)
    ep.import_past(
        _pc_expense(), date_from="2025-07-01", date_to="2026-06-15",
        list_fn=lambda *a, **k: [tx], download_fn=lambda *a, **k: (b"", ""),
        get_office_id_fn=_office, access_token="tok",
    )
    res = ep.revise_past(_pc_expense(), confirm=False)
    assert any("証憑なし" in s["reason"] for s in res["skipped"]) and not res["revised"]


def test_export_xlsx_embeds_past_receipt():
    import io

    pytest.importorskip("openpyxl")
    pimage = pytest.importorskip("PIL.Image")
    buf = io.BytesIO()
    pimage.new("RGB", (60, 80), (180, 180, 180)).save(buf, format="PNG")
    png = buf.getvalue()
    tx = _tx_full("100")
    tx["mf_file"].update(name="r.png", byte_size=len(png))

    ep.import_past(
        _pc_expense(), date_from="2025-07-01", date_to="2026-06-15",
        list_fn=lambda *a, **k: [tx], download_fn=lambda *a, **k: (png, "image/png"),
        get_office_id_fn=_office, access_token="tok",
    )
    assert (ep.past_dir() / "past_100.png").exists()
    out = ep.export_xlsx()
    import openpyxl

    ws = openpyxl.load_workbook(out).active
    payees = [ws.cell(r, 4).value for r in range(2, ws.max_row + 1)]
    assert "Cafe del sol" in payees  # 過去分が台帳に行として載る
    assert len(ws._images) >= 1  # past/ から証憑サムネイルを埋込


def test_export_xlsx_dedup_and_foreign_jpy():
    pytest.importorskip("openpyxl")
    tx = _tx_full("100", value=1000)
    tx["currency"], tx["jpyrate"] = "THB", 5.0  # 外貨(THB)・レート5.0
    ep.import_past(
        _pc_expense(), date_from="2025-07-01", date_to="2026-06-15",
        list_fn=lambda *a, **k: [tx], download_fn=lambda *a, **k: (b"img", "image/jpeg"),
        get_office_id_fn=_office, access_token="tok",
    )
    # 同一 MF 取引(id=100)の古い registered 重複を台帳に混入させる。
    led = ingest.Ledger.load(ep.ledger_path())
    led.upsert(ingest.LedgerEntry(
        receipt_id="2026-03-14_old", content_hash="h", date="2026-03-14", payee="OLD",
        amount="1000", currency="THB", mf_status="registered", mf_transaction_id="100",
        correlation_key="AC-old",
    ))
    led.save(ep.ledger_path())

    out = ep.export_xlsx(embed_images=False)
    import openpyxl

    ws = openpyxl.load_workbook(out).active
    mfids = [ws.cell(r, 16).value for r in range(2, ws.max_row + 1)]  # MF-ID 列
    assert mfids.count("100") == 1  # 重複排除: past_ 側1行のみ
    row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 16).value == "100")
    assert str(ws.cell(row, 10).value) == "5000"  # 円換算=value×rate=1000×5.0
    assert ws.cell(row, 4).value == "Cafe del sol"  # past_ 側(OLD ではない)


def test_cli_import_past_and_revise_past_dispatch(capsys, monkeypatch):
    from scripts import cli
    from scripts import expense_pipeline as ep_mod

    monkeypatch.setattr(ep_mod.oauth, "get_access_token", lambda pc: "tok")
    monkeypatch.setattr(ep_mod.mf_expense_api, "get_office_id", _office)
    monkeypatch.setattr(
        ep_mod.mf_expense_api, "list_my_ex_transactions",
        lambda pc, office_id, **k: [_tx_full("100")],
    )
    monkeypatch.setattr(
        ep_mod.mf_expense_api, "download_ex_transaction_receipt",
        lambda pc, office_id, tx_id, **k: (b"img", "image/jpeg"),
    )
    # クラウド経費の設定を ready に見せる(import-past/revise-past は load_product を通る)。
    monkeypatch.setattr(cli, "_err", lambda exc: str(exc))
    from core import moneyforward as mf
    monkeypatch.setattr(mf, "load_product", lambda product: _pc_expense())

    assert cli.main(["expense", "import-past"]) == 0
    out = capsys.readouterr().out
    assert "過去分取込" in out
    assert cli.main(["expense", "revise-past"]) == 0  # サイドカー無し→policy-only / dry-run
    out = capsys.readouterr().out
    assert "過去分補正" in out and "DRY-RUN" in out


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


def test_fetch_masters_merges_ids_into_usage():
    from core import refdata

    # 学習済み usage(通信費=LEARNED)を種にする。
    idx = refdata.aggregate_usage(
        [{"ex_item": {"name": "通信費", "id": "LEARNED"}, "remark": "AWS"}]
    )
    ep.save_usage(idx)

    ex_items = [{"id": "E1", "name": "通信費"}, {"id": "E2", "name": "支払手数料"}]
    excises = [{"id": "T8", "name": "課税仕入 8%"}]
    summary = ep.fetch_masters(
        _pc_expense(),
        access_token="tok",
        ex_items_fn=lambda pc, oid, *, access_token=None: ex_items,
        excises_fn=lambda pc, oid, *, access_token=None: excises,
        get_office_id_fn=lambda pc, *, access_token=None: "of1",
    )
    assert summary["ex_items"] == 2 and summary["excises"] == 1
    assert summary["added_ex_item"] == 1  # 通信費は学習済み→支払手数料のみ追加
    assert summary["added_excise"] == 1
    u = ep.load_usage()
    assert u.ex_item_id("通信費") == "LEARNED"  # 学習済みは保持
    assert u.ex_item_id("支払手数料") == "E2"  # 未学習費目を解決可能に
    assert u.excise_id("課税仕入 8%") == "T8"  # 8% を解決可能に


def test_fetch_masters_handles_missing_office():
    summary = ep.fetch_masters(
        _pc_expense(),
        access_token="tok",
        ex_items_fn=lambda *a, **k: [],
        excises_fn=lambda *a, **k: [],
        get_office_id_fn=lambda pc, *, access_token=None: None,
    )
    assert summary.get("error")


def test_is_var_core_filters_state_from_images():
    # 状態の核(再現不可)= True、証憑画像/一時物 = False。
    assert ep._is_var_core("ledger.json")
    assert ep._is_var_core("extracted/2026-05-30_x.json")
    assert ep._is_var_core("refdata/expense_usage.json")
    assert ep._is_var_core("drafts/r.json")
    assert ep._is_var_core("murc_2026.xls")
    assert ep._is_var_core("past/past_abc.mf.json")  # MF現値スナップショット=状態
    assert not ep._is_var_core("processed/2026-05-30_x.pdf")
    assert not ep._is_var_core("past/past_abc.jpg")  # 画像本体
    assert not ep._is_var_core("raw/scan.pdf")


def test_plan_var_sync_core_only_excludes_images():
    local = {"ledger.json": 100.0, "processed/a.jpg": 100.0, "raw/x.pdf": 100.0}
    remote = {"drafts/d.json": 200.0}
    full = dict(ep.plan_var_sync(local, remote, core_only=False))
    assert full["ledger.json"] == "push"
    assert full["processed/a.jpg"] == "push"  # 遠隔に無い → push
    assert full["drafts/d.json"] == "pull"  # ローカルに無い → pull
    core = dict(ep.plan_var_sync(local, remote, core_only=True))
    assert core == {"ledger.json": "push", "drafts/d.json": "pull"}  # 画像/raw は対象外


def test_sync_var_orchestration_injected():
    pushes, pulls = [], []
    res = ep.sync_var(
        connect=lambda base: ("drv", "Expense/Var/expense", "tok"),
        local_index_fn=lambda b: {"ledger.json": 100.0, "processed/a.jpg": 100.0},
        remote_index_fn=lambda d, rb, t: {
            "ledger.json": (50.0, {"id": "r1"}),  # local newer → push
            "drafts/d.json": (200.0, {"id": "r2"}),  # local 無し → pull
        },
        push_fn=lambda d, lp, rf, t: pushes.append(rf),
        pull_fn=lambda d, it, rf, lp, t: pulls.append((rf, it)),
    )
    assert set(res["pushed"]) == {"ledger.json", "processed/a.jpg"}
    assert res["pulled"] == ["drafts/d.json"]
    assert res["remote"] == "Expense/Var/expense"
    assert "Expense/Var/expense/ledger.json" in pushes
    assert pulls == [("Expense/Var/expense/drafts/d.json", {"id": "r2"})]  # remote item を pull に渡す
