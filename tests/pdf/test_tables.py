"""벡터 셀 기반 표 격자·텍스트 복원."""

from __future__ import annotations

from pathlib import Path

import fitz

from korean_exam_braille.app.pdf.extractor import extract_page_spans, extract_pdf
from korean_exam_braille.app.pdf.models import PdfPageStructure
from korean_exam_braille.app.pdf.tables import (
    detect_vector_tables,
    vector_table_diagnostics,
)


def _make_table_page() -> tuple[fitz.Document, fitz.Page]:
    doc = fitz.open()
    page = doc.new_page(width=850, height=700)
    xs = [453.3, 495.9, 577.9, 660.0, 742.0]
    ys = [525.6, 547.0, 568.3]
    values = [
        ["kind", "yes", "no", "unknown"],
        ["rate", "71%", "24%", "5%"],
    ]

    for row in range(2):
        for column in range(4):
            rect = fitz.Rect(xs[column], ys[row], xs[column + 1], ys[row + 1])
            # 실제 PDF처럼 같은 셀을 re로 중복 표현.
            page.draw_rect(rect, width=0.5)
            page.draw_rect(rect, width=0.5)
            page.insert_text(
                (rect.x0 + 3.0, rect.y0 + 14.0),
                values[row][column],
                fontsize=7,
            )

    # 동일 경계를 별도 line으로도 다시 표현.
    for x in xs:
        page.draw_line(fitz.Point(x, ys[0]), fitz.Point(x, ys[-1]), width=0.5)
    for y in ys:
        page.draw_line(fitz.Point(xs[0], y), fitz.Point(xs[-1], y), width=0.5)
    return doc, page


def test_detect_four_column_two_row_vector_table():
    doc, page = _make_table_page()
    spans = extract_page_spans(page, 1)
    tables = detect_vector_tables(page, spans)

    assert len(tables) == 1
    table = tables[0]
    assert table.row_count == 2
    assert table.column_count == 4
    assert len(table.cells) == 8
    assert [[c.text for c in table.cells if c.row == row] for row in range(2)] == [
        ["kind", "yes", "no", "unknown"],
        ["rate", "71%", "24%", "5%"],
    ]
    assert abs(table.bbox[0] - 453.3) < 1.0
    assert abs(table.bbox[2] - 742.0) < 1.0
    doc.close()


def test_extractor_preserves_table_and_tags_blocks(tmp_path: Path):
    doc, _page = _make_table_page()
    path = tmp_path / "table.pdf"
    doc.save(path)
    doc.close()

    extracted = extract_pdf(path, page_numbers=[1])
    page = extracted.pages[0]
    assert len(page.tables) == 1
    assert any("TableAsset" in block.candidate_tags for block in page.blocks)

    restored = PdfPageStructure.from_dict(page.to_dict())
    assert restored.tables[0].column_count == 4
    assert restored.tables[0].cells[5].text == "71%"


def test_detect_shared_line_grid_without_cell_rects():
    """개별 re가 없어도 공유 수평·수직선만으로 2×4 표를 복원한다."""
    doc = fitz.open()
    page = doc.new_page(width=850, height=700)
    xs = [453.3, 495.9, 577.9, 660.0, 742.0]
    ys = [525.6, 547.0, 568.3]
    values = [
        ["kind", "yes", "no", "unknown"],
        ["rate", "71%", "24%", "5%"],
    ]
    for x in xs:
        page.draw_line(fitz.Point(x, ys[0]), fitz.Point(x, ys[-1]), width=0.5)
    for y in ys:
        page.draw_line(fitz.Point(xs[0], y), fitz.Point(xs[-1], y), width=0.5)
    for row in range(2):
        for column in range(4):
            page.insert_text(
                (xs[column] + 3.0, ys[row] + 14.0),
                values[row][column],
                fontsize=7,
            )

    tables = detect_vector_tables(page, extract_page_spans(page, 1))
    assert len(tables) == 1
    assert (tables[0].row_count, tables[0].column_count) == (2, 4)
    assert [cell.text for cell in tables[0].cells] == [
        "kind",
        "yes",
        "no",
        "unknown",
        "rate",
        "71%",
        "24%",
        "5%",
    ]

    diagnostics = vector_table_diagnostics(page)
    assert diagnostics["rect_count"] == 0
    assert diagnostics["x_clusters"] == [453.3, 495.9, 577.9, 660.0, 742.0]
    assert diagnostics["y_clusters"] == [525.6, 547.0, 568.3]
    doc.close()


def test_plain_material_box_is_not_table():
    """[자료 2]/[자료 3]처럼 외곽선 하나뿐인 박스는 표가 아니다."""
    doc = fitz.open()
    page = doc.new_page(width=850, height=700)
    page.draw_rect(fitz.Rect(453.0, 580.0, 742.0, 650.0), width=0.5)
    page.insert_text((465.0, 610.0), "material 2", fontsize=9)
    assert detect_vector_tables(page, extract_page_spans(page, 1)) == []
    doc.close()
