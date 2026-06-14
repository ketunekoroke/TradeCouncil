"""core/pdfsplit.py: 分割計画の解釈・検証・出力名(zero-dep・純粋・無 pypdf)。"""

import pytest

from core import pdfsplit


def test_parse_explicit_plan():
    plan = pdfsplit.parse_split_sidecar({
        "source_file": "2026-01-18_30.pdf",
        "parts": [
            {"pages": [1], "suffix": "a", "note": "SAN KYU"},
            {"pages": [2], "suffix": "b"},
        ],
    })
    assert plan.source_file == "2026-01-18_30.pdf"
    assert plan.mode == "explicit"
    assert [p.suffix for p in plan.parts] == ["a", "b"]
    assert plan.parts[0].pages == [1] and plan.parts[0].note == "SAN KYU"


def test_roundtrip_to_dict():
    plan = pdfsplit.SplitPlan("x.pdf", [pdfsplit.SplitPart([1, 2], "a", "note")])
    again = pdfsplit.parse_split_sidecar(plan.to_dict())
    assert again.to_dict() == plan.to_dict()
    assert again.to_dict()["schema"] == pdfsplit.SIDECAR_SCHEMA


def test_validate_ok():
    parts = [pdfsplit.SplitPart([1], "a"), pdfsplit.SplitPart([2], "b")]
    assert pdfsplit.validate(parts, page_count=2) == []


def test_validate_catches_off_by_one():
    # ページ3は全2ページに対し範囲外 → pypdf の IndexError を未然に明確なエラーへ。
    parts = [pdfsplit.SplitPart([1], "a"), pdfsplit.SplitPart([3], "b")]
    problems = pdfsplit.validate(parts, page_count=2)
    assert any("範囲外" in p for p in problems)


def test_validate_rejects_dup_suffix_bad_chars_empty():
    assert any("重複" in p for p in pdfsplit.validate(
        [pdfsplit.SplitPart([1], "a"), pdfsplit.SplitPart([2], "a")]
    ))
    assert any("使えない文字" in p for p in pdfsplit.validate([pdfsplit.SplitPart([1], "a/b")]))
    assert any("suffix が空" in p for p in pdfsplit.validate([pdfsplit.SplitPart([1], "")]))
    assert any("pages が空" in p for p in pdfsplit.validate([pdfsplit.SplitPart([], "a")]))
    assert any("1始まり" in p for p in pdfsplit.validate([pdfsplit.SplitPart([0], "a")]))
    assert any("パートが空" in p for p in pdfsplit.validate([]))


def test_expand_per_page():
    plan = pdfsplit.parse_split_sidecar({"source_file": "x.pdf", "mode": "per_page"})
    parts = pdfsplit.expand(plan, 3)
    assert [p.suffix for p in parts] == ["01", "02", "03"]
    assert [p.pages for p in parts] == [[1], [2], [3]]


def test_expand_explicit_passthrough():
    plan = pdfsplit.parse_split_sidecar({
        "source_file": "x.pdf", "parts": [{"pages": [1, 2], "suffix": "a"}],
    })
    assert pdfsplit.expand(plan, 5)[0].pages == [1, 2]


def test_output_name():
    part = pdfsplit.SplitPart([1], "a")
    assert pdfsplit.output_name("2026-01-18_30.pdf", part) == "2026-01-18_30_a.pdf"
    assert pdfsplit.output_name("IMG_0001.PDF", part) == "IMG_0001_a.pdf"


def test_unused_pages():
    parts = [pdfsplit.SplitPart([1], "a"), pdfsplit.SplitPart([3], "c")]
    assert pdfsplit.unused_pages(parts, 3) == [2]


def test_parse_rejects_bad_structure():
    with pytest.raises(ValueError):
        pdfsplit.parse_split_sidecar([])  # オブジェクトでない
    with pytest.raises(ValueError):
        pdfsplit.parse_split_sidecar({"source_file": "x", "parts": [{"suffix": "a"}]})  # pages 無し
