"""순서도 상자 → 접근 가능한 선형 묵자."""

from __future__ import annotations

from pathlib import Path

import pytest

from korean_exam_braille.app.exam.builder import RuleExamStructureBuilder
from korean_exam_braille.app.pdf.boxes import BOX_RULE_INK
from korean_exam_braille.app.pdf.candidates import detect_block_candidates
from korean_exam_braille.app.pdf.extractor import extract_pdf
from korean_exam_braille.app.pdf.flowchart import (
    FLOWCHART_TITLE,
    detect_flowcharts,
    exclude_flowchart_boxes,
    promote_flowcharts_into_lines,
    serialize_flowchart,
)
from korean_exam_braille.app.pdf.models import PdfLine, PdfSpan

MARCH_PDF = Path(r"c:\Users\Seongman Hwang\Downloads\2026고2-3월국어.pdf")


def _span(text: str, bbox: tuple[float, float, float, float], index: int = 0) -> PdfSpan:
    return PdfSpan(
        id=f"s{index}",
        text=text,
        bbox=bbox,
        font="",
        font_size=10.0,
        is_bold=False,
        page_number=1,
        extraction_index=index,
    )


def _q8_like_boxes_and_spans():
    parent = (40.0, 40.0, 340.0, 260.0)
    left = [
        (50.0, 50.0, 200.0, 85.0),
        (50.0, 105.0, 200.0, 140.0),
        (50.0, 160.0, 200.0, 195.0),
        (50.0, 215.0, 200.0, 250.0),
    ]
    right = [
        (220.0, 50.0, 330.0, 85.0),
        (220.0, 105.0, 330.0, 140.0),
        (220.0, 160.0, 330.0, 195.0),
    ]
    boxes = [parent, *left, *right]
    spans = [
        _span("조사와 결합하지 않는가?", (60, 58, 190, 72), 0),
        _span("구무", (240, 52, 280, 64), 1),
        _span("[구멍]", (235, 68, 290, 80), 2),
        _span("자음으로 시작하는 조사와", (55, 108, 195, 120), 3),
        _span("결합하는가?", (70, 124, 160, 136), 4),
        _span("구무도(구무+도)", (225, 108, 320, 120), 5),
        _span("[구멍도]", (240, 124, 310, 136), 6),
        _span("조사 ‘와’와 결합하는가?", (55, 168, 195, 182), 7),
        _span("구무와(구무+와)", (225, 165, 320, 177), 8),
        _span("[구멍과]", (240, 180, 310, 192), 9),
        _span("굼기(/+이)", (80, 220, 160, 232), 10),
        _span("[구멍이]", (90, 236, 155, 248), 11),
        _span("예", (205, 68, 218, 80), 12),
        _span("↓아니요", (90, 90, 150, 102), 13),
    ]
    return boxes, spans


def test_detect_and_serialize_stacked_yes_no_boxes():
    boxes, spans = _q8_like_boxes_and_spans()
    found = detect_flowcharts(boxes, spans)
    assert len(found) == 1
    accessible_text = serialize_flowchart(found[0])
    assert "────────────────" not in accessible_text
    assert accessible_text.index("조사와 결합하지 않는가?") < accessible_text.index(
        "구무 [구멍]"
    )
    assert "자음으로 시작하는 조사와 결합하는가?" in accessible_text
    assert "예 → 구무도(구무+도) [구멍도]" in accessible_text
    assert "조사 ‘와’와 결합하는가?" in accessible_text
    assert "아니요 → 굼기(/+이) [구멍이]" in accessible_text
    assert "아니요 → 2번으로" in accessible_text
    assert accessible_text.startswith(FLOWCHART_TITLE)


def test_flowchart_region_drops_box_rules_and_mixed_order_lines():
    boxes, spans = _q8_like_boxes_and_spans()
    found = detect_flowcharts(boxes, spans)
    mixed = [
        PdfLine("l0", "intro", (50, 10, 200, 24), [], 1, 0),
        PdfLine("l1", BOX_RULE_INK, (220, 49, 330, 50), [], 1, 1),
        PdfLine("l2", "→구무", (220, 52, 280, 64), [], 1, 2),
        PdfLine("l3", "조사와 결합하지 않는가?", (60, 58, 190, 72), [], 1, 3),
        PdfLine("l4", "예[구멍]", (220, 68, 290, 80), [], 1, 4),
        PdfLine("l5", "after", (50, 280, 200, 294), [], 1, 5),
    ]
    out = promote_flowcharts_into_lines(mixed, found, page_number=1)
    texts = [ln.text for ln in out]
    assert texts[0] == "intro"
    assert texts[-1] == "after"
    assert BOX_RULE_INK not in texts
    assert any(FLOWCHART_TITLE in t for t in texts)
    assert "→구무" not in texts
    leftover = exclude_flowchart_boxes(boxes, found)
    assert leftover == []


def test_flowchart_serial_is_not_question_candidate():
    tags = detect_block_candidates(
        "[그림: 순서도]\n1. 조사와 결합하지 않는가?\n   예 → 구무 [구멍]"
    )
    assert "FlowchartAsset" in tags
    assert "Question" not in tags


@pytest.mark.skipif(not MARCH_PDF.exists(), reason="2026고2-3월 PDF not found")
def test_march_page3_q8_flowchart_accessible_order():
    extracted = extract_pdf(MARCH_PDF, page_numbers=[3])
    page = extracted.pages[0]
    fc_lines = [
        ln
        for ln in page.lines
        if "-flowchart-" in (ln.id or "") or (ln.text or "").startswith(FLOWCHART_TITLE)
    ]
    assert fc_lines, "Q8 순서도가 Flowchart 행으로 승격되어야 한다"
    accessible_text = fc_lines[0].text
    assert "────────────────" not in accessible_text
    assert accessible_text.index("조사와 결합하지 않는가?") < accessible_text.index(
        "구무 [구멍]"
    )
    assert "자음으로 시작하는 조사와 결합하는가?" in accessible_text
    assert "예 → 구무도(구무+도) [구멍도]" in accessible_text
    assert "조사 ‘와’와 결합하는가?" in accessible_text
    assert "아니요 → 굼기(/+이) [구멍이]" in accessible_text

    region = fc_lines[0].bbox
    for ln in page.lines:
        cx = (ln.bbox[0] + ln.bbox[2]) / 2
        cy = (ln.bbox[1] + ln.bbox[3]) / 2
        if region[0] <= cx <= region[2] and region[1] <= cy <= region[3]:
            assert BOX_RULE_INK not in (ln.text or "")
            assert not (ln.text or "").startswith("→구무")

    exam = RuleExamStructureBuilder().build(extracted)
    flowcharts = []

    def walk(node):
        if node.node_type == "FlowchartAsset":
            flowcharts.append(node)
        for child in node.children:
            walk(child)

    walk(exam.root)
    assert flowcharts
    assert "예 → 구무도(구무+도) [구멍도]" in (flowcharts[0].source_range.raw_text or "")
