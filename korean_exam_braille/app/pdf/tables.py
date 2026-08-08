"""PDF 벡터 셀(`re`)·공유 선(`l`)에서 표 격자와 셀 텍스트를 복원한다."""

from __future__ import annotations

from typing import Any

from korean_exam_braille.app.pdf.boxes import _dedupe_segments, _merge_collinear
from korean_exam_braille.app.pdf.models import BBox, PdfSpan, PdfTable, PdfTableCell

_COORD_TOL = 0.8
_GRID_TOL = 1.5
_MIN_CELL_SIZE = 5.0
_MIN_TEXT_OCCUPANCY = 0.5


def _rect_item_bbox(item: tuple[Any, ...]) -> BBox | None:
    if not item or item[0] != "re" or len(item) < 2:
        return None
    rect = item[1]
    try:
        return (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))
    except AttributeError:
        return None


def _dedupe_rects(rects: list[BBox]) -> list[BBox]:
    kept: list[BBox] = []
    for rect in sorted(rects, key=lambda b: (b[1], b[0], b[3], b[2])):
        if any(all(abs(a - b) <= _COORD_TOL for a, b in zip(rect, old)) for old in kept):
            continue
        kept.append(rect)
    return kept


def _share_cell_edge(a: BBox, b: BBox) -> bool:
    """두 셀이 수평/수직 경계를 공유하는지."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    vertical = (
        abs(ax1 - bx0) <= _COORD_TOL or abs(bx1 - ax0) <= _COORD_TOL
    ) and min(ay1, by1) - max(ay0, by0) >= _MIN_CELL_SIZE
    horizontal = (
        abs(ay1 - by0) <= _COORD_TOL or abs(by1 - ay0) <= _COORD_TOL
    ) and min(ax1, bx1) - max(ax0, bx0) >= _MIN_CELL_SIZE
    return vertical or horizontal


def _cell_components(rects: list[BBox]) -> list[list[BBox]]:
    neighbors: dict[int, set[int]] = {i: set() for i in range(len(rects))}
    for i, left in enumerate(rects):
        for j in range(i + 1, len(rects)):
            if _share_cell_edge(left, rects[j]):
                neighbors[i].add(j)
                neighbors[j].add(i)

    # 고립된 외곽 박스는 표 셀이 아니다.
    active = {i for i, linked in neighbors.items() if linked}
    components: list[list[BBox]] = []
    while active:
        start = active.pop()
        stack = [start]
        indexes = [start]
        while stack:
            current = stack.pop()
            for nxt in neighbors[current]:
                if nxt in active:
                    active.remove(nxt)
                    indexes.append(nxt)
                    stack.append(nxt)
        components.append([rects[i] for i in indexes])
    return components


def _cluster_coords(values: list[float]) -> list[float]:
    groups: list[list[float]] = []
    for value in sorted(values):
        if groups and abs(value - sum(groups[-1]) / len(groups[-1])) <= _COORD_TOL:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [sum(group) / len(group) for group in groups]


def _coord_index(coords: list[float], value: float) -> int | None:
    for i, coord in enumerate(coords):
        if abs(coord - value) <= _COORD_TOL:
            return i
    return None


def _text_in_bbox(spans: list[PdfSpan], bbox: BBox) -> str:
    x0, y0, x1, y1 = bbox
    inside: list[PdfSpan] = []
    for span in spans:
        sx0, sy0, sx1, sy1 = span.bbox
        cx, cy = (sx0 + sx1) / 2.0, (sy0 + sy1) / 2.0
        if x0 - 1.0 <= cx <= x1 + 1.0 and y0 - 1.0 <= cy <= y1 + 1.0:
            inside.append(span)
    inside.sort(key=lambda span: (span.bbox[1], span.bbox[0], span.extraction_index))
    return " ".join(span.text.strip() for span in inside if span.text.strip())


def _table_from_component(rects: list[BBox], spans: list[PdfSpan]) -> PdfTable | None:
    xs = _cluster_coords([value for rect in rects for value in (rect[0], rect[2])])
    ys = _cluster_coords([value for rect in rects for value in (rect[1], rect[3])])
    if len(xs) < 3 or len(ys) < 3:
        return None

    slots: dict[tuple[int, int], BBox] = {}
    for rect in rects:
        x0i = _coord_index(xs, rect[0])
        x1i = _coord_index(xs, rect[2])
        y0i = _coord_index(ys, rect[1])
        y1i = _coord_index(ys, rect[3])
        if None in {x0i, x1i, y0i, y1i}:
            continue
        if x1i == x0i + 1 and y1i == y0i + 1:
            slots[(y0i, x0i)] = rect

    row_count, column_count = len(ys) - 1, len(xs) - 1
    # 벡터 셀이 대부분 닫혀 있어야 고신뢰도 표로 인정한다.
    if len(slots) < row_count * column_count * 0.8:
        return None

    cells: list[PdfTableCell] = []
    for row in range(row_count):
        for column in range(column_count):
            bbox = slots.get(
                (row, column),
                (xs[column], ys[row], xs[column + 1], ys[row + 1]),
            )
            cells.append(
                PdfTableCell(
                    row=row,
                    column=column,
                    bbox=bbox,
                    text=_text_in_bbox(spans, bbox),
                )
            )
    return PdfTable(
        bbox=(xs[0], ys[0], xs[-1], ys[-1]),
        row_count=row_count,
        column_count=column_count,
        cells=cells,
    )


def _collect_grid_segments(
    page: Any,
) -> tuple[
    list[tuple[float, float, float]],
    list[tuple[float, float, float]],
    list[BBox],
]:
    """`re`를 네 변으로 펼치고 `l`과 합쳐 (수평, 수직, rect) 반환."""
    horizontal: list[tuple[float, float, float]] = []
    vertical: list[tuple[float, float, float]] = []
    rects: list[BBox] = []
    for drawing in page.get_drawings() or []:
        for item in drawing.get("items") or []:
            if not item:
                continue
            rect = _rect_item_bbox(item)
            if rect is not None:
                x0, y0, x1, y1 = rect
                if x1 - x0 < _MIN_CELL_SIZE or y1 - y0 < _MIN_CELL_SIZE:
                    continue
                rects.append(rect)
                horizontal.extend(((x0, x1, y0), (x0, x1, y1)))
                vertical.extend(((y0, y1, x0), (y0, y1, x1)))
                continue
            if item[0] != "l" or len(item) < 3:
                continue
            p1, p2 = item[1], item[2]
            xa, ya = float(p1.x), float(p1.y)
            xb, yb = float(p2.x), float(p2.y)
            if abs(ya - yb) <= _GRID_TOL and abs(xa - xb) >= _MIN_CELL_SIZE:
                horizontal.append((min(xa, xb), max(xa, xb), (ya + yb) / 2.0))
            elif abs(xa - xb) <= _GRID_TOL and abs(ya - yb) >= _MIN_CELL_SIZE:
                vertical.append((min(ya, yb), max(ya, yb), (xa + xb) / 2.0))

    # 같은 경계를 re와 l이 중복 제공해도 하나의 연속선으로 정규화한다.
    horizontal = _merge_collinear(_dedupe_segments(horizontal), axis_tol=_GRID_TOL)
    vertical = _merge_collinear(_dedupe_segments(vertical), axis_tol=_GRID_TOL)
    return horizontal, vertical, _dedupe_rects(rects)


def _covers(start: float, end: float, target_start: float, target_end: float) -> bool:
    target_length = max(target_end - target_start, 1.0)
    overlap = min(end, target_end) - max(start, target_start)
    return overlap / target_length >= 0.8


def _table_from_grid(
    xs: list[float],
    ys: list[float],
    spans: list[PdfSpan],
) -> PdfTable | None:
    if len(xs) < 3 or len(ys) < 3:
        return None
    row_count, column_count = len(ys) - 1, len(xs) - 1
    if row_count * column_count < 4:
        return None

    cells: list[PdfTableCell] = []
    occupied = 0
    for row in range(row_count):
        for column in range(column_count):
            bbox = (xs[column], ys[row], xs[column + 1], ys[row + 1])
            text = _text_in_bbox(spans, bbox)
            occupied += bool(text)
            cells.append(PdfTableCell(row=row, column=column, bbox=bbox, text=text))
    if occupied / len(cells) < _MIN_TEXT_OCCUPANCY:
        return None
    return PdfTable(
        bbox=(xs[0], ys[0], xs[-1], ys[-1]),
        row_count=row_count,
        column_count=column_count,
        cells=cells,
        confidence=0.9,
    )


def _tables_from_line_grid(
    horizontal: list[tuple[float, float, float]],
    vertical: list[tuple[float, float, float]],
    spans: list[PdfSpan],
) -> list[PdfTable]:
    """공유 경계선의 반복 x/y와 연결률로 표 후보를 만든다."""
    y_candidates = _cluster_coords([segment[2] for segment in horizontal])
    candidates: list[PdfTable] = []
    for top_index, top in enumerate(y_candidates):
        for bottom in y_candidates[top_index + 2 :]:
            if bottom - top < _MIN_CELL_SIZE * 2:
                continue
            spanning_vertical = [
                segment
                for segment in vertical
                if _covers(segment[0], segment[1], top, bottom)
            ]
            xs = _cluster_coords([segment[2] for segment in spanning_vertical])
            if len(xs) < 3:
                continue
            left, right = xs[0], xs[-1]
            spanning_horizontal = [
                segment
                for segment in horizontal
                if top - _GRID_TOL <= segment[2] <= bottom + _GRID_TOL
                and _covers(segment[0], segment[1], left, right)
            ]
            ys = _cluster_coords([segment[2] for segment in spanning_horizontal])
            if len(ys) < 3:
                continue
            table = _table_from_grid(xs, ys, spans)
            if table is not None:
                candidates.append(table)

    # 동일 격자의 부분 후보보다 행·열을 모두 포함한 최대 후보를 우선한다.
    candidates.sort(
        key=lambda table: (
            -((table.bbox[2] - table.bbox[0]) * (table.bbox[3] - table.bbox[1])),
            table.bbox[1],
            table.bbox[0],
        )
    )
    kept: list[PdfTable] = []
    for table in candidates:
        if any(
            table.bbox[0] >= old.bbox[0] - _GRID_TOL
            and table.bbox[1] >= old.bbox[1] - _GRID_TOL
            and table.bbox[2] <= old.bbox[2] + _GRID_TOL
            and table.bbox[3] <= old.bbox[3] + _GRID_TOL
            for old in kept
        ):
            continue
        kept.append(table)
    return kept


def _dedupe_tables(tables: list[PdfTable]) -> list[PdfTable]:
    kept: list[PdfTable] = []
    for table in sorted(tables, key=lambda item: (-item.confidence, item.bbox[1], item.bbox[0])):
        if any(
            all(abs(a - b) <= _GRID_TOL for a, b in zip(table.bbox, old.bbox))
            for old in kept
        ):
            continue
        kept.append(table)
    return sorted(kept, key=lambda table: (table.bbox[1], table.bbox[0]))


def vector_table_diagnostics(page: Any) -> dict[str, object]:
    """실제 PDF에서 표 탈락 원인을 확인할 수 있는 정규화 좌표 로그."""
    horizontal, vertical, rects = _collect_grid_segments(page)
    return {
        "rect_count": len(rects),
        "horizontal": [
            {"x0": round(x0, 2), "x1": round(x1, 2), "y": round(y, 2)}
            for x0, x1, y in horizontal
        ],
        "vertical": [
            {"y0": round(y0, 2), "y1": round(y1, 2), "x": round(x, 2)}
            for y0, y1, x in vertical
        ],
        "x_clusters": [round(x, 2) for x in _cluster_coords([v[2] for v in vertical])],
        "y_clusters": [round(y, 2) for y in _cluster_coords([h[2] for h in horizontal])],
    }


def detect_vector_tables(page: Any, spans: list[PdfSpan]) -> list[PdfTable]:
    """개별 `re` 또는 공유 `l` 경계로 확인한 2×2 이상 표를 반환한다."""
    horizontal, vertical, rects = _collect_grid_segments(page)
    rect_tables = [
        table
        for component in _cell_components(rects)
        if (table := _table_from_component(component, spans)) is not None
    ]
    line_tables = _tables_from_line_grid(horizontal, vertical, spans)
    return _dedupe_tables(rect_tables + line_tables)
