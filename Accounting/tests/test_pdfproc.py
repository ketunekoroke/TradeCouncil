"""scripts/pdfproc.py: PDF ページ数・分割(pypdf 未導入なら skip)。"""

import pytest

from scripts import pdfproc


def test_is_pdf():
    assert pdfproc.is_pdf("a.PDF") is True
    assert pdfproc.is_pdf("a.jpg") is False


def _make_pdf(path, pages):
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=300)
    with open(path, "wb") as f:
        writer.write(f)


def test_page_count(tmp_path):
    pytest.importorskip("pypdf")
    src = tmp_path / "multi.pdf"
    _make_pdf(src, 3)
    assert pdfproc.page_count(src) == 3


def test_split_pdf_writes_subsets(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    src = tmp_path / "2026-01-18_30.pdf"
    _make_pdf(src, 3)
    jobs = [
        (tmp_path / "out" / "a.pdf", [1]),
        (tmp_path / "out" / "b.pdf", [2, 3]),
    ]
    written = pdfproc.split_pdf(src, jobs)
    assert [p.name for p in written] == ["a.pdf", "b.pdf"]
    assert len(pypdf.PdfReader(str(written[0])).pages) == 1
    assert len(pypdf.PdfReader(str(written[1])).pages) == 2


def test_split_pdf_rejects_out_of_range(tmp_path):
    pytest.importorskip("pypdf")
    src = tmp_path / "s.pdf"
    _make_pdf(src, 1)
    with pytest.raises(ValueError):
        pdfproc.split_pdf(src, [(tmp_path / "o.pdf", [2])])
