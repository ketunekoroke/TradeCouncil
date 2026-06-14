"""scripts/imageproc.py: 画像トリミングと原本保持(Pillow 未導入なら skip)。"""

import pytest

from scripts import imageproc


def test_is_image():
    assert imageproc.is_image("a.JPG") is True
    assert imageproc.is_image("a.pdf") is False


def test_process_receipt_crops_image(tmp_path):
    pimage = pytest.importorskip("PIL.Image")
    src = tmp_path / "r.png"
    pimage.new("RGB", (100, 80), (255, 0, 0)).save(src)
    primary = tmp_path / "out" / "2026-05-30_AWS.png"
    original = tmp_path / "out" / "2026-05-30_AWS_original.png"
    res = imageproc.process_receipt(src, primary, original, box=(10, 10, 60, 50))
    assert res["cropped"] is True
    with pimage.open(primary) as im:
        assert im.size == (50, 40)  # 切出し後
    with pimage.open(original) as im:
        assert im.size == (100, 80)  # 原本は無加工


def test_process_receipt_no_box_copies(tmp_path):
    src = tmp_path / "r.pdf"
    src.write_bytes(b"%PDF-1.4 fake")
    primary = tmp_path / "o" / "r.pdf"
    original = tmp_path / "o" / "r_original.pdf"
    res = imageproc.process_receipt(src, primary, original, box=None)
    assert res["cropped"] is False
    assert primary.read_bytes() == b"%PDF-1.4 fake"
    assert original.read_bytes() == b"%PDF-1.4 fake"
