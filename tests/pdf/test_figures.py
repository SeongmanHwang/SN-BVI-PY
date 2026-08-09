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


def test_promote_figure_omits_overlapping_legend_keeps_nearby_caption():
    """그림 bbox와 면적 겹침이 큰 범례만 생략. 여유 있는 캡션은 유지."""
    from korean_exam_braille.app.pdf.models import PdfFigure

    figure = PdfFigure(bbox=(100.0, 200.0, 300.0, 320.0), piece_count=1)
    lines = [
        # gap=20 > bottom gap max → 캡션 유지
        PdfLine("cap", "캡션 아래", (100.0, 340.0, 220.0, 360.0), [], 1, 0),
        PdfLine("leg", "범례 N", (120.0, 220.0, 180.0, 240.0), [], 1, 1),
        PdfLine("side", "옆 본문", (320.0, 220.0, 420.0, 240.0), [], 1, 2),
        PdfLine("above", "위 문장", (100.0, 150.0, 220.0, 170.0), [], 1, 3),
    ]
    out = promote_figures_into_lines(lines, [figure], page_number=1)
    texts = [ln.text for ln in out]
    assert FIGURE_INK in texts
    assert "범례 N" not in texts
    assert "캡션 아래" in texts
    assert "옆 본문" in texts
    assert "위 문장" in texts


def test_promote_figure_omits_bottom_legend_with_narrow_gap():
    """겹치지 않아도 바로 아래 좁은 공백이면 범례로 본다."""
    from korean_exam_braille.app.pdf.models import PdfFigure

    # figure 200–320. 줄 324–340 → gap=4, 가로 정렬
    figure = PdfFigure(bbox=(100.0, 200.0, 300.0, 320.0), piece_count=1)
    lines = [
        PdfLine("botleg", "하단 범례", (120.0, 324.0, 180.0, 340.0), [], 1, 0),
        PdfLine("cap", "완전 아래 캡션", (100.0, 350.0, 220.0, 370.0), [], 1, 1),
    ]
    out = promote_figures_into_lines(lines, [figure], page_number=1)
    texts = [ln.text for ln in out]
    assert "하단 범례" not in texts
    assert "완전 아래 캡션" in texts
    assert FIGURE_INK in texts


def test_text_dense_notebook_figure_keeps_text_and_skips_placeholder():
    """글자가 많이 얹힌 노트형 래스터는 [그림] 생략·글자 유지 (행 수 무관)."""
    from korean_exam_braille.app.pdf.models import PdfFigure

    figure = PdfFigure(bbox=(50.0, 100.0, 400.0, 400.0), piece_count=1)
    lines = [
        PdfLine("h1", "(가)와 관련하여,", (70.0, 120.0, 200.0, 140.0), [], 1, 0),
        PdfLine("q1", "공통 자원의 비극이 무엇인지 말해 보자.", (70.0, 150.0, 360.0, 170.0), [], 1, 1),
        PdfLine("q2", "일상에서 공통 자원의 사례를 찾아보자.", (70.0, 180.0, 360.0, 200.0), [], 1, 2),
        PdfLine("q3", "복도는 왜 공통 자원인가?", (70.0, 210.0, 300.0, 230.0), [], 1, 3),
        PdfLine("h2", "(나)와 관련하여,", (70.0, 260.0, 200.0, 280.0), [], 1, 4),
        PdfLine("q4", "텀블러를 씻는 과정이 환경을 오염시킨다?", (70.0, 290.0, 360.0, 310.0), [], 1, 5),
        # gap=30 → 하단 범례로 보지 않음
        PdfLine("near", "일반 본문", (50.0, 430.0, 150.0, 450.0), [], 1, 6),
    ]
    out = promote_figures_into_lines(lines, [figure], page_number=1)
    texts = [ln.text for ln in out]
    assert FIGURE_INK not in texts
    assert "(가)와 관련하여," in texts
    assert "복도는 왜 공통 자원인가?" in texts
    assert "일반 본문" in texts


def test_few_overlapping_lines_still_promotes_figure():
    """겹침 행이 많아도 글자 수가 적으면 [그림] 유지·겹친 글 생략."""
    from korean_exam_braille.app.pdf.models import PdfFigure

    figure = PdfFigure(bbox=(50.0, 100.0, 300.0, 300.0), piece_count=1)
    lines = [
        PdfLine("a", "가", (70.0, 120.0, 90.0, 140.0), [], 1, 0),
        PdfLine("b", "나", (70.0, 150.0, 90.0, 170.0), [], 1, 1),
        PdfLine("c", "다", (70.0, 180.0, 90.0, 200.0), [], 1, 2),
        PdfLine("d", "라", (70.0, 210.0, 90.0, 230.0), [], 1, 3),
        PdfLine("e", "본문", (50.0, 330.0, 100.0, 350.0), [], 1, 4),
    ]
    out = promote_figures_into_lines(lines, [figure], page_number=1)
    texts = [ln.text for ln in out]
    assert FIGURE_INK in texts
    assert "가" not in texts
    assert "라" not in texts
    assert "본문" in texts


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
