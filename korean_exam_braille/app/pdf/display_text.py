"""추출 텍스트 표시용 — 불투명 정규화·밑줄 구간 표시."""

from __future__ import annotations

from korean_exam_braille.app.common.opaque_text import (
    OPAQUE_REPLACEMENT,
    is_opaque_char,
    replace_opaque_with_slash,
)
from korean_exam_braille.app.pdf.emphasis import annotate_text_with_underline_ranges
from korean_exam_braille.app.pdf.models import PdfPageStructure

__all__ = [
    "OPAQUE_REPLACEMENT",
    "annotate_opaque_codepoints",
    "format_page_text_for_display",
    "is_opaque_char",
    "replace_opaque_with_slash",
]


def annotate_opaque_codepoints(text: str) -> str:
    """호환용: 불투명 문자를 빗금으로 바꾼다."""
    return replace_opaque_with_slash(text)


def format_page_text_for_display(page: PdfPageStructure) -> str:
    """읽기 순서 블록 텍스트 + 부분 밑줄 ``<u>…</u>`` 표시.

    변환 파이프라인의 ``block.text``에도 동일 마커가 들어가며, 점역기가
    강조부호로 변환한다. 이 함수는 표시용 재구성( span 기준 )에 쓴다.
    """
    spans_by_id = {s.id: s for s in page.spans}
    lines_by_id = {ln.id: ln for ln in page.lines}
    parts: list[str] = []
    for block in sorted(page.blocks, key=lambda b: b.reading_order):
        line_texts: list[str] = []
        for lid in block.line_ids:
            line = lines_by_id.get(lid)
            if line is None:
                continue
            if line.span_ids:
                chunk = "".join(
                    annotate_text_with_underline_ranges(
                        sp.text, sp.underline_ranges
                    )
                    if (sp := spans_by_id.get(sid)) is not None
                    else ""
                    for sid in line.span_ids
                )
                # line_builder는 span을 공백 정규화해 붙이기도 함 — 표시는
                # span 연결을 우선하고, 비면 line.text 사용
                text = chunk if chunk.strip() else (line.text or "")
            else:
                text = line.text or ""
            text = replace_opaque_with_slash(text).strip()
            if text:
                line_texts.append(text)
        if line_texts:
            parts.append("\n".join(line_texts))
    return "\n\n".join(parts)
