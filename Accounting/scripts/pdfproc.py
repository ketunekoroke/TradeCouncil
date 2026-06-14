"""PDF 操作(scripts 層・pypdf)。複数レシート PDF を1ファイル1レシートに分割する。

core は zero-dep のため pypdf 依存はここ(scripts/)に置く(ADR-0011)。pypdf は遅延 import し、
未導入環境でも本モジュールの import 自体は失敗しないようにする(実呼び出し時に明示エラー)。
**どのページをどの出力にするか** の計画と検証は純粋な `core/pdfsplit.py` が担い、本モジュールは
受け取ったジョブ(出力パス, 1始まりページ番号list)を pypdf で書き出すだけにする。
"""

from __future__ import annotations

from pathlib import Path


def is_pdf(path: str | Path) -> bool:
    return Path(path).suffix.lower() == ".pdf"


def _pypdf():
    try:
        import pypdf
    except ImportError as exc:  # pragma: no cover - 環境依存
        raise SystemExit(
            "error: pypdf が必要です(`pip install pypdf` か optional-deps 'pipeline')"
        ) from exc
    return pypdf


def page_count(path: str | Path) -> int:
    """PDF のページ数を返す。"""
    pypdf = _pypdf()
    reader = pypdf.PdfReader(str(path))
    return len(reader.pages)


def split_pdf(src: str | Path, jobs: list[tuple[Path, list[int]]]) -> list[Path]:
    """`src` を `jobs`(出力パス, 1始まりページ番号list)に従って分割し、書いたパスを返す。

    ページ番号は **1始まり**(`core/pdfsplit.validate` で範囲検証済みの前提)。内部で 0 始まりへ
    変換する。万一の範囲外には再防御で `ValueError` を上げる(pypdf の IndexError に頼らない)。
    """
    pypdf = _pypdf()
    src = Path(src)
    reader = pypdf.PdfReader(str(src))
    total = len(reader.pages)
    written: list[Path] = []
    for out_path, pages in jobs:
        out_path = Path(out_path)
        writer = pypdf.PdfWriter()
        for pg in pages:
            if not (1 <= pg <= total):  # core で弾く想定だが念のため再防御
                raise ValueError(f"ページ {pg} は範囲外です(全 {total} ページ): {src.name}")
            writer.add_page(reader.pages[pg - 1])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            writer.write(f)
        written.append(out_path)
    return written
