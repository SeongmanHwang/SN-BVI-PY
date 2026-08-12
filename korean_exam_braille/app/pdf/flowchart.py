"""순서도(조건·결과 상자) → 접근 가능한 선형 묵자.

상자 테두리·화살표는 구조로만 쓰고 출력하지 않는다.
일반 본문 reading order(y, x) 대신 상자 쌍을 위에서 아래로 순회한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from korean_exam_braille.app.pdf.boxes import line_mostly_in_box
from korean_exam_braille.app.pdf.models import BBox, PdfLine

FLOWCHART_TITLE = "[그림: 순서도]"
FLOWCHART_LINE_ID = "flowchart"

_NODE_MIN_H = 24.0
_NODE_MAX_H = 58.0
_NODE_MIN_W = 60.0
_NODE_MAX_W = 250.0
_MIN_NODE_BOXES = 3
_ROW_Y_TOL = 8.0
_PAIR_X_GAP = 10.0
_CONTAIN_PAD = 6.0
_SAME_BOX_TOL = 4.0
_DECISION_RE = re.compile(r"는가\s*\?|인가\s*\?|을까\s*\?|할까요\s*\?|예|아니요")
_WS_RE = re.compile(r"\s+")
_LEADING_ARROW_RE = re.compile(r"^[→↓]\s*")


@dataclass
class FlowchartNode:
    kind: str  # "condition" | "result"
    text: str
    bbox: BBox
    yes_text: str | None = None
    yes_bbox: BBox | None = None


@dataclass
class Flowchart:
    bbox: BBox
    nodes: list[FlowchartNode] = field(default_factory=list)
    title: str = FLOWCHART_TITLE

    def node_bboxes(self) -> list[BBox]:
        out: list[BBox] = [self.bbox]
        for node in self.nodes:
            out.append(node.bbox)
            if node.yes_bbox is not None:
                out.append(node.yes_bbox)
        return out


def _union_bbox(boxes: list[BBox]) -> BBox:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _same_box(a: BBox, b: BBox, *, tol: float = _SAME_BOX_TOL) -> bool:
    return (
        abs(a[0] - b[0]) <= tol
        and abs(a[1] - b[1]) <= tol
        and abs(a[2] - b[2]) <= tol
        and abs(a[3] - b[3]) <= tol
    )


def _contains(parent: BBox, child: BBox, *, pad: float = _CONTAIN_PAD) -> bool:
    return (
        parent[0] <= child[0] + pad
        and parent[1] <= child[1] + pad
        and parent[2] >= child[2] - pad
        and parent[3] >= child[3] - pad
        and (parent[2] - parent[0]) * (parent[3] - parent[1])
        > (child[2] - child[0]) * (child[3] - child[1]) * 1.15
    )


def _is_node_box(box: BBox) -> bool:
    width = box[2] - box[0]
    height = box[3] - box[1]
    return _NODE_MIN_W <= width <= _NODE_MAX_W and _NODE_MIN_H <= height <= _NODE_MAX_H


def _text_in_box(spans: list[object], box: BBox, *, min_overlap: float = 0.4) -> str:
    parts: list[str] = []
    ordered = sorted(
        spans,
        key=lambda s: (float(s.bbox[1]), float(s.bbox[0])),  # type: ignore[attr-defined]
    )
    for span in ordered:
        raw = (getattr(span, "text", None) or "").strip()
        if not raw:
            continue
        bbox = getattr(span, "bbox", None)
        if bbox is None:
            continue
        if line_mostly_in_box(bbox, box, min_overlap=min_overlap):
            parts.append(raw)
    text = _WS_RE.sub(" ", " ".join(parts)).strip()
    return _LEADING_ARROW_RE.sub("", text)


def _region_text(spans: list[object], box: BBox) -> str:
    parts: list[str] = []
    for span in spans:
        raw = (getattr(span, "text", None) or "").strip()
        if not raw:
            continue
        bbox = getattr(span, "bbox", None)
        if bbox is None:
            continue
        if line_mostly_in_box(bbox, box, min_overlap=0.2):
            parts.append(raw)
        else:
            cx = (bbox[0] + bbox[2]) / 2
            cy = (bbox[1] + bbox[3]) / 2
            if box[0] <= cx <= box[2] and box[1] <= cy <= box[3]:
                parts.append(raw)
    return " ".join(parts)


def _looks_like_decision(text: str) -> bool:
    return bool(_DECISION_RE.search(text or ""))


def _group_rows(boxes: list[BBox]) -> list[list[BBox]]:
    rows: list[list[BBox]] = []
    for box in sorted(boxes, key=lambda b: (b[1], b[0])):
        if rows and abs(box[1] - rows[-1][0][1]) <= _ROW_Y_TOL:
            rows[-1].append(box)
        else:
            rows.append([box])
    for row in rows:
        row.sort(key=lambda b: b[0])
    return rows


def _build_flowchart(
    parent: BBox,
    node_boxes: list[BBox],
    spans: list[object],
) -> Flowchart | None:
    rows = _group_rows(node_boxes)
    if len(rows) < 2:
        return None
    paired = sum(1 for row in rows if len(row) >= 2)
    if paired < 1:
        return None

    nodes: list[FlowchartNode] = []
    for row in rows:
        left = row[0]
        right = row[-1] if len(row) >= 2 and row[-1][0] - left[2] >= _PAIR_X_GAP else None
        left_text = _text_in_box(spans, left)
        if not left_text:
            continue
        if right is not None:
            yes_text = _text_in_box(spans, right)
            nodes.append(
                FlowchartNode(
                    kind="condition",
                    text=left_text,
                    bbox=left,
                    yes_text=yes_text or None,
                    yes_bbox=right,
                )
            )
            continue
        if _looks_like_decision(left_text):
            nodes.append(FlowchartNode(kind="condition", text=left_text, bbox=left))
        else:
            nodes.append(FlowchartNode(kind="result", text=left_text, bbox=left))

    conditions = [n for n in nodes if n.kind == "condition"]
    if len(conditions) < 2:
        return None
    if not any(n.yes_text for n in conditions):
        return None
    region = _region_text(spans, parent)
    if not (_looks_like_decision(region) or any(_looks_like_decision(n.text) for n in nodes)):
        return None
    return Flowchart(bbox=parent, nodes=nodes, title=FLOWCHART_TITLE)


def detect_flowcharts(
    boxes: list[BBox],
    spans: list[object] | None = None,
) -> list[Flowchart]:
    """작은 상자 군집이 조건/결과 쌍으로 쌓이면 Flowchart로 승격."""
    span_list = list(spans or [])
    node_boxes = [box for box in boxes if _is_node_box(box)]
    if len(node_boxes) < _MIN_NODE_BOXES:
        return []

    parent_hits: list[tuple[BBox, list[BBox]]] = []
    for cand in boxes:
        if _is_node_box(cand):
            continue
        kids = [node for node in node_boxes if _contains(cand, node)]
        if len(kids) >= _MIN_NODE_BOXES:
            parent_hits.append((cand, kids))
    parent_hits.sort(
        key=lambda item: (item[0][2] - item[0][0]) * (item[0][3] - item[0][1])
    )

    used: list[BBox] = []
    found: list[Flowchart] = []

    def _already_used(box: BBox) -> bool:
        return any(_same_box(box, prev) for prev in used)

    for parent, kids in parent_hits:
        if any(_already_used(kid) for kid in kids):
            continue
        flowchart = _build_flowchart(parent, kids, span_list)
        if flowchart is None:
            continue
        found.append(flowchart)
        used.extend(kids)

    leftover = [box for box in node_boxes if not _already_used(box)]
    if len(leftover) >= _MIN_NODE_BOXES:
        clustered = _cluster_stacked(leftover)
        for cluster in clustered:
            if any(_already_used(box) for box in cluster):
                continue
            parent = _union_bbox(cluster)
            flowchart = _build_flowchart(parent, cluster, span_list)
            if flowchart is None:
                continue
            found.append(flowchart)
            used.extend(cluster)

    found.sort(key=lambda fc: (fc.bbox[1], fc.bbox[0]))
    return found


def _cluster_stacked(boxes: list[BBox]) -> list[list[BBox]]:
    """비슷한 x0으로 세로 쌓인 상자 군집."""
    if not boxes:
        return []
    ordered = sorted(boxes, key=lambda b: (b[0], b[1]))
    clusters: list[list[BBox]] = []
    current = [ordered[0]]
    for box in ordered[1:]:
        prev = current[-1]
        same_col = abs(box[0] - prev[0]) <= 18.0
        close_y = box[1] - prev[3] <= 40.0
        if same_col and close_y:
            current.append(box)
            continue
        if len(current) >= _MIN_NODE_BOXES:
            # include right-hand partners near this stack
            clusters.append(_with_row_partners(current, boxes))
        current = [box]
    if len(current) >= 2:
        clusters.append(_with_row_partners(current, boxes))
    return [c for c in clusters if len(c) >= _MIN_NODE_BOXES]


def _with_row_partners(stack: list[BBox], all_nodes: list[BBox]) -> list[BBox]:
    out = list(stack)
    for left in stack:
        for cand in all_nodes:
            if _same_box(cand, left):
                continue
            if abs(cand[1] - left[1]) <= _ROW_Y_TOL and cand[0] - left[2] >= _PAIR_X_GAP:
                if not any(_same_box(cand, existing) for existing in out):
                    out.append(cand)
    return out


def serialize_flowchart(flowchart: Flowchart) -> str:
    """점자용 선형 구조. 상자 테두리·↓/→ 도형은 쓰지 않는다."""
    lines = [flowchart.title or FLOWCHART_TITLE]
    step = 0
    for index, node in enumerate(flowchart.nodes):
        if node.kind == "result":
            continue
        step += 1
        lines.append(f"{step}. {node.text}")
        if node.yes_text:
            lines.append(f"   예 → {node.yes_text}")
        nxt = flowchart.nodes[index + 1] if index + 1 < len(flowchart.nodes) else None
        if nxt is None:
            continue
        if nxt.kind == "result":
            lines.append(f"   아니요 → {nxt.text}")
        else:
            lines.append(f"   아니요 → {step + 1}번으로")
    return "\n".join(lines)


def is_flowchart_line(line: PdfLine) -> bool:
    return FLOWCHART_LINE_ID in (line.id or "")


def line_in_flowchart(line: PdfLine, flowchart: Flowchart) -> bool:
    if line_mostly_in_box(line.bbox, flowchart.bbox, min_overlap=0.28):
        return True
    cx = (line.bbox[0] + line.bbox[2]) / 2
    cy = (line.bbox[1] + line.bbox[3]) / 2
    box = flowchart.bbox
    return box[0] <= cx <= box[2] and box[1] <= cy <= box[3]


def promote_flowcharts_into_lines(
    lines: list[PdfLine],
    flowcharts: list[Flowchart],
    *,
    page_number: int,
) -> list[PdfLine]:
    """순서도 영역 행을 선형 구조 한 덩어리로 교체한다."""
    if not flowcharts:
        return lines
    kept = [
        line
        for line in lines
        if not any(line_in_flowchart(line, fc) for fc in flowcharts)
    ]
    for index, flowchart in enumerate(flowcharts):
        kept.append(
            PdfLine(
                id=f"p{page_number}-{FLOWCHART_LINE_ID}-{index}",
                text=serialize_flowchart(flowchart),
                bbox=flowchart.bbox,
                span_ids=[],
                page_number=page_number,
                reading_order=0,
            )
        )
    kept.sort(key=lambda ln: (ln.bbox[1], ln.bbox[0]))
    for order, line in enumerate(kept):
        line.reading_order = order
    return kept


def exclude_flowchart_boxes(
    boxes: list[BBox],
    flowcharts: list[Flowchart],
) -> list[BBox]:
    """순서도 상자·외곽은 표선(────) 출력에서 뺀다."""
    if not flowcharts:
        return boxes
    kept: list[BBox] = []
    for box in boxes:
        skip = False
        for flowchart in flowcharts:
            if _same_box(box, flowchart.bbox):
                skip = True
                break
            if _contains(flowchart.bbox, box, pad=2.0):
                skip = True
                break
            if any(_same_box(box, node_box) for node_box in flowchart.node_bboxes()):
                skip = True
                break
        if not skip:
            kept.append(box)
    return kept


__all__ = [
    "FLOWCHART_LINE_ID",
    "FLOWCHART_TITLE",
    "Flowchart",
    "FlowchartNode",
    "detect_flowcharts",
    "exclude_flowchart_boxes",
    "is_flowchart_line",
    "promote_flowcharts_into_lines",
    "serialize_flowchart",
]
