"""병렬 선택지(①~⑤ × ㉠/㉡ …) 감지 후 행 텍스트 재조합.

「3열인가?」가 아니라 여러 행에서 같은 x축 정렬이 반복되는지,
선택지 번호·열 헤더가 함께인지를 보고 높은 신뢰도일 때만 승격한다.
확신이 없으면 기존 reading order 줄을 그대로 둔다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from korean_exam_braille.app.pdf.models import BBox, PdfLine, PdfSpan

_CHOICE_MARKERS = ("①", "②", "③", "④", "⑤")
_CHOICE_SET = frozenset(_CHOICE_MARKERS)
_HEADER_RE = re.compile(r"^[㉠-㉭]$")
_CELL_SEP = " / "

# 줄 간격·셀 간격 휴리스틱
_MIN_CHOICE_ROWS = 4
_MIN_TEXT_LANES = 2
_MIN_CONFIDENCE = 0.78
# 페이지 2단(선택지|본문) 오탐 방지: ㉠/㉡류 열 헤더 없으면 승격하지 않음
_REQUIRE_COLUMN_HEADERS = True


@dataclass
class _Cell:
    spans: list[PdfSpan]
    text: str
    x_mid: float
    bbox: BBox


@dataclass
class _Row:
    y_mid: float
    cells: list[_Cell]
    spans: list[PdfSpan]


@dataclass
class ParallelChoiceHit:
    """감지된 병렬 선택지 구역."""

    headers: list[str]
    rows: list[tuple[str, list[str]]]  # (①, [col0, col1, …])
    span_ids: set[str] = field(default_factory=set)
    bbox: BBox = (0.0, 0.0, 0.0, 0.0)
    confidence: float = 0.0


def _union_bbox(boxes: list[BBox]) -> BBox:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _y_mid(span: PdfSpan) -> float:
    return (span.bbox[1] + span.bbox[3]) / 2


def _x_mid(bbox: BBox) -> float:
    return (bbox[0] + bbox[2]) / 2


def _cluster_by_y(spans: list[PdfSpan], *, y_tol: float) -> list[list[PdfSpan]]:
    if not spans:
        return []
    ordered = sorted(spans, key=lambda s: (_y_mid(s), s.bbox[0], s.extraction_index))
    groups: list[list[PdfSpan]] = []
    current: list[PdfSpan] = []
    cur_y: float | None = None
    for span in ordered:
        ym = _y_mid(span)
        if cur_y is None or abs(ym - cur_y) <= y_tol:
            current.append(span)
            cur_y = sum(_y_mid(s) for s in current) / len(current)
        else:
            groups.append(current)
            current = [span]
            cur_y = ym
    if current:
        groups.append(current)
    return groups


def _join_cell_text(spans: list[PdfSpan]) -> str:
    raw = "".join(s.text for s in spans)
    return " ".join(raw.split())


def _cluster_row_cells(
    spans: list[PdfSpan],
    *,
    gap_min: float,
) -> list[_Cell]:
    """한 시각 행 안 span을 가로 gap으로 셀 분할."""
    if not spans:
        return []
    ordered = sorted(spans, key=lambda s: (s.bbox[0], s.extraction_index))
    groups: list[list[PdfSpan]] = [[ordered[0]]]
    for span in ordered[1:]:
        prev = groups[-1][-1]
        gap = span.bbox[0] - prev.bbox[2]
        if gap >= gap_min:
            groups.append([span])
        else:
            groups[-1].append(span)
    cells: list[_Cell] = []
    for g in groups:
        text = _join_cell_text(g)
        if not text.strip():
            continue
        bbox = _union_bbox([s.bbox for s in g])
        cells.append(_Cell(spans=g, text=text.strip(), x_mid=_x_mid(bbox), bbox=bbox))
    return cells


def _peel_marker(text: str) -> tuple[str | None, str]:
    t = text.strip()
    for m in _CHOICE_MARKERS:
        if t == m:
            return m, ""
        if t.startswith(m):
            rest = t[len(m) :].lstrip(" .)．。\t")
            return m, rest
    return None, t


def _parse_choice_row(cells: list[_Cell]) -> tuple[str, list[_Cell]] | None:
    """마커 + 본문 셀들. 본문 셀이 2개 미만이면 None.

    같은 y에 다른 단(지문 등)이 붙어 있어도, 행 안에서 선택지 마커가
    처음 나타나는 셀부터 해석한다(선행 잡음 셀은 무시).
    """
    if not cells:
        return None
    start = None
    for idx, cell in enumerate(cells):
        marker, _rest = _peel_marker(cell.text)
        if marker is not None or cell.text.strip() in _CHOICE_SET:
            start = idx
            break
    if start is None:
        return None
    sub = cells[start:]
    marker, rest = _peel_marker(sub[0].text)
    if marker is None:
        if sub[0].text.strip() in _CHOICE_SET and len(sub) >= 3:
            return sub[0].text.strip(), sub[1:]
        return None
    body: list[_Cell] = []
    if rest:
        # 마커와 첫 본문이 한 셀에 붙음 → 가상 셀
        c0 = sub[0]
        body.append(
            _Cell(
                spans=c0.spans,
                text=rest,
                x_mid=c0.x_mid,
                bbox=c0.bbox,
            )
        )
        body.extend(sub[1:])
    else:
        body = list(sub[1:])
    if len(body) < _MIN_TEXT_LANES:
        return None
    return marker, body


def _cluster_lane_centers(
    values: list[float],
    *,
    tol: float,
) -> list[float]:
    if not values:
        return []
    ordered = sorted(values)
    groups: list[list[float]] = [[ordered[0]]]
    for v in ordered[1:]:
        if abs(v - groups[-1][-1]) <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [sum(g) / len(g) for g in groups]


def _assign_to_lanes(
    bodies: list[_Cell],
    lanes: list[float],
    *,
    tol: float,
) -> list[str] | None:
    """본문 셀을 lane 순서로 배치. 한 lane에 중복·빈칸 과다면 실패."""
    out = [""] * len(lanes)
    used: set[int] = set()
    for cell in bodies:
        best_i = None
        best_d = None
        for i, lx in enumerate(lanes):
            if i in used:
                continue
            d = abs(cell.x_mid - lx)
            if d <= tol and (best_d is None or d < best_d):
                best_d = d
                best_i = i
        if best_i is None:
            return None
        used.add(best_i)
        out[best_i] = cell.text
    if sum(1 for t in out if t) < _MIN_TEXT_LANES:
        return None
    return out


def _header_cells(cells: list[_Cell]) -> list[_Cell]:
    """행에서 ㉠–㉭ 단독 헤더 셀만 골라 x 순으로 반환."""
    found = [c for c in cells if _HEADER_RE.match(c.text.strip())]
    return sorted(found, key=lambda c: c.x_mid)


def _looks_like_header_row(cells: list[_Cell]) -> list[str] | None:
    """열 헤더 라벨. 같은 y의 다른 단 텍스트가 섞여도 헤더 셀만 인정."""
    headers = _header_cells(cells)
    if len(headers) >= _MIN_TEXT_LANES:
        return [c.text.strip() for c in headers]
    return None


def _score_hit(
    *,
    n_rows: int,
    n_lanes: int,
    headers: list[str],
    markers: list[str],
    lane_coverage: float,
    y_gap_cv: float,
) -> float:
    score = 0.0
    if markers == list(_CHOICE_MARKERS[:n_rows]) and n_rows >= _MIN_CHOICE_ROWS:
        score += 0.35
    if n_rows == 5 and markers == list(_CHOICE_MARKERS):
        score += 0.15
    if n_lanes >= _MIN_TEXT_LANES:
        score += 0.2
    if headers and len(headers) == n_lanes:
        score += 0.2
    elif headers:
        score += 0.08
    score += 0.15 * min(1.0, lane_coverage)
    if y_gap_cv <= 0.35:
        score += 0.1
    elif y_gap_cv <= 0.55:
        score += 0.05
    return min(1.0, score)


def detect_parallel_choices(
    spans: list[PdfSpan],
    *,
    y_tol: float | None = None,
    x_gap_min: float | None = None,
    lane_tol: float | None = None,
) -> list[ParallelChoiceHit]:
    """span 기하에서 병렬 선택지 후보를 찾는다. 낮은 신뢰도는 버린다."""
    usable = [s for s in spans if (s.text or "").strip()]
    if len(usable) < 8:
        return []

    sizes = [s.font_size for s in usable if s.font_size > 0]
    med_size = (sum(sizes) / len(sizes)) if sizes else 10.0
    y_tolerance = y_tol if y_tol is not None else max(2.5, med_size * 0.55)
    gap_min = x_gap_min if x_gap_min is not None else max(10.0, med_size * 1.2)
    l_tol = lane_tol if lane_tol is not None else max(14.0, med_size * 2.2)

    row_groups = _cluster_by_y(usable, y_tol=y_tolerance)
    rows: list[_Row] = []
    for group in row_groups:
        cells = _cluster_row_cells(group, gap_min=gap_min)
        if not cells:
            continue
        ym = sum(_y_mid(s) for s in group) / len(group)
        rows.append(_Row(y_mid=ym, cells=cells, spans=list(group)))

    hits: list[ParallelChoiceHit] = []
    i = 0
    while i < len(rows):
        parsed = _parse_choice_row(rows[i].cells)
        if parsed is None:
            i += 1
            continue

        # 연속 선택지 행 수집
        choice_rows: list[tuple[_Row, str, list[_Cell]]] = []
        j = i
        expected = list(_CHOICE_MARKERS)
        while j < len(rows) and len(choice_rows) < 5:
            p = _parse_choice_row(rows[j].cells)
            if p is None:
                break
            marker, bodies = p
            want = expected[len(choice_rows)]
            if marker != want:
                break
            choice_rows.append((rows[j], marker, bodies))
            j += 1

        if len(choice_rows) < _MIN_CHOICE_ROWS:
            i += 1
            continue

        # 본문 셀 x_mid → lane
        x_vals: list[float] = []
        for _, _, bodies in choice_rows:
            x_vals.extend(c.x_mid for c in bodies)
        lanes = _cluster_lane_centers(x_vals, tol=l_tol)
        if len(lanes) < _MIN_TEXT_LANES:
            i = max(i + 1, j)
            continue
        # 상위 빈도 lane만 유지 (잡음 lane 제거)
        if len(lanes) > 4:
            lanes = lanes[:4]

        aligned: list[tuple[str, list[str]]] = []
        covered = 0
        all_spans: list[PdfSpan] = []
        for row, marker, bodies in choice_rows:
            assigned = _assign_to_lanes(bodies, lanes, tol=l_tol * 1.25)
            if assigned is None:
                break
            covered += sum(1 for t in assigned if t) / max(1, len(lanes))
            aligned.append((marker, assigned))
            # 다른 단 지문이 같은 y에 있어도 선택지 셀만 소비(bbox 오염 방지)
            for cell in bodies:
                all_spans.extend(cell.spans)
            for cell in row.cells:
                m, _ = _peel_marker(cell.text)
                if m is not None or cell.text.strip() in _CHOICE_SET:
                    all_spans.extend(cell.spans)

        if len(aligned) < _MIN_CHOICE_ROWS:
            i += 1
            continue

        # 헤더: 첫 선택지 바로 위 행 — 필수(페이지 2단 오탐 차단)
        headers: list[str] = []
        if i > 0:
            hdr_cells = _header_cells(rows[i - 1].cells)
            if len(hdr_cells) == len(lanes) and _headers_align_lanes(
                hdr_cells, lanes, tol=max(36.0, l_tol * 2.5)
            ):
                headers = [c.text.strip() for c in hdr_cells]
                for hc in hdr_cells:
                    all_spans.extend(hc.spans)

        if _REQUIRE_COLUMN_HEADERS and len(headers) != len(lanes):
            i += 1
            continue

        markers = [m for m, _ in aligned]
        lane_coverage = covered / len(aligned)
        ys = [r.y_mid for r, _, _ in choice_rows[: len(aligned)]]
        gaps = [ys[k + 1] - ys[k] for k in range(len(ys) - 1)]
        if gaps:
            mean_g = sum(gaps) / len(gaps)
            var = sum((g - mean_g) ** 2 for g in gaps) / len(gaps)
            y_gap_cv = (var**0.5) / mean_g if mean_g > 1e-6 else 1.0
        else:
            y_gap_cv = 1.0

        conf = _score_hit(
            n_rows=len(aligned),
            n_lanes=len(lanes),
            headers=headers,
            markers=markers,
            lane_coverage=lane_coverage,
            y_gap_cv=y_gap_cv,
        )
        if conf < _MIN_CONFIDENCE:
            i += 1
            continue

        uniq_spans = {s.id: s for s in all_spans}
        bbox = _union_bbox([s.bbox for s in uniq_spans.values()])
        hits.append(
            ParallelChoiceHit(
                headers=headers,
                rows=[(m, cols) for m, cols in aligned],
                span_ids=set(uniq_spans),
                bbox=bbox,
                confidence=conf,
            )
        )
        i = j

    return hits


def _headers_align_lanes(
    hdr_cells: list[_Cell],
    lanes: list[float],
    *,
    tol: float,
) -> bool:
    """헤더가 본문 lane에 1:1로 가깝게 대응하는지."""
    used: set[int] = set()
    for hc in hdr_cells:
        best_i: int | None = None
        best_d: float | None = None
        for i, lx in enumerate(lanes):
            if i in used:
                continue
            d = abs(hc.x_mid - lx)
            if best_d is None or d < best_d:
                best_d = d
                best_i = i
        if best_i is None or best_d is None or best_d > tol:
            return False
        used.add(best_i)
    return len(used) == len(lanes)


def format_parallel_choice_line(
    marker: str,
    columns: list[str],
    *,
    headers: list[str] | None = None,
) -> str:
    """``① ㉠ 주제… / ㉡ 경험…`` 또는 헤더 없이 ``① a / b``."""
    parts: list[str] = []
    for i, col in enumerate(columns):
        if not col:
            continue
        if headers and i < len(headers) and headers[i]:
            parts.append(f"{headers[i]} {col}")
        else:
            parts.append(col)
    return f"{marker} {_CELL_SEP.join(parts)}".strip()


def apply_parallel_choices(
    lines: list[PdfLine],
    hits: list[ParallelChoiceHit],
    *,
    page_number: int,
) -> list[PdfLine]:
    """적중 span을 포함한 기존 줄을 제거하고 재조합 줄로 대체."""
    if not hits:
        return lines

    consumed: set[str] = set()
    for hit in hits:
        consumed |= hit.span_ids

    kept: list[PdfLine] = []
    for ln in lines:
        if any(sid in consumed for sid in ln.span_ids):
            continue
        # span_ids가 비어 있어도 bbox가 구역과 크게 겹치면 제거
        skip = False
        for hit in hits:
            hx0, hy0, hx1, hy1 = hit.bbox
            lx0, ly0, lx1, ly1 = ln.bbox
            overlap_y = min(hy1, ly1) - max(hy0, ly0)
            overlap_x = min(hx1, lx1) - max(hx0, lx0)
            if overlap_y > 2 and overlap_x > 2:
                # 줄 높이의 절반 이상 겹치면 재작성 구역으로 간주
                if overlap_y >= 0.5 * max(1.0, ly1 - ly0):
                    skip = True
                    break
        if not skip:
            kept.append(ln)

    new_lines: list[PdfLine] = []
    for hit_i, hit in enumerate(hits):
        y0 = hit.bbox[1]
        # 헤더만 별도 줄 (선택지가 아닌 안내) — 블록 시작표에 안 걸리게 둔다
        if hit.headers:
            text = _CELL_SEP.join(hit.headers)
            new_lines.append(
                PdfLine(
                    id=f"p{page_number}-pc{hit_i}-hdr",
                    text=text,
                    bbox=(hit.bbox[0], y0 - 1.0, hit.bbox[2], y0 + 1.0),
                    span_ids=[],
                    page_number=page_number,
                    reading_order=0,
                )
            )
        row_h = max(12.0, (hit.bbox[3] - hit.bbox[1]) / max(1, len(hit.rows)))
        for r_i, (marker, cols) in enumerate(hit.rows):
            text = format_parallel_choice_line(
                marker, cols, headers=hit.headers or None
            )
            top = y0 + r_i * row_h
            new_lines.append(
                PdfLine(
                    id=f"p{page_number}-pc{hit_i}-r{r_i}",
                    text=text,
                    bbox=(hit.bbox[0], top, hit.bbox[2], top + row_h * 0.9),
                    span_ids=[],
                    page_number=page_number,
                    reading_order=0,
                )
            )

    merged = kept + new_lines
    merged.sort(key=lambda ln: (ln.bbox[1], ln.bbox[0], ln.id))
    for order, ln in enumerate(merged):
        ln.reading_order = order
    return merged


def promote_parallel_choices_in_lines(
    spans: list[PdfSpan],
    lines: list[PdfLine],
    *,
    page_number: int,
) -> list[PdfLine]:
    """감지 → 적용 한 번에. 미검출 시 lines 그대로."""
    hits = detect_parallel_choices(spans)
    if not hits:
        return lines
    return apply_parallel_choices(lines, hits, page_number=page_number)
