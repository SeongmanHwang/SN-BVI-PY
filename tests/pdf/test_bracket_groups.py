"""여백 [A]/[B] 꺾인 괄호 감지 (왼쪽·오른쪽)."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from korean_exam_braille.app.pdf.bracket_groups import (
    detect_and_assign_bracket_groups,
    detect_bracket_geometries,
)
from korean_exam_braille.app.pdf.display_text import format_page_text_for_display
from korean_exam_braille.app.pdf.extractor import extract_pdf
from korean_exam_braille.app.pdf.models import PdfLine

EXAM_PDF = Path(
    r"c:\Users\Seongman Hwang\Downloads\2026년-6월-고2-모의고사-국어-문제.pdf"
)


def _draw_bracket(
    page: fitz.Page,
    *,
    stem_x: float,
    y0: float,
    gap_y0: float,
    gap_y1: float,
    y1: float,
    tick: float = 10.0,
    body_side: str = "left",
) -> None:
    """위·아래 세로선 + 본문 쪽 턱 (가운데 끊김).

    body_side=\"left\": 턱이 왼쪽(오른쪽 여백 괄호).
    body_side=\"right\": 턱이 오른쪽(왼쪽 여백 괄호).
    """
    if body_side == "right":
        tip = stem_x + tick
    else:
        tip = stem_x - tick
    page.draw_line(fitz.Point(tip, y0), fitz.Point(stem_x, y0), width=0.8)
    page.draw_line(fitz.Point(stem_x, y0), fitz.Point(stem_x, gap_y0), width=0.8)
    page.draw_line(fitz.Point(stem_x, gap_y1), fitz.Point(stem_x, y1), width=0.8)
    page.draw_line(fitz.Point(tip, y1), fitz.Point(stem_x, y1), width=0.8)


def test_synthetic_bracket_assigns_lines(tmp_path: Path):
    fontfile = Path(r"C:\Windows\Fonts\malgun.ttf")
    if not fontfile.exists():
        fontfile = Path(r"C:\Windows\Fonts\arial.ttf")

    path = tmp_path / "bracket_a.pdf"
    doc = fitz.open()
    page = doc.new_page(width=500, height=500)
    page.insert_font(fontname="f0", fontfile=str(fontfile))

    stem_x = 400.0
    y0, gap_y0, gap_y1, y1 = 100.0, 160.0, 175.0, 240.0
    _draw_bracket(
        page, stem_x=stem_x, y0=y0, gap_y0=gap_y0, gap_y1=gap_y1, y1=y1
    )
    page.insert_text((stem_x - 8, (gap_y0 + gap_y1) / 2 + 4), "[A]", fontsize=11, fontname="f0")
    page.insert_text((60, 120), "학생1 : 양이 많긴 하지만", fontsize=12, fontname="f0")
    page.insert_text((60, 150), "학생2 : 조사해 보니", fontsize=12, fontname="f0")
    page.insert_text((60, 200), "학생3 : 환경에 부담까지", fontsize=12, fontname="f0")
    page.insert_text((60, 300), "바깥 행입니다", fontsize=12, fontname="f0")

    doc.save(path)
    doc.close()

    extracted = extract_pdf(path, page_numbers=[1])
    page_struct = extracted.pages[0]
    labels = {g.label for g in page_struct.bracket_groups}
    assert "[A]" in labels
    group_a = next(g for g in page_struct.bracket_groups if g.label == "[A]")
    assert group_a.body_side == "left"
    assert group_a.line_ids
    owned = [ln for ln in page_struct.lines if ln.bracket_label == "[A]"]
    texts = " ".join(ln.text for ln in owned)
    assert "학생1" in texts
    assert "학생3" in texts
    assert "바깥 행" not in texts
    assert all("[A]" not in span.text for span in page_struct.spans)
    assert any("bracket:[A]" in (b.candidate_tags or []) for b in page_struct.blocks)
    assert sum(
        "bracket-start:[A]" in (b.candidate_tags or [])
        for b in page_struct.blocks
    ) == 1
    assert sum(
        "bracket-end:[A]" in (b.candidate_tags or [])
        for b in page_struct.blocks
    ) == 1
    displayed = format_page_text_for_display(page_struct)
    assert "[A] 학생1" in displayed
    assert "[A] 학생3" in displayed


def test_synthetic_left_margin_bracket_assigns_lines(tmp_path: Path):
    """왼쪽 여백 괄호(오른쪽으로 뻗은 턱)도 본문 행에 소속시킨다."""
    fontfile = Path(r"C:\Windows\Fonts\malgun.ttf")
    if not fontfile.exists():
        fontfile = Path(r"C:\Windows\Fonts\arial.ttf")

    path = tmp_path / "bracket_left.pdf"
    doc = fitz.open()
    page = doc.new_page(width=500, height=500)
    page.insert_font(fontname="f0", fontfile=str(fontfile))

    stem_x = 80.0
    y0, gap_y0, gap_y1, y1 = 100.0, 160.0, 175.0, 240.0
    _draw_bracket(
        page,
        stem_x=stem_x,
        y0=y0,
        gap_y0=gap_y0,
        gap_y1=gap_y1,
        y1=y1,
        body_side="right",
    )
    page.insert_text((stem_x + 2, (gap_y0 + gap_y1) / 2 + 4), "[A]", fontsize=11, fontname="f0")
    page.insert_text((120, 120), "학생1 : 양이 많긴 하지만", fontsize=12, fontname="f0")
    page.insert_text((120, 150), "학생2 : 조사해 보니", fontsize=12, fontname="f0")
    page.insert_text((120, 200), "학생3 : 환경에 부담까지", fontsize=12, fontname="f0")
    page.insert_text((120, 300), "바깥 행입니다", fontsize=12, fontname="f0")

    doc.save(path)
    doc.close()

    extracted = extract_pdf(path, page_numbers=[1])
    page_struct = extracted.pages[0]
    assert any(g.label == "[A]" for g in page_struct.bracket_groups)
    group_a = next(g for g in page_struct.bracket_groups if g.label == "[A]")
    assert group_a.body_side == "right"
    assert group_a.tick_x0 > group_a.stem_x
    owned = [ln for ln in page_struct.lines if ln.bracket_label == "[A]"]
    texts = " ".join(ln.text for ln in owned)
    assert "학생1" in texts
    assert "학생3" in texts
    assert "바깥 행" not in texts
    displayed = format_page_text_for_display(page_struct)
    assert "[A] 학생1" in displayed


def test_long_box_edge_not_bracket(tmp_path: Path):
    """긴 가로변(박스)은 턱으로 보지 않는다."""
    path = tmp_path / "long_edge.pdf"
    doc = fitz.open()
    page = doc.new_page(width=500, height=400)
    # 긴 가로선 + 세로선 공백 — 턱 길이 초과
    page.draw_line(fitz.Point(50, 80), fitz.Point(400, 80), width=0.8)
    page.draw_line(fitz.Point(400, 80), fitz.Point(400, 140), width=0.8)
    page.draw_line(fitz.Point(400, 160), fitz.Point(400, 220), width=0.8)
    page.draw_line(fitz.Point(50, 220), fitz.Point(400, 220), width=0.8)
    page.insert_text((390, 155), "[A]", fontsize=11)
    doc.save(path)
    doc.close()

    doc2 = fitz.open(path)
    geos = detect_bracket_geometries(doc2[0])
    doc2.close()
    assert not geos


@pytest.mark.skipif(not EXAM_PDF.exists(), reason="exam PDF not found")
def test_exam_page2_bracket_a_and_b():
    """2026-6 고2 국어 2면: 왼쪽 열 [A]/[B] 꺾인 괄호."""
    extracted = extract_pdf(EXAM_PDF, page_numbers=[2])
    page = extracted.pages[0]
    by_label = {g.label: g for g in page.bracket_groups}
    assert "[A]" in by_label
    assert "[B]" in by_label

    a = by_label["[A]"]
    assert abs(a.stem_x - 398.444) < 1.0
    assert a.y0 < 260 and a.y1 > 385
    assert 10 <= (a.gap_y1 - a.gap_y0) <= 20

    owned_a = [ln for ln in page.lines if ln.bracket_label == "[A]"]
    text_a = "\n".join(ln.text for ln in owned_a)
    assert "양이 많긴 하지만" in text_a
    assert "환경에 부담까지" in text_a
    assert "매립하더라도" in text_a  # gap 행(줄 끝에 [A] 붙은 본문)
    assert "지자체에서도 [A]" not in text_a
    # 문항에서 [A]를 참조하는 일반 텍스트는 물리적 표지 제거 대상이 아니다.
    all_text = "\n".join(ln.text for ln in page.lines)
    assert "[A]의" in all_text and "학생2" in all_text

    b = by_label["[B]"]
    owned_b = [ln for ln in page.lines if ln.bracket_label == "[B]"]
    text_b = "\n".join(ln.text for ln in owned_b)
    assert "학생4" in text_b or "보도 자료를 보니" in text_b
    assert "새활용" in text_b or "업사이클링" in text_b

    # 박스 긴 변으로 생긴 가짜 괄호가 없어야 함
    assert len(page.bracket_groups) == 2


@pytest.mark.skipif(not EXAM_PDF.exists(), reason="exam PDF not found")
def test_exam_page10_left_margin_bracket_a():
    """10면 하단: 11.75pt 줄기+오른쪽 턱의 왼쪽 여백 [A]."""
    extracted = extract_pdf(EXAM_PDF, page_numbers=[10])
    page = extracted.pages[0]
    group_a = next(g for g in page.bracket_groups if g.label == "[A]")

    assert group_a.body_side == "right"
    assert abs(group_a.stem_x - 101.889) < 1.0
    assert group_a.tick_x0 > group_a.stem_x

    owned = [ln for ln in page.lines if ln.bracket_label == "[A]"]
    text = "\n".join(ln.text for ln in owned)
    assert "교내 캠페인" in text
    assert "멸종 위기 홍보" in text
    assert "[A]" not in text

    # 30번 문항의 본문 참조 [A]는 물리적 구간 표지가 아니므로 유지한다.
    all_text = "\n".join(ln.text for ln in page.lines)
    assert "바탕으로 [A]를 고쳐 쓴" in all_text


def test_assign_prefers_nearer_stem():
    lines = [
        PdfLine("l0", "본문", (100, 100, 300, 115), [], 1, 0),
    ]
    from korean_exam_braille.app.pdf.bracket_groups import BracketGroup, assign_lines_to_brackets

    far = BracketGroup(
        label="[A]",
        stem_x=500,
        y0=90,
        y1=130,
        gap_y0=105,
        gap_y1=115,
        tick_x0=490,
        label_bbox=(492, 106, 510, 118),
        body_side="left",
    )
    near = BracketGroup(
        label="[B]",
        stem_x=350,
        y0=90,
        y1=130,
        gap_y0=105,
        gap_y1=115,
        tick_x0=340,
        label_bbox=(342, 106, 360, 118),
        body_side="left",
    )
    assign_lines_to_brackets(lines, [far, near])
    assert lines[0].bracket_label == "[B]"


def test_build_blocks_splits_before_bracket_preamble():
    """괄호 밖 서술과 괄호 안 인용을 한 블록으로 합치지 않는다."""
    from korean_exam_braille.app.pdf.block_builder import build_blocks
    from korean_exam_braille.app.pdf.bracket_groups import annotate_blocks_with_brackets
    from korean_exam_braille.app.pdf.bracket_groups import BracketGroup

    lines = [
        PdfLine("l0", "손병진을 꾸짖어 말하기를,", (60, 100, 280, 114), [], 1, 0),
        PdfLine("l1", "“네가 국가의 녹봉을 받는", (60, 116, 280, 130), [], 1, 1),
        PdfLine("l2", "신하로서 간사한 계집의 말을 듣", (60, 132, 280, 146), [], 1, 2),
        PdfLine("l3", "바깥 이어지는 문장.", (60, 160, 280, 174), [], 1, 3),
    ]
    lines[0].bracket_label = None
    lines[1].bracket_label = "[B]"
    lines[2].bracket_label = "[B]"
    lines[3].bracket_label = None

    blocks = build_blocks(lines, page_number=1)
    assert len(blocks) >= 3
    # 첫 블록은 서술만
    assert blocks[0].line_ids == ["l0"]
    assert "손병진" in blocks[0].text
    assert "네가" not in blocks[0].text
    # 인용 블록
    quote = next(b for b in blocks if "l1" in b.line_ids)
    assert "l0" not in quote.line_ids
    assert "네가" in quote.text

    group = BracketGroup(
        label="[B]",
        stem_x=400,
        y0=110,
        y1=150,
        gap_y0=120,
        gap_y1=130,
        tick_x0=390,
        label_bbox=(392, 122, 410, 134),
        body_side="left",
        line_ids=["l1", "l2"],
    )
    annotate_blocks_with_brackets(blocks, lines, [group])
    start_blocks = [
        b for b in blocks if "bracket-start:[B]" in (b.candidate_tags or [])
    ]
    assert len(start_blocks) == 1
    assert "손병진" not in start_blocks[0].text
    assert "네가" in start_blocks[0].text
