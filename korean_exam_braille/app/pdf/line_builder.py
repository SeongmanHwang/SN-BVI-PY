"""span을 열(column) 인식 후 시각적 행(line)으로 묶는다."""

from __future__ import annotations

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
    ordered = sorted(spans, key=lambda s: (s.bbox[1], s.bbox[0], s.extraction_index))
    groups: list[list[PdfSpan]] = []
    current: list[PdfSpan] = []
    current_y: float | None = None

    for span in ordered:
        y_mid = (span.bbox[1] + span.bbox[3]) / 2
        if current_y is None or abs(y_mid - current_y) <= y_tolerance:
            if current:
                max_x1 = max(s.bbox[2] for s in current)
                if span.bbox[0] - max_x1 > max(28.0, y_tolerance * 6):
                    groups.append(current)
                    current = [span]
                    current_y = y_mid
                    continue
            current.append(span)
            ys = [(s.bbox[1] + s.bbox[3]) / 2 for s in current]
            current_y = sum(ys) / len(ys)
        else:
            groups.append(current)
            current = [span]
            current_y = y_mid
    if current:
        groups.append(current)

    label = {-2: "h", -1: "f", 0: "0", 1: "1", 2: "t"}.get(column_index, str(column_index))
    lines: list[PdfLine] = []
    for i, group in enumerate(groups):
        group_sorted = sorted(group, key=lambda s: (s.bbox[0], s.extraction_index))
        raw = "".join(s.text for s in group_sorted)
        text = " ".join(raw.split()) if raw.strip() else raw
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
