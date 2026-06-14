"""画像トリミング(scripts 層・Pillow)。原本は別名で保持し、切出し版を主ファイルにする。

core は zero-dep のため画像処理はここ(scripts/)に置く(ADR-0011)。Pillow は遅延 import し、
未導入環境でも本モジュールの import 自体は失敗しないようにする(実呼び出し時に明示エラー)。
切出し枠(box)は Claude / 将来のビジョンブリッジが提示する [left, top, right, bottom](px)。
"""

from __future__ import annotations

import shutil
from pathlib import Path

# 画像とみなす拡張子(これ以外=PDF 等はトリミングせずコピーのみ)。
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".heic"}


def is_image(path: str | Path) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTS


def crop_image(src: str | Path, dst: str | Path, box: tuple[int, int, int, int]) -> None:
    """`src` を box で切り出して `dst` に保存(拡張子で形式を決定)。"""
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - 環境依存
        raise SystemExit(
            "error: Pillow が必要です(`pip install Pillow` か optional-deps 'pipeline')"
        ) from exc

    left, top, right, bottom = (int(v) for v in box)
    with Image.open(src) as im:
        cropped = im.crop((left, top, right, bottom))
        # JPEG は RGBA/P を保存できないため RGB に倒す。
        if Path(dst).suffix.lower() in (".jpg", ".jpeg") and cropped.mode not in ("RGB", "L"):
            cropped = cropped.convert("RGB")
        cropped.save(dst)


def process_receipt(
    src: str | Path,
    primary_dst: str | Path,
    original_dst: str | Path,
    box: tuple[int, int, int, int] | None = None,
) -> dict:
    """証憑1件を処理する。原本を `original_dst` に保持し、主ファイル `primary_dst` を用意する。

    画像で box があれば切出し、無ければ(または非画像なら)原本をそのまま主ファイルにコピーする。
    返り値は実際に書いたファイルと、トリミングしたか否か。
    """
    src = Path(src)
    primary_dst = Path(primary_dst)
    original_dst = Path(original_dst)
    primary_dst.parent.mkdir(parents=True, exist_ok=True)
    original_dst.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(src, original_dst)  # 原本は常に保持(_original)
    cropped = False
    if box is not None and is_image(src):
        crop_image(src, primary_dst, tuple(box))
        cropped = True
    else:
        shutil.copy2(src, primary_dst)
    return {
        "primary": str(primary_dst),
        "original": str(original_dst),
        "cropped": cropped,
    }
