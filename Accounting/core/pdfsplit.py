"""PDF 分割の計画(zero-dep・純粋)。実 pypdf 操作は `scripts/pdfproc.py`。

1ファイルに複数のレシートが入った PDF を「1ファイル1レシート」に分けるための計画
(どのページをどの出力にするか)を、Claude が書く **分割サイドカー**
(`var/expense/split/<raw>.json`)から型と検証付きで読む。**ページ番号は1始まり**で扱い、
範囲外(off-by-one)や空パートをここで弾いてから pypdf に渡す(pypdf の不透明な
`IndexError` を未然に明確なメッセージへ変える)。

**複数ページ = 複数レシートとは限らない**(1枚のレシートが2ページにわたることもある)。
よって分割は **分割サイドカーで明示されたファイルだけ** に行い、ページ数からの自動分割はしない。

サイドカーの形:
  {
    "schema": "ac.expense.split/v1",
    "source_file": "2026-01-18_30.pdf",   # raw/ 配下の元 PDF 名
    "mode": "explicit",                     # explicit(既定・parts を使う) | per_page
    "parts": [
      {"pages": [1], "suffix": "a", "note": "SAN KYU"},
      {"pages": [2], "suffix": "b", "note": "2nd STREET"}
    ]
  }
mode=per_page のとき parts は省略可(実ページ数から 1ページ=1パートを自動生成。suffix=連番)。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SIDECAR_SCHEMA = "ac.expense.split/v1"
MODE_EXPLICIT = "explicit"
MODE_PER_PAGE = "per_page"

# suffix に使える文字(ファイル名片・パス区切りを弾く)。英数 + 日本語 + `_` `-` のみ。
_SUFFIX_OK = re.compile(r"^[0-9A-Za-z぀-ヿ一-鿿ー_-]+$")


@dataclass
class SplitPart:
    """分割後の1ファイル(=1レシート想定)。`pages` は1始まりのページ番号。"""

    pages: list[int]
    suffix: str
    note: str = ""

    def to_dict(self) -> dict:
        return {"pages": list(self.pages), "suffix": self.suffix, "note": self.note}

    @classmethod
    def from_dict(cls, d: dict) -> SplitPart:
        if not isinstance(d, dict):
            raise ValueError("part は JSON オブジェクトである必要があります")
        pages = d.get("pages")
        if pages is None:
            raise ValueError("part に pages がありません")
        try:
            pages = [int(x) for x in pages]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"pages が整数の配列ではありません: {pages!r}") from exc
        return cls(
            pages=pages,
            suffix=str(d.get("suffix") or "").strip(),
            note=str(d.get("note") or ""),
        )


@dataclass
class SplitPlan:
    """1つの元 PDF をどう分けるかの計画。"""

    source_file: str
    parts: list[SplitPart]
    mode: str = MODE_EXPLICIT

    def to_dict(self) -> dict:
        return {
            "schema": SIDECAR_SCHEMA,
            "source_file": self.source_file,
            "mode": self.mode,
            "parts": [p.to_dict() for p in self.parts],
        }

    @classmethod
    def from_dict(cls, d: dict) -> SplitPlan:
        if not isinstance(d, dict):
            raise ValueError("分割サイドカーは JSON オブジェクトである必要があります")
        mode = str(d.get("mode") or MODE_EXPLICIT).strip().lower()
        raw_parts = d.get("parts") or []
        if not isinstance(raw_parts, list):
            raise ValueError("parts は配列である必要があります")
        parts = [SplitPart.from_dict(p) for p in raw_parts]
        return cls(source_file=str(d.get("source_file") or ""), parts=parts, mode=mode)


def parse_split_sidecar(d: dict) -> SplitPlan:
    """分割サイドカー(dict)を `SplitPlan` にする。構造が壊れていれば ValueError。"""
    return SplitPlan.from_dict(d)


def per_page_parts(page_count: int) -> list[SplitPart]:
    """1ページ=1パートを生成する(suffix は2桁以上の連番 01..NN)。"""
    if page_count < 1:
        return []
    width = max(2, len(str(page_count)))
    return [SplitPart(pages=[i], suffix=str(i).zfill(width)) for i in range(1, page_count + 1)]


def expand(plan: SplitPlan, page_count: int) -> list[SplitPart]:
    """mode に応じて具体的な parts を返す。per_page は実ページ数から生成し、explicit はそのまま。"""
    if plan.mode == MODE_PER_PAGE and not plan.parts:
        return per_page_parts(page_count)
    return list(plan.parts)


def validate(parts: list[SplitPart], *, page_count: int | None = None) -> list[str]:
    """分割計画の妥当性を検査し、問題の一覧を返す(空なら合格)。

    ページ番号は1始まり。`page_count` を渡すと範囲外(off-by-one)を弾く。suffix は重複・
    ファイル名に使えない文字・空を弾く(出力名衝突や不正パスを防ぐ)。
    """
    problems: list[str] = []
    if not parts:
        problems.append("分割パートが空です(parts が空 / per_page でページ数 0)")
    seen_suffix: set[str] = set()
    for i, part in enumerate(parts):
        where = f"part[{i}]"
        if not part.suffix:
            problems.append(f"{where}: suffix が空です")
        elif not _SUFFIX_OK.match(part.suffix):
            problems.append(f"{where}: suffix にファイル名に使えない文字: {part.suffix!r}")
        elif part.suffix in seen_suffix:
            problems.append(f"{where}: suffix が重複しています: {part.suffix!r}")
        else:
            seen_suffix.add(part.suffix)
        if not part.pages:
            problems.append(f"{where}: pages が空です")
        for pg in part.pages:
            if pg < 1:
                problems.append(f"{where}: ページ番号は1始まりです: {pg}")
            elif page_count is not None and pg > page_count:
                problems.append(f"{where}: ページ {pg} は範囲外です(全 {page_count} ページ)")
    return problems


def output_name(source_file: str, part: SplitPart, *, ext: str = "pdf") -> str:
    """分割後ファイル名 `<元ステム>_<suffix>.<ext>`。元の拡張子は問わない(出力は PDF)。"""
    stem = source_file.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if "." in stem:
        stem = stem.rsplit(".", 1)[0]
    ext = (ext or "pdf").lstrip(".").lower()
    return f"{stem}_{part.suffix}.{ext}"


def unused_pages(parts: list[SplitPart], page_count: int) -> list[int]:
    """どのパートにも含まれないページ(取りこぼし確認用・情報)。"""
    used = {pg for part in parts for pg in part.pages}
    return [pg for pg in range(1, page_count + 1) if pg not in used]
