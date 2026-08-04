"""BRF 텍스트·문서 비교 — Prototype 3 품질 루프용."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from korean_exam_braille.app.brf.ascii_braille import FORM_FEED, normalize_brf_ascii
from korean_exam_braille.app.brf.models import BrfDocument
from korean_exam_braille.app.brf.parser import load_brf, parse_brf_text


@dataclass
class LineDiff:
    page_index: int
    line_index: int
    generated: str
    reference: str
    cell_equal: int
    cell_total: int

    @property
    def match_ratio(self) -> float:
        if self.cell_total == 0:
            return 1.0 if self.generated == self.reference else 0.0
        return self.cell_equal / self.cell_total


@dataclass
class BrfCompareResult:
    generated_pages: int
    reference_pages: int
    generated_lines: int
    reference_lines: int
    matched_lines: int
    cell_equal: int
    cell_total: int
    diffs: list[LineDiff] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def line_match_ratio(self) -> float:
        denom = max(self.generated_lines, self.reference_lines, 1)
        return self.matched_lines / denom

    @property
    def cell_match_ratio(self) -> float:
        if self.cell_total == 0:
            return 1.0
        return self.cell_equal / self.cell_total

    def summary(self, *, max_diffs: int = 12) -> str:
        lines = [
            f"면 {self.generated_pages}/{self.reference_pages} "
            f"(생성/참고)",
            f"행 {self.generated_lines}/{self.reference_lines} · "
            f"완전일치 {self.matched_lines} "
            f"({self.line_match_ratio:.1%})",
            f"셀 일치 {self.cell_equal}/{self.cell_total} "
            f"({self.cell_match_ratio:.1%})",
        ]
        if self.diffs:
            lines.append("차이 예시:")
            for d in self.diffs[:max_diffs]:
                lines.append(
                    f"  p{d.page_index + 1} L{d.line_index + 1} "
                    f"({d.match_ratio:.0%})"
                )
                lines.append(f"    gen: {d.generated!r}")
                lines.append(f"    ref: {d.reference!r}")
            if len(self.diffs) > max_diffs:
                lines.append(f"  … 외 {len(self.diffs) - max_diffs}건")
        return "\n".join(lines)


def _pages_from_text(text: str) -> list[list[str]]:
    doc = parse_brf_text(text)
    return [[ln.raw_ascii for ln in page.lines] for page in doc.pages]


def _pages_from_document(doc: BrfDocument) -> list[list[str]]:
    return [[ln.raw_ascii for ln in page.lines] for page in doc.pages]


def _norm_line(s: str) -> str:
    return normalize_brf_ascii(s.rstrip("\r\n")).rstrip()


def _cell_overlap(a: str, b: str) -> tuple[int, int]:
    a_n, b_n = _norm_line(a), _norm_line(b)
    n = max(len(a_n), len(b_n))
    if n == 0:
        return 1, 1
    eq = sum(1 for i in range(n) if i < len(a_n) and i < len(b_n) and a_n[i] == b_n[i])
    return eq, n


def compare_page_lines(
    generated: list[list[str]],
    reference: list[list[str]],
    *,
    page_limit: int | None = None,
    max_diffs: int = 200,
) -> BrfCompareResult:
    """면·행 정렬 비교 (같은 인덱스의 행끼리)."""
    g_pages = generated[:page_limit] if page_limit else generated
    r_pages = reference[:page_limit] if page_limit else reference
    n_pages = max(len(g_pages), len(r_pages))

    matched = 0
    cell_eq = 0
    cell_tot = 0
    diffs: list[LineDiff] = []
    g_lines = 0
    r_lines = 0

    for pi in range(n_pages):
        g_ls = g_pages[pi] if pi < len(g_pages) else []
        r_ls = r_pages[pi] if pi < len(r_pages) else []
        g_lines += len(g_ls)
        r_lines += len(r_ls)
        n_lines = max(len(g_ls), len(r_ls))
        for li in range(n_lines):
            g = g_ls[li] if li < len(g_ls) else ""
            r = r_ls[li] if li < len(r_ls) else ""
            eq, tot = _cell_overlap(g, r)
            cell_eq += eq
            cell_tot += tot
            if _norm_line(g) == _norm_line(r):
                matched += 1
            elif len(diffs) < max_diffs:
                diffs.append(
                    LineDiff(
                        page_index=pi,
                        line_index=li,
                        generated=g,
                        reference=r,
                        cell_equal=eq,
                        cell_total=tot,
                    )
                )

    return BrfCompareResult(
        generated_pages=len(g_pages),
        reference_pages=len(r_pages),
        generated_lines=g_lines,
        reference_lines=r_lines,
        matched_lines=matched,
        cell_equal=cell_eq,
        cell_total=cell_tot,
        diffs=diffs,
    )


def compare_brf_texts(
    generated_text: str,
    reference_text: str,
    *,
    page_limit: int | None = None,
) -> BrfCompareResult:
    return compare_page_lines(
        _pages_from_text(generated_text),
        _pages_from_text(reference_text),
        page_limit=page_limit,
    )


def compare_to_reference_file(
    generated_text: str,
    reference_path: str | Path,
    *,
    page_limit: int | None = None,
) -> BrfCompareResult:
    ref = load_brf(reference_path)
    result = compare_page_lines(
        _pages_from_text(generated_text),
        _pages_from_document(ref),
        page_limit=page_limit,
    )
    result.metadata["reference_path"] = str(reference_path)
    return result


def join_pages(pages: list[list[str]]) -> str:
    return FORM_FEED.join("\n".join(lines) for lines in pages)
