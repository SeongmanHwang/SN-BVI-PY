"""PDF 벡터 셀(`re`)·공유 선(`l`)에서 표 격자와 셀 텍스트를 복원한다."""

from __future__ import annotations

from typing import Any

from korean_exam_braille.app.pdf.boxes import (
    _dedupe_segments,
    _merge_collinear,
    line_mostly_in_box,
)
from korean_exam_braille.app.pdf.models import (
    BBox,
    PdfLine,
    PdfSpan,
    PdfTable,
    PdfTableCell,
)

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


def _matches_band_height(
    segment: tuple[float, float, float],
    top: float,
    bottom: float,
) -> bool:
    """표 구간 높이와 세로선 길이가 비슷한지. 긴 프레임 세로선을 걸러낸다."""
    band_height = bottom - top
    return abs((segment[1] - segment[0]) - band_height) <= _GRID_TOL


def _has_vertical_edge(
    vertical: list[tuple[float, float, float]],
    x: float,
    y0: float,
    y1: float,
) -> bool:
    return any(
        abs(vx - x) <= _GRID_TOL and _covers(vy0, vy1, y0, y1)
        for vy0, vy1, vx in vertical
    )


def _has_horizontal_edge(
    horizontal: list[tuple[float, float, float]],
    y: float,
    x0: float,
    x1: float,
) -> bool:
    return any(
        abs(hy - y) <= _GRID_TOL and _covers(hx0, hx1, x0, x1)
        for hx0, hx1, hy in horizontal
    )


def _table_from_merge_grid(
    xs: list[float],
    ys: list[float],
    horizontal: list[tuple[float, float, float]],
    vertical: list[tuple[float, float, float]],
    spans: list[PdfSpan],
) -> PdfTable | None:
    """부분 선 유무로 rowspan/colspan을 추론한 표를 만든다."""
    if len(xs) < 3 or len(ys) < 3:
        return None
    row_count, column_count = len(ys) - 1, len(xs) - 1
    if row_count * column_count < 4:
        return None

    covered: set[tuple[int, int]] = set()
    cells: list[PdfTableCell] = []
    occupied_atomic = 0
    for row in range(row_count):
        for column in range(column_count):
            if (row, column) in covered:
                continue
            colspan = 1
            while column + colspan < column_count:
                edge_x = xs[column + colspan]
                if _has_vertical_edge(vertical, edge_x, ys[row], ys[row + 1]):
                    break
                colspan += 1
            rowspan = 1
            while row + rowspan < row_count:
                edge_y = ys[row + rowspan]
                if _has_horizontal_edge(
                    horizontal, edge_y, xs[column], xs[column + colspan]
                ):
                    break
                rowspan += 1
            for rr in range(row, row + rowspan):
                for cc in range(column, column + colspan):
                    covered.add((rr, cc))
            bbox = (
                xs[column],
                ys[row],
                xs[column + colspan],
                ys[row + rowspan],
            )
            text = _text_in_bbox(spans, bbox)
            if text:
                occupied_atomic += rowspan * colspan
            cells.append(
                PdfTableCell(
                    row=row,
                    column=column,
                    bbox=bbox,
                    text=text,
                    rowspan=rowspan,
                    colspan=colspan,
                )
            )
    if occupied_atomic / (row_count * column_count) < _MIN_TEXT_OCCUPANCY:
        return None
    return PdfTable(
        bbox=(xs[0], ys[0], xs[-1], ys[-1]),
        row_count=row_count,
        column_count=column_count,
        cells=cells,
        confidence=0.9,
    )


def _group_aligned_horizontals(
    horizontal: list[tuple[float, float, float]],
) -> list[list[tuple[float, float, float]]]:
    """양 끝(x0,x1)이 같은 가로선끼리 묶는다. 페이지 긴 세로선과 섞지 않기 위함."""
    groups: list[list[tuple[float, float, float]]] = []
    for segment in sorted(horizontal, key=lambda item: (item[0], item[1], item[2])):
        x0, x1, _y = segment
        for group in groups:
            left = sum(item[0] for item in group) / len(group)
            right = sum(item[1] for item in group) / len(group)
            if abs(x0 - left) <= _GRID_TOL and abs(x1 - right) <= _GRID_TOL:
                group.append(segment)
                break
        else:
            groups.append([segment])
    return groups


def _local_segments_in_band(
    horizontal: list[tuple[float, float, float]],
    vertical: list[tuple[float, float, float]],
    *,
    left: float,
    right: float,
    top: float,
    bottom: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    """표 bbox 안의 부분 가로·세로선을 모은다(짧은 내부선 포함)."""
    local_h = [
        segment
        for segment in horizontal
        if top - _GRID_TOL <= segment[2] <= bottom + _GRID_TOL
        and min(segment[1], right) - max(segment[0], left) >= _MIN_CELL_SIZE
    ]
    local_v = [
        segment
        for segment in vertical
        if left - _GRID_TOL <= segment[2] <= right + _GRID_TOL
        and min(segment[1], bottom) - max(segment[0], top) >= _MIN_CELL_SIZE
    ]
    return local_h, local_v


def _tables_from_line_grid(
    horizontal: list[tuple[float, float, float]],
    vertical: list[tuple[float, float, float]],
    spans: list[PdfSpan],
) -> list[PdfTable]:
    """전체 폭 가로선으로 외곽을 잡고, 부분 선으로 병합 셀 격자를 복원한다."""
    candidates: list[PdfTable] = []
    for group in _group_aligned_horizontals(horizontal):
        frame_ys = _cluster_coords([segment[2] for segment in group])
        if len(frame_ys) < 3:
            continue
        left = sum(segment[0] for segment in group) / len(group)
        right = sum(segment[1] for segment in group) / len(group)
        # 같은 폭의 자료 박스 가로선까지 한 묶음이 될 수 있으므로,
        # 외곽 세로선이 덮는 부분 구간만 표 후보로 본다.
        for top_index, top in enumerate(frame_ys):
            for bottom_index in range(top_index + 2, len(frame_ys)):
                bottom = frame_ys[bottom_index]
                if bottom - top < _MIN_CELL_SIZE * 2:
                    continue
                outer_vertical = [
                    segment
                    for segment in vertical
                    if _covers(segment[0], segment[1], top, bottom)
                    and left - _GRID_TOL <= segment[2] <= right + _GRID_TOL
                    and _matches_band_height(segment, top, bottom)
                ]
                outer_xs = _cluster_coords([segment[2] for segment in outer_vertical])
                if len(outer_xs) < 2:
                    continue
                if abs(outer_xs[0] - left) > _GRID_TOL or abs(outer_xs[-1] - right) > _GRID_TOL:
                    continue
                local_h, local_v = _local_segments_in_band(
                    horizontal,
                    vertical,
                    left=left,
                    right=right,
                    top=top,
                    bottom=bottom,
                )
                xs = _cluster_coords(
                    [left, right] + [segment[2] for segment in local_v]
                )
                ys = _cluster_coords(
                    [top, bottom] + [segment[2] for segment in local_h]
                )
                # 외곽 가로선 묶음의 행 경계도 유지한다.
                ys = _cluster_coords(ys + frame_ys[top_index : bottom_index + 1])
                if abs(xs[0] - left) > _GRID_TOL or abs(xs[-1] - right) > _GRID_TOL:
                    continue
                table = _table_from_merge_grid(xs, ys, local_h, local_v, spans)
                if table is not None:
                    candidates.append(table)

    # 동일 격자의 부분 후보보다 행·열을 모두 포함한 최대 후보를 우선한다.
    candidates.sort(
        key=lambda table: (
            -((table.bbox[2] - table.bbox[0]) * (table.bbox[3] - table.bbox[1])),
            -table.column_count,
            -table.row_count,
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


def _cell_owner_grid(
    table: PdfTable,
) -> list[list[PdfTableCell | None]]:
    """atomic (row, col) → 덮는 셀."""
    grid: list[list[PdfTableCell | None]] = [
        [None] * table.column_count for _ in range(table.row_count)
    ]
    for cell in table.cells:
        for row in range(cell.row, cell.row + max(cell.rowspan, 1)):
            if row >= table.row_count:
                break
            for column in range(cell.column, cell.column + max(cell.colspan, 1)):
                if column >= table.column_count:
                    break
                grid[row][column] = cell
    return grid


def _foldable_header_child_row(table: PdfTable, owner: list[list[PdfTableCell | None]]) -> int | None:
    """row0 colspan 부모 아래 leaf 헤더가 있는 행(보통 1). 없으면 None."""
    if table.row_count < 2:
        return None
    parents = [
        cell
        for cell in table.cells
        if cell.row == 0 and max(cell.colspan, 1) > 1 and (cell.text or "").strip()
    ]
    if not parents:
        return None
    child_row = 1
    for parent in parents:
        children: list[str] = []
        for column in range(parent.column, parent.column + parent.colspan):
            if column >= table.column_count:
                return None
            child = owner[child_row][column]
            if (
                child is None
                or child.row != child_row
                or child.column != column
                or not (child.text or "").strip()
            ):
                return None
            children.append((child.text or "").strip())
        if len(children) != parent.colspan:
            return None
    return child_row


def _format_header_line(
    table: PdfTable,
    owner: list[list[PdfTableCell | None]],
    *,
    child_row: int,
) -> str:
    parts: list[str] = []
    column = 0
    while column < table.column_count:
        cell = owner[0][column]
        if cell is None or cell.row != 0 or cell.column != column:
            column += 1
            continue
        text = (cell.text or "").strip()
        colspan = max(cell.colspan, 1)
        if colspan > 1:
            children: list[str] = []
            for child_col in range(column, column + colspan):
                child = owner[child_row][child_col]
                children.append("" if child is None else (child.text or "").strip())
            parts.append(f"{text}({'  '.join(children)})")
        else:
            parts.append(text)
        column += colspan
    return "  ".join(parts)


def _format_body_line(
    table: PdfTable,
    owner: list[list[PdfTableCell | None]],
    row: int,
) -> str:
    parts: list[str] = []
    column = 0
    while column < table.column_count:
        cell = owner[row][column]
        if cell is None:
            parts.append("")
            column += 1
            continue
        if cell.row == row and cell.column == column:
            parts.append((cell.text or "").strip())
            column += max(cell.colspan, 1)
            continue
        column += 1
    return "  ".join(parts)


def format_table_rows(table: PdfTable) -> list[tuple[str, float, float]]:
    """표 행을 (묵자, y0, y1)로 직렬화한다. 계층 헤더는 한 줄로 접는다."""
    if not table.cells:
        return []
    owner = _cell_owner_grid(table)
    child_row = _foldable_header_child_row(table, owner)
    skip_rows = {child_row} if child_row is not None else set()
    rows: list[tuple[str, float, float]] = []
    for row in range(table.row_count):
        if row in skip_rows:
            continue
        if row == 0 and child_row is not None:
            text = _format_header_line(table, owner, child_row=child_row)
            header_cells = [
                cell
                for cell in table.cells
                if cell.row in {0, child_row}
            ]
        else:
            text = _format_body_line(table, owner, row)
            header_cells = [cell for cell in table.cells if cell.row == row]
        if not header_cells and not text.strip():
            continue
        if not header_cells:
            # rowspan만으로 덮인 행 — 본문 토큰이 있으면 bbox는 표 폭·행 추정 불가 시 skip
            continue
        y0 = min(cell.bbox[1] for cell in header_cells)
        y1 = max(cell.bbox[3] for cell in header_cells)
        rows.append((text, y0, y1))
    return rows


def format_table_row_texts(table: PdfTable) -> list[str]:
    """표 행을 묵자 한 줄씩으로 직렬화한다."""
    return [text for text, _y0, _y1 in format_table_rows(table)]


def box_matches_table(box: BBox, tables: list[PdfTable], *, tol: float = 3.0) -> bool:
    """박스 표선용 외곽이 표 격자 자체이면 True."""
    return any(
        all(abs(a - b) <= tol for a, b in zip(box, table.bbox)) for table in tables
    )


def clear_underlines_inside_tables(spans: list[PdfSpan], tables: list[PdfTable]) -> None:
    """표 격자선을 밑줄로 오인한 span 강조를 제거한다."""
    if not tables:
        return
    for span in spans:
        cx = (span.bbox[0] + span.bbox[2]) / 2.0
        cy = (span.bbox[1] + span.bbox[3]) / 2.0
        if any(
            table.bbox[0] - 1.0 <= cx <= table.bbox[2] + 1.0
            and table.bbox[1] - 1.0 <= cy <= table.bbox[3] + 1.0
            for table in tables
        ):
            span.underline_ranges = []
            span.is_underline = False


def promote_tables_into_lines(
    lines: list[PdfLine],
    tables: list[PdfTable],
    *,
    page_number: int,
) -> list[PdfLine]:
    """표 영역 원문 행을 셀 격자 행으로 바꾼다."""
    if not lines or not tables:
        return lines

    kept = [
        line
        for line in lines
        if not any(
            line_mostly_in_box(line.bbox, table.bbox, min_overlap=0.3)
            for table in tables
        )
    ]
    promoted: list[PdfLine] = []
    for table_index, table in enumerate(tables):
        for row, (text, y0, y1) in enumerate(format_table_rows(table)):
            promoted.append(
                PdfLine(
                    id=f"p{page_number}-table{table_index}-r{row}",
                    text=text,
                    bbox=(table.bbox[0], y0, table.bbox[2], y1),
                    span_ids=[],
                    page_number=page_number,
                    reading_order=0,
                )
            )

    merged = kept + promoted
    merged.sort(key=lambda line: (line.bbox[1], line.bbox[0], line.id))
    for index, line in enumerate(merged):
        line.reading_order = index
    return merged
