"""중략 줄거리 구간 끝 표지 검출."""

from __future__ import annotations

from pathlib import Path

import fitz

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line
from korean_exam_braille.app.common.plot_summary_markup import (
    PLOT_SUMMARY_END_BRAILLE_ASCII,
    PLOT_SUMMARY_END_INK,
)
from korean_exam_braille.app.pdf.extractor import extract_pdf
from korean_exam_braille.app.pdf.models import PdfLine, PdfSpan
from korean_exam_braille.app.pdf.plot_summary import annotate_plot_summary_lines


def _span(
    sid: str,
    text: str,
    *,
    font: str,
    size: float,
    y0: float,
    y1: float | None = None,
    x0: float = 50.0,
    x1: float = 300.0,
) -> PdfSpan:
    bottom = y1 if y1 is not None else y0 + size
    return PdfSpan(
        id=sid,
        text=text,
        bbox=(x0, y0, x1, bottom),
        font=font,
        font_size=size,
        is_bold=False,
        page_number=1,
        extraction_index=int(sid.split("s")[-1]) if "s" in sid else 0,
    )


def _line(lid: str, text: str, spans: list[PdfSpan], order: int) -> PdfLine:
    y0 = min(s.bbox[1] for s in spans)
    y1 = max(s.bbox[3] for s in spans)
    x0 = min(s.bbox[0] for s in spans)
    x1 = max(s.bbox[2] for s in spans)
    return PdfLine(
        id=lid,
        text=text,
        bbox=(x0, y0, x1, y1),
        span_ids=[s.id for s in spans],
        page_number=1,
        reading_order=order,
    )


def test_annotate_inserts_end_after_dotum_run():
    body_a = _span("s0", "본문 앞.", font="HaansoftBatang", size=11.15, y0=100)
    cue = _span(
        "s1",
        "[중략 부분의 줄거리] 부용 남매는",
        font="HaansoftDotum",
        size=9.72,
        y0=140,
    )
    more = _span(
        "s2",
        "강남에 올라가니",
        font="HaansoftDotum",
        size=9.72,
        y0=160,
    )
    body_b = _span("s3", "본문 뒤.", font="HaansoftBatang", size=11.15, y0=200)
    spans = [body_a, cue, more, body_b]
    lines = [
        _line("l0", body_a.text, [body_a], 0),
        _line("l1", cue.text, [cue], 1),
        _line("l2", more.text, [more], 2),
        _line("l3", body_b.text, [body_b], 3),
    ]
    out = annotate_plot_summary_lines(lines, spans, page_number=1)
    texts = [ln.text for ln in out]
    assert texts == [
        "본문 앞.",
        "[중략 부분의 줄거리] 부용 남매는",
        "강남에 올라가니",
        PLOT_SUMMARY_END_INK,
        "본문 뒤.",
    ]


def test_annotate_requires_cue_marker():
    """표지 없이 돋움만 있으면 삽입하지 않는다."""
    s0 = _span("s0", "작은 돋움 본문", font="HaansoftDotum", size=9.72, y0=100)
    s1 = _span("s1", "이어서", font="HaansoftDotum", size=9.72, y0=120)
    spans = [s0, s1]
    lines = [
        _line("l0", s0.text, [s0], 0),
        _line("l1", s1.text, [s1], 1),
    ]
    out = annotate_plot_summary_lines(lines, spans, page_number=1)
    assert all(ln.text != PLOT_SUMMARY_END_INK for ln in out)


def test_plot_summary_end_braille_roundtrip():
    assert hangul_text_to_ascii(PLOT_SUMMARY_END_INK) == PLOT_SUMMARY_END_BRAILLE_ASCII
    assert reverse_translate_line(PLOT_SUMMARY_END_BRAILLE_ASCII) == PLOT_SUMMARY_END_INK


def test_extractor_inserts_plot_summary_end(tmp_path: Path):
    batang = Path(r"C:\Windows\Fonts\batang.ttc")
    gulim = Path(r"C:\Windows\Fonts\gulim.ttc")
    if not batang.is_file() or not gulim.is_file():
        batang = Path(r"C:\Windows\Fonts\times.ttf")
        gulim = Path(r"C:\Windows\Fonts\arial.ttf")
    if not batang.is_file() or not gulim.is_file():
        import pytest

        pytest.skip("serif/sans test fonts unavailable")

    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    page.insert_font(fontname="body", fontfile=str(batang))
    page.insert_font(fontname="sum", fontfile=str(gulim))
    page.insert_text((50, 80), "형제는 한 몸이라 하오니", fontsize=11, fontname="body")
    page.insert_text(
        (50, 160),
        "[중략 부분의 줄거리] 부용 남매는 떠났고",
        fontsize=9.5,
        fontname="sum",
    )
    page.insert_text((50, 180), "강남에 올라가니 소식이 없더라", fontsize=9.5, fontname="sum")
    page.insert_text((50, 260), "다시 본문이 이어진다", fontsize=11, fontname="body")
    path = tmp_path / "plot_summary.pdf"
    doc.save(path)
    doc.close()

    page_struct = extract_pdf(path, page_numbers=[1]).pages[0]
    texts = [ln.text for ln in page_struct.lines]
    assert any("[중략 부분의 줄거리]" in (t or "") for t in texts)
    assert PLOT_SUMMARY_END_INK in texts
    cue_i = next(i for i, t in enumerate(texts) if "[중략 부분의 줄거리]" in (t or ""))
    end_i = texts.index(PLOT_SUMMARY_END_INK)
    body_i = next(i for i, t in enumerate(texts) if "다시 본문이 이어진다" in (t or ""))
    assert cue_i < end_i < body_i
