"""시각 강조(밑줄 등) 감지 — 드로잉 ∩ 글자 bbox → 구간 오프셋."""

from __future__ import annotations

from typing import Any

from korean_exam_braille.app.pdf.models import BBox, PdfSpan
from korean_exam_braille.app.pdf.boxes import iter_box_rects

UnderlineRange = tuple[int, int]  # [start, end) 문자 오프셋
UnderlineSegment = tuple[float, float, float]  # (x0, x1, y)
UnderlineMatch = int | None  # segments 목록의 인덱스


def iter_horizontal_underline_segments(
    page: Any,
    *,
    max_dy: float = 1.5,
    min_width: float = 8.0,
    max_width_ratio: float = 0.42,
) -> list[tuple[float, float, float]]:
    """페이지 드로잉에서 밑줄 후보인 거의 수평 선분 (x0, x1, y).

    열 구분선·박스 가로줄(페이지 폭에 가까운 긴 선)은 제외하고,
    단어·구 길이의 짧은 선만 남긴다.
    """
    page_width = float(getattr(getattr(page, "rect", None), "width", 0) or 0)
    max_width = page_width * max_width_ratio if page_width > 0 else 180.0
    boxes = iter_box_rects(page)
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
            width = x1 - x0
            if width < min_width or width > max_width:
                continue
            # 닫힌 박스의 위·아랫변은 글자 가까이에 있어도 밑줄이 아니다.
            # [가] 빈칸 박스와 제시문 외곽 하단이 대표적인 오인 사례다.
            sy = (y1 + y2) / 2.0
            if any(
                abs(x0 - bx0) <= 3.0
                and abs(x1 - bx1) <= 3.0
                and (abs(sy - by0) <= 2.0 or abs(sy - by1) <= 2.0)
                for bx0, by0, bx1, by1 in boxes
            ):
                continue
            segs.append((x0, x1, sy))
    return segs


def bbox_has_underline(
    bbox: BBox,
    segments: list[UnderlineSegment],
    *,
    y_pad_below: float = 4.0,
    min_x_overlap_ratio: float = 0.35,
) -> bool:
    """텍스트 bbox 하단 근처를 가로지르는 수평선이 있으면 True."""
    x0, y0, x1, y1 = bbox
    width = max(x1 - x0, 1.0)
    height = max(y1 - y0, 1.0)
    y_lo = y0 + height * 0.45
    y_hi = y1 + y_pad_below
    for sx0, sx1, sy in segments:
        if sy < y_lo or sy > y_hi:
            continue
        overlap = min(x1, sx1) - max(x0, sx0)
        if overlap >= width * min_x_overlap_ratio:
            return True
    return False


def char_is_underlined(
    char_bbox: BBox,
    segments: list[UnderlineSegment],
    *,
    y_pad_below: float = 5.0,
    min_x_overlap_ratio: float = 0.35,
) -> bool:
    """한 글자 bbox가 밑줄 선분과 의미 있게 겹치면 True.

    부분 밑줄은 span 전체 비율이 아니라 글자 폭 기준으로 판정한다.
    """
    return char_underline_match(
        char_bbox,
        segments,
        y_pad_below=y_pad_below,
        min_x_overlap_ratio=min_x_overlap_ratio,
    ) is not None


def char_underline_match(
    char_bbox: BBox,
    segments: list[UnderlineSegment],
    *,
    y_pad_below: float = 5.0,
    min_x_overlap_ratio: float = 0.35,
) -> UnderlineMatch:
    """한 글자와 가장 잘 겹치는 밑줄 선분의 인덱스를 반환한다.

    인접한 두 글자가 각각 다른 짧은 선분과 겹치면 서로 다른 ID를
    유지한다. 하나의 긴 선분이 여러 글자를 관통하면 같은 ID가 된다.
    """
    x0, y0, x1, y1 = char_bbox
    width = max(x1 - x0, 1.0)
    height = max(y1 - y0, 1.0)
    y_lo = y0 + height * 0.45
    y_hi = y1 + y_pad_below
    best_id: UnderlineMatch = None
    best_overlap = 0.0
    for segment_id, (sx0, sx1, sy) in enumerate(segments):
        if sy < y_lo or sy > y_hi:
            continue
        overlap = min(x1, sx1) - max(x0, sx0)
        if overlap < width * min_x_overlap_ratio:
            continue
        if overlap > best_overlap:
            best_id = segment_id
            best_overlap = overlap
    return best_id


def merge_underline_flags(flags: list[bool]) -> list[UnderlineRange]:
    """글자별 밑줄 플래그 → [start, end) 연속 구간."""
    ranges: list[UnderlineRange] = []
    n = len(flags)
    i = 0
    while i < n:
        if not flags[i]:
            i += 1
            continue
        j = i + 1
        while j < n and flags[j]:
            j += 1
        ranges.append((i, j))
        i = j
    return ranges


def merge_underline_matches(matches: list[UnderlineMatch]) -> list[UnderlineRange]:
    """글자별 밑줄 선분 ID → 같은 선분별 연속 구간.

    ``[17, 18]``은 ``[(0, 1), (1, 2)]``로 분리하고,
    ``[17, 17]``은 ``[(0, 2)]``로 병합한다.
    """
    ranges: list[UnderlineRange] = []
    i = 0
    while i < len(matches):
        segment_id = matches[i]
        if segment_id is None:
            i += 1
            continue
        j = i + 1
        while j < len(matches) and matches[j] == segment_id:
            j += 1
        ranges.append((i, j))
        i = j
    return ranges


def annotate_text_with_underline_ranges(
    text: str,
    ranges: list[UnderlineRange],
    *,
    open_mark: str = "<u>",
    close_mark: str = "</u>",
) -> str:
    """밑줄 구간에 표시용 마커를 삽입 (끝에서부터)."""
    if not text or not ranges:
        return text
    out = text
    for start, end in sorted(ranges, key=lambda r: r[0], reverse=True):
        start = max(0, min(start, len(out)))
        end = max(start, min(end, len(out)))
        if start >= end:
            continue
        out = out[:start] + open_mark + out[start:end] + close_mark + out[end:]
    return out


def mark_underlined_spans(page: Any, spans: list[PdfSpan]) -> list[PdfSpan]:
    """드로잉 밑줄과 교차하는 span/글자 구간을 표시 (제자리).

    - ``char_bboxes``가 있으면 부분 밑줄을 ``underline_ranges``로 기록
    - 글자 정보가 없으면 span bbox 전체 교차로 ``is_underline``만 설정
    """
    if not spans:
        return spans
    segs = iter_horizontal_underline_segments(page)
    if not segs:
        return spans
    for span in spans:
        if span.char_bboxes and len(span.char_bboxes) == len(span.text):
            matches = [char_underline_match(bb, segs) for bb in span.char_bboxes]
            ranges = merge_underline_matches(matches)
            span.underline_ranges = ranges
            span.is_underline = bool(ranges)
        elif bbox_has_underline(span.bbox, segs):
            span.is_underline = True
            span.underline_ranges = [(0, len(span.text))] if span.text else []
    return spans
