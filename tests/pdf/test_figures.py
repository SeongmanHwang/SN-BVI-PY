"""래스터 그림 검출·[그림] 승격."""

from __future__ import annotations

from pathlib import Path

import fitz

from korean_exam_braille.app.common.figure_markup import (
    FIGURE_BRAILLE_ASCII,
    FIGURE_INK,
)
from korean_exam_braille.app.pdf.extractor import extract_pdf
from korean_exam_braille.app.pdf.figures import (
    detect_raster_figures,
    promote_figures_into_lines,
)
from korean_exam_braille.app.pdf.models import PdfLine, PdfPageStructure


def _insert_strip_images(page: fitz.Page, xs: tuple[float, float], ys: list[float]) -> None:
    """시험지처럼 세로로 잘린 래스터 조각을 넣는다."""
    for top, bottom in zip(ys, ys[1:]):
        height = max(int(bottom - top), 8)
        width = max(int(xs[1] - xs[0]), 8)
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, width, height), False)
        pix.set_rect(pix.irect, (180, 120, 90))
        page.insert_image(fitz.Rect(xs[0], top, xs[1], bottom), pixmap=pix)


def test_merge_sliced_images_into_one_figure():
    doc = fitz.open()
    page = doc.new_page(width=850, height=1100)
    xs = (459.3, 544.2)
    ys = [722.4, 737.5, 752.6, 767.7, 782.8, 797.5]
    _insert_strip_images(page, xs, ys)

    figures = detect_raster_figures(page)
    assert len(figures) == 1
    assert figures[0].piece_count >= 2
    assert abs(figures[0].bbox[0] - xs[0]) < 2.0
    assert abs(figures[0].bbox[2] - xs[1]) < 2.0
    assert abs(figures[0].bbox[1] - ys[0]) < 2.0
    assert abs(figures[0].bbox[3] - ys[-1]) < 2.0
    doc.close()


def test_promote_figure_inserts_placeholder_line():
    lines = [
        PdfLine("a", "before", (100, 100, 200, 120), [], 1, 0),
        PdfLine("b", "after", (100, 300, 200, 320), [], 1, 1),
    ]
    from korean_exam_braille.app.pdf.models import PdfFigure

    figures = [PdfFigure(bbox=(120, 200, 280, 280), piece_count=3)]
    out = promote_figures_into_lines(lines, figures, page_number=1)
    texts = [ln.text for ln in out]
    assert texts == ["before", FIGURE_INK, "after"]


def test_extractor_tags_figure_asset(tmp_path: Path):
    doc = fitz.open()
    page = doc.new_page(width=850, height=1100)
    page.insert_text((100, 180), "caption near figure", fontsize=11)
    _insert_strip_images(page, (100.0, 280.0), [200.0, 240.0, 280.0, 320.0])
    path = tmp_path / "figure.pdf"
    doc.save(path)
    doc.close()

    page_struct = extract_pdf(path, page_numbers=[1]).pages[0]
    assert len(page_struct.figures) == 1
    assert any(FIGURE_INK in (ln.text or "") for ln in page_struct.lines)
    assert any("FigureAsset" in (b.candidate_tags or []) for b in page_struct.blocks)

    restored = PdfPageStructure.from_dict(page_struct.to_dict())
    assert restored.figures[0].piece_count >= 2
