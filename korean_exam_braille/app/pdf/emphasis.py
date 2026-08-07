"""시각 강조(밑줄 등) 감지 — PyMuPDF 드로잉·span bbox 교차."""

from __future__ import annotations

from typing import Any

from korean_exam_braille.app.pdf.models import BBox, PdfSpan

# span flags에 underline 비트는 없음(실측). HTML/선 드로잉으로만 존재.


def iter_horizontal_underline_segments(
    page: Any,
    *,
    max_dy: float = 1.5,
) -> list[tuple[float, float, float]]:
    """페이지 드로잉에서 거의 수평인 선분 (x0, x1, y) 목록."""
    segs: list[tuple[float, float, float]] = []
    for drawing in page.get_drawings() or []:
        for item in drawing.get("items") or []:
            if not item or item[0] != "l":
                continue
            p1, p2 = item[1], item[2]
            y1, y2 = float(p1.y), float(p2.y)
            if abs(y1 - y2) > max_dy:
                continue
            x0 = float(min(p1.x, p2.x))
            x1 = float(max(p1.x, p2.x))
            if x1 - x0 < 2.0:
                continue
            segs.append((x0, x1, (y1 + y2) / 2.0))
    return segs


def bbox_has_underline(
    bbox: BBox,
    segments: list[tuple[float, float, float]],
    *,
    y_pad_below: float = 4.0,
    min_x_overlap_ratio: float = 0.35,
) -> bool:
    """텍스트 bbox 하단 근처를 가로지르는 수평선이 있으면 True."""
    x0, y0, x1, y1 = bbox
    width = max(x1 - x0, 1.0)
    height = max(y1 - y0, 1.0)
    # 밑줄은 보통 baseline~하단 바로 아래. 글자 상단 쪽 선은 제외.
    y_lo = y0 + height * 0.45
    y_hi = y1 + y_pad_below
    for sx0, sx1, sy in segments:
        if sy < y_lo or sy > y_hi:
            continue
        overlap = min(x1, sx1) - max(x0, sx0)
        if overlap >= width * min_x_overlap_ratio:
            return True
    return False


def mark_underlined_spans(page: Any, spans: list[PdfSpan]) -> list[PdfSpan]:
    """드로잉 밑줄과 교차하는 span의 is_underline을 True로 표시 (제자리)."""
    if not spans:
        return spans
    segs = iter_horizontal_underline_segments(page)
    if not segs:
        return spans
    for span in spans:
        if bbox_has_underline(span.bbox, segs):
            span.is_underline = True
    return spans
