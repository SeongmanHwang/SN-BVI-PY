# -*- coding: utf-8 -*-
"""PdfSpan → PdfLine 기하 재구성."""

from korean_exam_braille.app.pdf.line_builder import build_lines
from korean_exam_braille.app.pdf.models import PdfSpan


def _span(
    idx: int,
    text: str,
    *,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    size: float = 11.0,
    bold: bool = False,
) -> PdfSpan:
    return PdfSpan(
        id=f"s{idx}",
        text=text,
        bbox=(x0, y0, x1, y1),
        font="Test",
        font_size=size,
        is_bold=bold,
        page_number=1,
        extraction_index=idx,
    )


def test_inline_size_split_spans_stay_one_line_in_x_order():
    """글자 크기만 다른 인라인 span이 한 줄로 좌→우 재조립된다.

    2026-6 고2 15면 「과 괴석 등은 모두 나와…」: size 11.0/11.2가
    y0만 어긋나며, 옛 y0정렬+가로gap이 '은 모두'를 분리했다.
    """
    # extraction_index는 의도적으로 뒤섞인 순서를 흉내
    spans = [
        _span(22, "과 괴석 등", x0=105.84, x1=161.18, y0=391.68, y1=402.72, size=11.04),
        _span(24, "나와 함께 떠다니는 것", x0=205.92, x1=320.54, y0=391.68, y1=402.72, size=11.04),
        _span(25, "입니다. 떠다니다", x0=320.52, x1=404.28, y0=391.58, y1=402.73, size=11.15),
        _span(23, "은 모두 ", x0=161.16, x1=202.92, y0=391.58, y1=402.73, size=11.15),
    ]
    lines = build_lines(spans, page_number=15, y_tolerance=3.0, page_width=800.0)
    body = [ln.text for ln in lines if (ln.text or "").strip()]
    assert len(body) == 1, body
    assert body[0] == "과 괴석 등은 모두 나와 함께 떠다니는 것입니다. 떠다니다"
    assert "은 모두" not in [ln.text for ln in lines if ln.text == "은 모두"]


def test_bold_flag_does_not_drive_line_order():
    """bold는 스타일만 — 줄 순서는 bbox."""
    spans = [
        _span(1, "뒤에", x0=200, x1=250, y0=100.1, y1=111, bold=True),
        _span(0, "앞에 ", x0=100, x1=150, y0=100.0, y1=111, bold=False),
    ]
    lines = build_lines(spans, page_number=1, y_tolerance=3.0, page_width=400.0)
    assert len(lines) == 1
    assert lines[0].text == "앞에 뒤에"
