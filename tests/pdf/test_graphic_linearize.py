"""보기 그래픽 직렬화: 향찰 2행(밑줄 / 원문자) + 박스 표선."""

from __future__ import annotations

from pathlib import Path

import fitz

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as rev
from korean_exam_braille.app.pdf.boxes import iter_box_rects, line_mostly_in_box
from korean_exam_braille.app.pdf.extractor import extract_pdf
from korean_exam_braille.app.pdf.graphic_linearize import (
    BOX_RULE_INK,
    format_two_line_hyangchal,
    insert_box_rule_lines,
    merge_circled_label_lines,
    split_stacked_hyangchal_lines,
)
from korean_exam_braille.app.pdf.models import PdfLine


def test_two_line_hyangchal_format_and_braille():
    ink = format_two_line_hyangchal(
        "[향찰 표기] <u>오</u>은 <u>수</u><u>을</u> <u>음</u><u>다</u>",
        ["ⓐ", "ⓑ", "ⓒ", "ⓓ", "ⓔ"],
    )
    lines = ink.splitlines()
    assert lines[0].startswith("[향찰 표기]")
    assert "<u>오</u>" in lines[0]
    assert "ⓐ" not in lines[0]
    assert lines[1] == "ⓐ ⓑ ⓒ ⓓ ⓔ"
    brl = hangul_text_to_ascii(ink)
    assert "7a7" in brl and "7e7" in brl
    assert ",-" in brl
    back_lines = rev(brl).splitlines()
    assert "<u>" in back_lines[0]
    assert "ⓐ" in back_lines[1]


def test_split_mixed_underline_and_labels():
    mixed = PdfLine(
        "m0",
        "[향찰 표기] ⓐ<u>오</u>은 ⓑ<u>수</u>",
        (20, 40, 200, 55),
        [],
        1,
        0,
    )
    out = split_stacked_hyangchal_lines([mixed])
    assert len(out) == 2
    assert "ⓐ" not in out[0].text and "<u>오</u>" in out[0].text
    assert out[1].text == "ⓐ ⓑ"


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


def test_box_rule_line_braille_and_reverse():
    brl = hangul_text_to_ascii(BOX_RULE_INK)
    assert brl.startswith("!")
    assert "3" in brl
    assert rev(brl) == "─" * 16


def test_insert_box_rule_lines_around_content():
    lines = [
        PdfLine("l0", "outside", (10, 10, 50, 20), [], 1, 0),
        PdfLine("l1", "inner-a", (30, 40, 90, 50), [], 1, 1),
        PdfLine("l2", "inner-b", (30, 55, 90, 65), [], 1, 2),
        PdfLine("l3", "after", (10, 100, 50, 110), [], 1, 3),
    ]
    box = (25, 35, 95, 70)
    assert line_mostly_in_box(lines[1].bbox, box)
    out = insert_box_rule_lines(lines, [box], page_number=1)
    texts = [ln.text for ln in out]
    assert BOX_RULE_INK in texts
    i0 = texts.index("inner-a")
    i1 = texts.index("inner-b")
    assert texts[i0 - 1] == BOX_RULE_INK
    assert texts[i1 + 1] == BOX_RULE_INK


def test_small_blank_box_does_not_insert_structure_rules():
    """[가] 빈 응답란 같은 낮은 박스는 제시문 표선으로 직렬화하지 않는다."""
    lines = [
        PdfLine("l0", "학생3 : [가]", (140, 924, 390, 937), [], 1, 0),
        PdfLine("l1", "사회자: 네, 좋은 의견입니다.", (90, 942, 350, 955), [], 1, 1),
    ]
    small_box = (136.65, 923.84, 398.92, 938.11)
    out = insert_box_rule_lines(lines, [small_box], page_number=1)
    assert [ln.text for ln in out] == [
        "학생3 : [가]",
        "사회자: 네, 좋은 의견입니다.",
    ]


def test_pdf_two_line_hyangchal_extract(tmp_path: Path):
    """합성 PDF: 밑줄 본문 + 아래 원문자 → 두 줄 (합치지 않음)."""
    fontfile = Path(r"C:\Windows\Fonts\malgun.ttf")
    if not fontfile.exists():
        fontfile = Path(r"C:\Windows\Fonts\arial.ttf")

    path = tmp_path / "hyangchal_two_line.pdf"
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

    # 원문자가 밑줄과 같은 토큰으로 붙지 않음
    for ln in page_struct.lines:
        if "<u>" in (ln.text or "") and "ⓐ" in (ln.text or ""):
            raise AssertionError(f"mixed stacked line: {ln.text!r}")

    joined = "\n".join(ln.text for ln in page_struct.lines)
    assert BOX_RULE_INK in joined or any("<u>" in (ln.text or "") for ln in page_struct.lines)
    # 라벨 전용 행이 있거나, 최소한 원문자가 본문 밑줄과 분리
    label_lines = [
        ln for ln in page_struct.lines if ln.text and all(
            c in "ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ \t" for c in ln.text
        )
    ]
    if any("ⓐ" in (s.text or "") for s in page_struct.spans):
        assert label_lines or "ⓐ" in joined
