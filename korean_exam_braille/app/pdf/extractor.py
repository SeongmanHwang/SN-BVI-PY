"""PDF에서 문자(span)를 추출한다."""

from __future__ import annotations

from pathlib import Path

import fitz

from korean_exam_braille.app.pdf.block_builder import build_blocks
from korean_exam_braille.app.pdf.boxes import line_mostly_in_box
from korean_exam_braille.app.pdf.bracket_groups import (
    annotate_blocks_with_brackets,
    assign_lines_to_brackets,
    detect_bracket_geometries,
    remove_detected_label_text,
)
from korean_exam_braille.app.pdf.candidates import detect_block_candidates
from korean_exam_braille.app.common.opaque_text import replace_opaque_with_slash
from korean_exam_braille.app.pdf.emphasis import mark_underlined_spans
from korean_exam_braille.app.pdf.graphic_linearize import linearize_page_graphics
from korean_exam_braille.app.pdf.layout_profile import PageLayoutProfile, infer_layout_profile
from korean_exam_braille.app.pdf.line_builder import build_lines
from korean_exam_braille.app.pdf.models import (
    PdfDocumentStructure,
    PdfPageStructure,
    PdfSpan,
)
from korean_exam_braille.app.pdf.figures import FIGURE_INK, detect_raster_figures
from korean_exam_braille.app.pdf.tables import (
    clear_underlines_inside_tables,
    detect_vector_tables,
)
from korean_exam_braille.app.pdf.reading_order import assign_reading_order


def _is_bold(flags: int, font_name: str) -> bool:
    if flags & 16:
        return True
    lower = font_name.lower()
    return "bold" in lower or "black" in lower or "heavy" in lower


def extract_page_spans(page: fitz.Page, page_number: int) -> list[PdfSpan]:
    """한 페이지의 텍스트 span을 추출 순서대로 반환.

    rawdict로 글자 bbox를 함께 두어 부분 밑줄 구간에 쓴다.
    """
    spans: list[PdfSpan] = []
    data = page.get_text("rawdict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
    index = 0
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                chars = span.get("chars") or []
                if chars:
                    raw_chars = [str(c.get("c") or "") for c in chars]
                    char_bboxes: list[tuple[float, float, float, float]] = []
                    for c in chars:
                        bb = c.get("bbox") or (0, 0, 0, 0)
                        char_bboxes.append(
                            (float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3]))
                        )
                    raw_text = "".join(raw_chars)
                else:
                    raw_text = span.get("text") or ""
                    char_bboxes = []

                text = replace_opaque_with_slash(raw_text)
                if text == "":
                    continue
                # opaque 치환으로 길이가 달라지면 글자 bbox 정렬이 깨지므로 포기
                if char_bboxes and len(char_bboxes) != len(text):
                    char_bboxes = []

                bbox = tuple(float(x) for x in span["bbox"])
                font = str(span.get("font", ""))
                size = float(span.get("size", 0.0))
                flags = int(span.get("flags", 0))
                spans.append(
                    PdfSpan(
                        id=f"p{page_number}-s{index}",
                        text=text,
                        bbox=(bbox[0], bbox[1], bbox[2], bbox[3]),
                        font=font,
                        font_size=size,
                        is_bold=_is_bold(flags, font),
                        page_number=page_number,
                        extraction_index=index,
                        is_underline=False,
                        char_bboxes=char_bboxes,
                    )
                )
                index += 1
    return spans


def build_page_structure(
    page: fitz.Page,
    page_number: int,
    *,
    profile: PageLayoutProfile | None = None,
) -> PdfPageStructure:
    rect = page.rect
    spans = extract_page_spans(page, page_number)
    tables = detect_vector_tables(page, spans)
    figures = detect_raster_figures(page)
    mark_underlined_spans(page, spans)
    clear_underlines_inside_tables(spans, tables)
    # drawing과 원래 PDF 텍스트로 괄호를 먼저 찾은 뒤, 공백에 인쇄된
    # 물리적 [A]~[E]만 텍스트에서 제거한다. 의미는 아래 메타데이터로 보존.
    bracket_groups = detect_bracket_geometries(page)
    remove_detected_label_text(spans, bracket_groups)
    spans = [span for span in spans if span.text]
    lines = build_lines(
        spans,
        page_number,
        page_width=float(rect.width),
        profile=profile,
    )
    # 향찰: 밑줄 본문 행 / 원문자 행 분리·병합 + 표·그림 승격 + 박스 표선
    lines = linearize_page_graphics(page, lines, tables=tables, figures=figures)
    # 오른쪽 여백 [A]~[E] 꺾인 괄호 → 행 소속
    assign_lines_to_brackets(lines, bracket_groups)
    blocks = build_blocks(lines, page_number, profile=profile)
    assign_reading_order(blocks, profile=profile)
    for block in blocks:
        band = profile.band_of_y(block.bbox[1]) if profile is not None else None
        block.candidate_tags = detect_block_candidates(block.text, band=band)
        if any(
            line_mostly_in_box(block.bbox, table.bbox, min_overlap=0.3)
            for table in tables
        ):
            block.candidate_tags.append("TableAsset")
        if any(
            line_mostly_in_box(block.bbox, figure.bbox, min_overlap=0.3)
            or FIGURE_INK in (block.text or "")
            for figure in figures
        ):
            block.candidate_tags.append("FigureAsset")
        block.candidate_tags = list(dict.fromkeys(block.candidate_tags))
    annotate_blocks_with_brackets(blocks, lines, bracket_groups)
    return PdfPageStructure(
        page_number=page_number,
        width=float(rect.width),
        height=float(rect.height),
        spans=spans,
        lines=lines,
        blocks=blocks,
        tables=tables,
        figures=figures,
        bracket_groups=bracket_groups,
    )


def extract_pdf(
    path: str | Path,
    *,
    page_numbers: list[int] | None = None,
    profile: PageLayoutProfile | None = None,
) -> PdfDocumentStructure:
    """PDF 전체 또는 지정 면(1-based)을 구조로 추출.

    프로필이 없으면 문서 전체에서 공통 2단·헤더·푸터를 한 번 추론해
    모든 면에 동일하게 적용한다.
    """
    path = Path(path)
    doc = fitz.open(path)
    try:
        layout = profile or infer_layout_profile(doc)
        selected = page_numbers or list(range(1, doc.page_count + 1))
        pages: list[PdfPageStructure] = []
        for num in selected:
            if num < 1 or num > doc.page_count:
                continue
            pages.append(build_page_structure(doc[num - 1], num, profile=layout))
        return PdfDocumentStructure(
            source_path=str(path),
            page_count=doc.page_count,
            pages=pages,
            metadata={
                "title": doc.metadata.get("title") if doc.metadata else None,
                "extracted_pages": [p.page_number for p in pages],
                "layout_profile": layout.to_dict(),
            },
        )
    finally:
        doc.close()


def render_page_pixmap(path: str | Path, page_number: int, *, zoom: float = 2.0) -> bytes:
    """페이지를 PNG 바이트로 렌더링."""
    path = Path(path)
    doc = fitz.open(path)
    try:
        page = doc[page_number - 1]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()
