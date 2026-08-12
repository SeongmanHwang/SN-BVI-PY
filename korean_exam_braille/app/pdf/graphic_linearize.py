"""보기 그래픽 → 선형 묵자: 박스 표선 + 흩어진 원문자 행 병합.

본문에 이미 있는 원문자(``그 적용을 ⓐ배제할 …``)는 그대로 둔다.
밑줄 아래 별행 원문자도 위치를 옮기지 않는다 (본문 행 / 라벨 행 유지).
원문자는 ``7a7``…(ⓐ…) 로 점역한다. 참고 BRF ``70a7``/‘a’ 는 쓰지 않는다.

박스 경계 → ──── 행 (점역 시 표선 !333…4)
"""

from __future__ import annotations

from korean_exam_braille.app.pdf.boxes import (
    BOX_RULE_INK,
    iter_box_rects,
    line_mostly_in_box,
)
from korean_exam_braille.app.pdf.figures import promote_figures_into_lines
from korean_exam_braille.app.pdf.flowchart import (
    detect_flowcharts,
    exclude_flowchart_boxes,
    promote_flowcharts_into_lines,
)
from korean_exam_braille.app.pdf.models import BBox, PdfFigure, PdfLine, PdfSpan, PdfTable
from korean_exam_braille.app.pdf.tables import (
    box_matches_table,
    promote_tables_into_lines,
)

_CIRCLED_LATIN = set("ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ")

# 라벨 전용 행으로 볼 y 간격 (연속 행 병합)
_LABEL_LINE_Y_GAP = 18.0


def _union_bbox(boxes: list[BBox]) -> BBox:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _circled_chars(text: str) -> list[str]:
    return [ch for ch in text if ch in _CIRCLED_LATIN]


def _is_label_only_line(text: str) -> bool:
    """원문자·공백만 있는 행."""
    body = "".join(ch for ch in (text or "") if not ch.isspace())
    return bool(body) and all(ch in _CIRCLED_LATIN for ch in body)


def merge_circled_label_lines(lines: list[PdfLine]) -> list[PdfLine]:
    """가로로 흩어진 원문자 전용 행을 한 줄로 합친다 (ⓐ ⓑ ⓒ …)."""
    if not lines:
        return lines
    out: list[PdfLine] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not _is_label_only_line(ln.text):
            out.append(ln)
            i += 1
            continue
        run = [ln]
        j = i + 1
        while j < len(lines) and _is_label_only_line(lines[j].text):
            prev = run[-1]
            if lines[j].bbox[1] - prev.bbox[3] > _LABEL_LINE_Y_GAP:
                break
            run.append(lines[j])
            j += 1
        run_sorted = sorted(run, key=lambda L: (L.bbox[0], L.bbox[1]))
        labels: list[str] = []
        for piece in run_sorted:
            labels.extend(_circled_chars(piece.text))
        seen: set[str] = set()
        ordered: list[str] = []
        for ch in labels:
            if ch not in seen:
                seen.add(ch)
                ordered.append(ch)
        merged = PdfLine(
            id=run[0].id,
            text=" ".join(ordered),
            bbox=_union_bbox([p.bbox for p in run]),
            span_ids=[sid for p in run for sid in p.span_ids],
            page_number=run[0].page_number,
            reading_order=run[0].reading_order,
        )
        out.append(merged)
        i = j

    for k, ln in enumerate(out):
        ln.reading_order = k
    return out


def insert_box_rule_lines(
    lines: list[PdfLine],
    boxes: list[BBox],
    *,
    page_number: int,
    rule_text: str = BOX_RULE_INK,
) -> list[PdfLine]:
    """구조 박스에 속한 행 앞·뒤에 표선 묵자 행을 끼운다.

    높이가 낮은 빈 응답란(`[가]` 등)은 구조 컨테이너가 아니므로 제외한다.
    """
    if not lines or not boxes:
        return lines

    structural_boxes = [box for box in boxes if box[3] - box[1] >= 28.0]
    if not structural_boxes:
        return lines

    ordered_boxes = sorted(
        structural_boxes,
        key=lambda b: ((b[2] - b[0]) * (b[3] - b[1]), b[1], b[0]),
    )

    before = [0] * len(lines)
    after = [0] * len(lines)
    for box in ordered_boxes:
        idxs = [i for i, ln in enumerate(lines) if line_mostly_in_box(ln.bbox, box)]
        if not idxs:
            continue
        before[idxs[0]] += 1
        after[idxs[-1]] += 1

    out: list[PdfLine] = []
    seq = 0

    def _rule_line(y: float, x0: float, x1: float) -> PdfLine:
        nonlocal seq
        seq += 1
        return PdfLine(
            id=f"p{page_number}-rule-{seq}",
            text=rule_text,
            bbox=(x0, y, x1, y + 1.0),
            span_ids=[],
            page_number=page_number,
            reading_order=0,
        )

    for i, ln in enumerate(lines):
        for _ in range(before[i]):
            out.append(_rule_line(ln.bbox[1] - 1.0, ln.bbox[0], ln.bbox[2]))
        out.append(ln)
        for _ in range(after[i]):
            out.append(_rule_line(ln.bbox[3] + 1.0, ln.bbox[0], ln.bbox[2]))

    compacted: list[PdfLine] = []
    for ln in out:
        if compacted and compacted[-1].text == rule_text and ln.text == rule_text:
            continue
        compacted.append(ln)

    for i, ln in enumerate(compacted):
        ln.reading_order = i
    return compacted


def linearize_page_graphics(
    page: object,
    lines: list[PdfLine],
    *,
    tables: list[PdfTable] | None = None,
    figures: list[PdfFigure] | None = None,
    spans: list[PdfSpan] | None = None,
) -> list[PdfLine]:
    """흩어진 원문자 행 병합 + 표·그림 승격 + 순서도 선형화 + 박스 표선."""
    table_list = tables or []
    figure_list = figures or []
    if not lines:
        page_number = 1
        if figure_list:
            return promote_figures_into_lines([], figure_list, page_number=page_number)
        return lines
    page_number = lines[0].page_number
    lines = merge_circled_label_lines(lines)
    if table_list:
        lines = promote_tables_into_lines(lines, table_list, page_number=page_number)
    if figure_list:
        lines = promote_figures_into_lines(lines, figure_list, page_number=page_number)
    boxes = [
        box
        for box in iter_box_rects(page)
        if not box_matches_table(box, table_list)
    ]
    flowcharts = detect_flowcharts(boxes, spans or [])
    if flowcharts:
        lines = promote_flowcharts_into_lines(
            lines, flowcharts, page_number=page_number
        )
        boxes = exclude_flowchart_boxes(boxes, flowcharts)
    return insert_box_rule_lines(lines, boxes, page_number=page_number)
