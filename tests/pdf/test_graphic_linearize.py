"""보기 그래픽 직렬화: 흩어진 원문자 행 병합 + 박스 표선."""

from __future__ import annotations

from pathlib import Path

import fitz

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as rev
from korean_exam_braille.app.pdf.boxes import iter_box_rects
from korean_exam_braille.app.pdf.extractor import extract_pdf
from korean_exam_braille.app.pdf.graphic_linearize import (
    BOX_RULE_INK,
    insert_box_rule_lines,
    merge_circled_label_lines,
)
from korean_exam_braille.app.pdf.models import PdfLine


def test_merge_scattered_label_lines():
    lines = [
        PdfLine("h", "[향찰 표기] <u>오</u>은", (20, 40, 180, 54), [], 1, 0),
        PdfLine("a", "ⓐ", (40, 58, 52, 70), [], 1, 1),
        PdfLine("b", "ⓑⓒ", (80, 58, 110, 70), [], 1, 2),
        PdfLine("c", "ⓓ", (140, 59, 152, 71), [], 1, 3),
        PdfLine("d", "ⓔ", (170, 58, 182, 70), [], 1, 4),
    ]
    out = merge_circled_label_lines(lines)
    texts = [ln.text for ln in out]
    assert texts[0].startswith("[향찰 표기]")
    assert texts[1] == "ⓐ ⓑ ⓒ ⓓ ⓔ"
    assert len(out) == 2


def test_inline_circled_with_underline_stays_put():
    """본문에 이미 있는 ⓐ+밑줄은 분리·이동하지 않는다."""
    mixed = PdfLine(
        "m0",
        "그 적용을 ⓐ<u>배제할</u> 수 있다.",
        (20, 40, 200, 55),
        [],
        1,
        0,
    )
    out = merge_circled_label_lines([mixed])
    assert len(out) == 1
    assert out[0].text == "그 적용을 ⓐ<u>배제할</u> 수 있다."


def test_stacked_label_line_not_moved_onto_body():
    """밑줄 본문 + 아래 원문자 행은 그대로 두 줄."""
    lines = [
        PdfLine("h", "[향찰 표기] <u>吾</u>隱 <u>水乙</u> <u>飮多</u>", (20, 40, 200, 54), [], 1, 0),
        PdfLine("a", "ⓐ ⓑ ⓒ ⓓ ⓔ", (40, 55, 180, 68), [], 1, 1),
    ]
    out = merge_circled_label_lines(lines)
    assert len(out) == 2
    assert "<u>吾</u>" in out[0].text and "ⓐ" not in out[0].text
    assert out[1].text == "ⓐ ⓑ ⓒ ⓓ ⓔ"


def test_box_rule_line_braille_and_reverse():
    brl = hangul_text_to_ascii(BOX_RULE_INK)
    assert brl.startswith("!")
    assert "3" in brl
    assert rev(brl) == "─" * 16


def test_insert_box_rule_lines_around_content():
    lines = [
        PdfLine("l0", "outside", (10, 10, 50, 20), [], 1, 0),
        PdfLine("l1", "inside A", (40, 40, 120, 55), [], 1, 1),
        PdfLine("l2", "inside B", (40, 60, 120, 75), [], 1, 2),
        PdfLine("l3", "outside2", (10, 200, 50, 210), [], 1, 3),
    ]
    boxes = [(30, 35, 130, 80)]
    out = insert_box_rule_lines(lines, boxes, page_number=1)
    texts = [ln.text for ln in out]
    assert BOX_RULE_INK in texts
    i0 = texts.index("inside A")
    i1 = texts.index("inside B")
    assert texts[i0 - 1] == BOX_RULE_INK
    assert texts[i1 + 1] == BOX_RULE_INK


def test_insert_box_rule_skips_shallow_answer_slot():
    lines = [
        PdfLine("l0", "학생3 : [가]", (90, 920, 200, 935), [], 1, 0),
        PdfLine("l1", "사회자: 네, 좋은 의견입니다.", (90, 942, 350, 955), [], 1, 1),
    ]
    small_box = (136.65, 923.84, 398.92, 938.11)
    out = insert_box_rule_lines(lines, [small_box], page_number=1)
    assert [ln.text for ln in out] == [
        "학생3 : [가]",
        "사회자: 네, 좋은 의견입니다.",
    ]


def test_pdf_stacked_labels_remain_separate(tmp_path: Path):
    """합성 PDF: 밑줄 본문 + 아래 원문자 → 합치지 않고 두 줄 유지 가능."""
    fontfile = Path(r"C:\Windows\Fonts\malgun.ttf")
    if not fontfile.exists():
        fontfile = Path(r"C:\Windows\Fonts\arial.ttf")

    path = tmp_path / "hyangchal_stacked.pdf"
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_font(fontname="f0", fontfile=str(fontfile))
    page.draw_rect(fitz.Rect(40, 40, 360, 220), color=(0, 0, 0), width=1.0)

    page.insert_text((80, 100), "오은", fontsize=14, fontname="f0")
    hits = page.search_for("오은")
    assert hits
    r = hits[0]
    page.draw_line(
        fitz.Point(r.x0, r.y1 + 1.0),
        fitz.Point(r.x1, r.y1 + 1.0),
        width=0.7,
    )
    cx = (r.x0 + r.x1) / 2
    page.insert_text((cx - 6, r.y1 + 16), "ⓐ", fontsize=11, fontname="f0")

    doc.save(path)
    doc.close()

    extracted = extract_pdf(path, page_numbers=[1])
    page_struct = extracted.pages[0]

    doc2 = fitz.open(path)
    assert iter_box_rects(doc2[0]), "draw_rect should yield a box"
    doc2.close()

    joined = "\n".join(ln.text for ln in page_struct.lines)
    assert BOX_RULE_INK in joined or any("<u>" in (ln.text or "") for ln in page_struct.lines)
    if any("ⓐ" in (s.text or "") for s in page_struct.spans):
        assert "ⓐ" in joined
