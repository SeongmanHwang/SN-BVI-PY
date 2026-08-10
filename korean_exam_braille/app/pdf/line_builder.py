"""span을 열(column) 인식 후 시각적 행(line)으로 묶는다."""

from __future__ import annotations

from korean_exam_braille.app.pdf.emphasis import annotate_text_with_underline_ranges
from korean_exam_braille.app.pdf.layout_profile import PageLayoutProfile
from korean_exam_braille.app.pdf.models import BBox, PdfLine, PdfSpan


def _union_bbox(boxes: list[BBox]) -> BBox:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def detect_column_boundary(spans: list[PdfSpan], page_width: float | None = None) -> float | None:
    """단일 면 기준 2단 경계 추정(프로필이 없을 때 폴백)."""
    if len(spans) < 8:
        return None
    width = page_width or max(s.bbox[2] for s in spans)
    mids = sorted((s.bbox[0] + s.bbox[2]) / 2 for s in spans)

    best_gap = 0.0
    best_cut: float | None = None
    for a, b in zip(mids, mids[1:]):
        gap = b - a
        cut = (a + b) / 2
        if cut < width * 0.28 or cut > width * 0.72:
            continue
        if gap > best_gap:
            best_gap = gap
            best_cut = cut

    min_gap = max(28.0, width * 0.045)
    if best_cut is not None and best_gap >= min_gap:
        return best_cut
    return None


def _assign_columns(
    spans: list[PdfSpan],
    cut: float | None,
    profile: PageLayoutProfile | None = None,
) -> list[tuple[int, PdfSpan]]:
    """열 번호: -2=헤더, -1=전폭, 0=좌, 1=우, 2=푸터."""
    if cut is None and profile is None:
        return [(0, s) for s in spans]

    out: list[tuple[int, PdfSpan]] = []
    for s in spans:
        y_mid = (s.bbox[1] + s.bbox[3]) / 2
        mid = (s.bbox[0] + s.bbox[2]) / 2
        span_w = s.bbox[2] - s.bbox[0]

        if profile is not None:
            band = profile.band_of_y(s.bbox[1])
            if band == "header":
                out.append((-2, s))
                continue
            if band == "footer":
                out.append((2, s))
                continue
            col = profile.column_of_x(mid, span_width=span_w)
            out.append((col, s))
            continue

        page_w = max(sp.bbox[2] for sp in spans)
        assert cut is not None
        if span_w > page_w * 0.50 and s.bbox[0] < cut < s.bbox[2]:
            out.append((-1, s))
        elif mid < cut:
            out.append((0, s))
        else:
            out.append((1, s))
    return out


def _y_mid(span: PdfSpan) -> float:
    return (span.bbox[1] + span.bbox[3]) / 2


def _cluster_spans_by_y(
    spans: list[PdfSpan],
    *,
    y_tolerance: float,
) -> list[list[PdfSpan]]:
    """같은 시각 행의 span을 y_mid 근접으로 묶는다.

    열 분리는 호출 전에 끝난 상태라, 가로 gap으로 줄을 쪼개지 않는다.
    (글자 크기만 다른 인라인 span이 가로로 떨어져도 한 줄로 유지)

    정렬 키는 ``bbox[1]``(y0)이 아니라 ``y_mid`` — 크기·베이스라인 차로
    y0만 어긋난 강조 span이 줄 앞으로 끼어들지 않게 한다.
    """
    if not spans:
        return []
    ordered = sorted(spans, key=lambda s: (_y_mid(s), s.bbox[0], s.extraction_index))
    groups: list[list[PdfSpan]] = []
    current: list[PdfSpan] = []
    current_y: float | None = None

    for span in ordered:
        ym = _y_mid(span)
        if current_y is None or abs(ym - current_y) <= y_tolerance:
            current.append(span)
            current_y = sum(_y_mid(s) for s in current) / len(current)
        else:
            groups.append(current)
            current = [span]
            current_y = ym
    if current:
        groups.append(current)
    return groups


def _join_line_text(group_sorted: list[PdfSpan]) -> str:
    """행 span을 좌→우로 이어 붙인다. 부분 밑줄 마커를 보존한다."""
    raw = "".join(
        annotate_text_with_underline_ranges(s.text, s.underline_ranges)
        for s in group_sorted
    )
    return " ".join(raw.split()) if raw.strip() else raw


def _group_spans_into_lines(
    spans: list[PdfSpan],
    page_number: int,
    column_index: int,
    *,
    y_tolerance: float,
    start_index: int,
) -> list[PdfLine]:
    if not spans:
        return []
    groups = _cluster_spans_by_y(spans, y_tolerance=y_tolerance)

    label = {-2: "h", -1: "f", 0: "0", 1: "1", 2: "t"}.get(column_index, str(column_index))
    lines: list[PdfLine] = []
    for i, group in enumerate(groups):
        group_sorted = sorted(group, key=lambda s: (s.bbox[0], s.extraction_index))
        text = _join_line_text(group_sorted)
        bbox = _union_bbox([s.bbox for s in group_sorted])
        lines.append(
            PdfLine(
                id=f"p{page_number}-c{label}-l{start_index + i}",
                text=text,
                bbox=bbox,
                span_ids=[s.id for s in group_sorted],
                page_number=page_number,
                reading_order=start_index + i,
            )
        )
    return lines


def build_lines(
    spans: list[PdfSpan],
    page_number: int,
    *,
    y_tolerance: float | None = None,
    page_width: float | None = None,
    profile: PageLayoutProfile | None = None,
) -> list[PdfLine]:
    """열을 나눈 뒤, 열 안에서 y가 가까운 span을 행으로 묶는다."""
    if not spans:
        return []

    sizes = [s.font_size for s in spans if s.font_size > 0]
    tol = y_tolerance if y_tolerance is not None else max(
        2.0, (sum(sizes) / len(sizes)) * 0.45 if sizes else 3.0
    )
    width = (
        profile.page_width
        if profile is not None
        else (page_width or max(s.bbox[2] for s in spans))
    )
    cut = profile.column_cut_x if profile is not None else detect_column_boundary(spans, width)
    assigned = _assign_columns(spans, cut, profile)

    by_col: dict[int, list[PdfSpan]] = {}
    for col, span in assigned:
        by_col.setdefault(col, []).append(span)

    lines: list[PdfLine] = []
    order = 0
    # 헤더 → 전폭 → 좌 → 우 → 푸터
    for col in sorted(by_col):
        col_lines = _group_spans_into_lines(
            by_col[col],
            page_number,
            col,
            y_tolerance=tol,
            start_index=order,
        )
        lines.extend(col_lines)
        order += len(col_lines)

    for i, line in enumerate(lines):
        line.reading_order = i
    return lines
