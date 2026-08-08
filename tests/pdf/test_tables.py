"""벡터 셀 기반 표 격자·텍스트 복원."""

from __future__ import annotations

from pathlib import Path

import fitz

from korean_exam_braille.app.pdf.extractor import extract_page_spans, extract_pdf
from korean_exam_braille.app.pdf.models import (
    PdfPageStructure,
    PdfTable,
    PdfTableCell,
)
from korean_exam_braille.app.pdf.tables import (
    detect_vector_tables,
    format_table_row_texts,
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
    table_text = "\n".join(
        block.text
        for block in page.blocks
        if "TableAsset" in block.candidate_tags
    )
    assert "kind  yes  no  unknown" in table_text
    assert "rate  71%  24%  5%" in table_text
    assert "<u>" not in table_text

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


def test_page_long_verticals_do_not_inflate_table_width():
    """페이지 긴 세로선이 있어도 표 가로선 폭 안의 세로선만으로 2×4를 복원한다."""
    doc = fitz.open()
    page = doc.new_page(width=850, height=1100)
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
    # 실제 시험지처럼 표 높이도 덮는 페이지 프레임 세로선.
    for x in (87.7, 420.5, 751.9):
        page.draw_line(fitz.Point(x, 193.0), fitz.Point(x, 960.0), width=0.5)
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
    assert abs(tables[0].bbox[0] - 453.3) < 1.0
    assert abs(tables[0].bbox[2] - 742.0) < 1.0
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
    doc.close()


def test_taller_same_width_verticals_are_ignored():
    """같은 폭이라도 높이가 다른 세로선은 표 격자에 섞지 않는다."""
    doc = fitz.open()
    page = doc.new_page(width=850, height=900)
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
    # 표와 같은 폭의 아래 자료 박스(가로 2줄 + 훨씬 긴 세로선).
    page.draw_line(fitz.Point(xs[0], 596.0), fitz.Point(xs[-1], 596.0), width=0.5)
    page.draw_line(fitz.Point(xs[0], 804.0), fitz.Point(xs[-1], 804.0), width=0.5)
    for x in (xs[0], xs[-1]):
        page.draw_line(fitz.Point(x, 596.0), fitz.Point(x, 804.0), width=0.5)
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
    assert abs(tables[0].bbox[3] - 568.3) < 1.0
    doc.close()


def test_detect_two_level_header_with_merged_cells():
    """부분 가로·세로선으로 2단 헤더(rowspan/colspan)를 복원한다."""
    doc = fitz.open()
    page = doc.new_page(width=500, height=700)
    # leaf: 구분 | 접사 | 어근 | 접사 | 어미
    xs = [120.0, 155.0, 208.0, 281.0, 340.0, 410.0]
    # 헤더 2단 + 데이터 1행
    ys = [430.0, 450.0, 470.0, 495.0]
    font = "C:/Windows/Fonts/malgun.ttf"
    page.insert_font(fontname="malgun", fontfile=font)

    def put(x: float, y: float, text: str, size: float = 8.0) -> None:
        page.insert_text((x, y), text, fontsize=size, fontname="malgun")

    # 외곽·전체 폭 가로선 (헤더 중간 가로선은 제외)
    for y in (ys[0], ys[2], ys[3]):
        page.draw_line(fitz.Point(xs[0], y), fitz.Point(xs[-1], y), width=0.5)
    # 어간 영역만 가로지르는 헤더 2단 가로선
    page.draw_line(fitz.Point(xs[1], ys[1]), fitz.Point(xs[4], ys[1]), width=0.5)

    # 전체 높이 세로선: 외곽 + 구분|어간 + 어간|어미
    for x in (xs[0], xs[1], xs[4], xs[5]):
        page.draw_line(fitz.Point(x, ys[0]), fitz.Point(x, ys[-1]), width=0.5)
    # 짧은 중간 세로선: 헤더 2단 아래부터
    for x in (xs[2], xs[3]):
        page.draw_line(fitz.Point(x, ys[1]), fitz.Point(x, ys[-1]), width=0.5)

    # 텍스트 배치 (병합 영역 중심)
    put(xs[0] + 8, ys[0] + 28, "구분")
    put(xs[1] + 55, ys[0] + 12, "어간")
    put(xs[4] + 12, ys[0] + 28, "어미")
    put(xs[1] + 8, ys[1] + 14, "접사")
    put(xs[2] + 12, ys[1] + 14, "어근")
    put(xs[3] + 12, ys[1] + 14, "접사")
    put(xs[0] + 8, ys[2] + 16, "㉠")
    put(xs[1] + 12, ys[2] + 16, "ㆍ")
    put(xs[2] + 4, ys[2] + 16, "높-, 푸르-", 7)
    put(xs[3] + 12, ys[2] + 16, "ㆍ")
    put(xs[4] + 12, ys[2] + 16, "-며")

    tables = detect_vector_tables(page, extract_page_spans(page, 1))
    assert len(tables) == 1
    table = tables[0]
    assert (table.row_count, table.column_count) == (3, 5)

    by_pos = {(c.row, c.column): c for c in table.cells}
    assert by_pos[(0, 0)].text == "구분"
    assert by_pos[(0, 0)].rowspan == 2
    assert by_pos[(0, 1)].text == "어간"
    assert by_pos[(0, 1)].colspan == 3
    assert by_pos[(0, 4)].text == "어미"
    assert by_pos[(0, 4)].rowspan == 2
    assert by_pos[(1, 1)].text == "접사"
    assert by_pos[(1, 2)].text == "어근"
    assert by_pos[(1, 3)].text == "접사"

    rows = format_table_row_texts(table)
    assert rows[0] == "구분  어간(접사  어근  접사)  어미"
    assert rows[1] == "㉠  ㆍ  높-, 푸르-  ㆍ  -며"
    doc.close()


def test_table_cell_span_roundtrip_in_page_dict():
    table = PdfTable(
        bbox=(0.0, 0.0, 10.0, 10.0),
        row_count=2,
        column_count=3,
        cells=[
            PdfTableCell(
                row=0,
                column=0,
                bbox=(0.0, 0.0, 3.0, 10.0),
                text="a",
                rowspan=2,
                colspan=1,
            ),
            PdfTableCell(
                row=0,
                column=1,
                bbox=(3.0, 0.0, 10.0, 5.0),
                text="b",
                rowspan=1,
                colspan=2,
            ),
        ],
    )
    restored = PdfTable.from_dict(table.to_dict())
    assert restored.cells[0].rowspan == 2
    assert restored.cells[1].colspan == 2
