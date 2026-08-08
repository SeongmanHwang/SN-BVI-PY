"""PDF 래스터 그림 영역 검출 — 존재 사실만 표시용으로 승격한다."""

from __future__ import annotations

from typing import Any

from korean_exam_braille.app.common.figure_markup import FIGURE_INK
from korean_exam_braille.app.pdf.models import BBox, PdfFigure, PdfLine

# 아이콘·장식 조각을 걸러 내기 위한 최소 크기(병합 후 기준)
_MIN_W = 36.0
_MIN_H = 24.0
_MIN_AREA = 1500.0
# 잘린 스트립 한 장은 아주 낮을 수 있음 → 병합 전에만 완화
_STRIP_MIN_H = 8.0
_STRIP_MIN_AREA = 400.0
# 가로로 잘린 조각을 한 그림으로 묶을 때
_X_ALIGN_TOL = 4.0
_Y_GAP_TOL = 8.0


def _union(a: BBox, b: BBox) -> BBox:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _x_aligned(a: BBox, b: BBox) -> bool:
    return abs(a[0] - b[0]) <= _X_ALIGN_TOL and abs(a[2] - b[2]) <= _X_ALIGN_TOL


def _vertically_adjacent(a: BBox, b: BBox) -> bool:
    upper, lower = (a, b) if a[1] <= b[1] else (b, a)
    gap = lower[1] - upper[3]
    return -_Y_GAP_TOL <= gap <= _Y_GAP_TOL


def _merge_image_boxes(boxes: list[BBox]) -> list[tuple[BBox, int]]:
    """세로로 이어 붙인 이미지 조각을 (병합 bbox, 조각 수)로 묶는다."""
    if not boxes:
        return []
    remaining = sorted(boxes, key=lambda b: (b[1], b[0]))
    groups: list[tuple[BBox, int]] = []
    while remaining:
        current = remaining.pop(0)
        count = 1
        changed = True
        while changed:
            changed = False
            nxt: list[BBox] = []
            for box in remaining:
                if _x_aligned(current, box) and _vertically_adjacent(current, box):
                    current = _union(current, box)
                    count += 1
                    changed = True
                else:
                    nxt.append(box)
            remaining = nxt
        groups.append((current, count))
    return groups


def _raw_image_boxes(page: Any) -> list[BBox]:
    page_width = float(getattr(getattr(page, "rect", None), "width", 0) or 0)
    page_height = float(getattr(getattr(page, "rect", None), "height", 0) or 0)
    infos: list[dict[str, Any]]
    try:
        infos = list(page.get_image_info(xrefs=True) or [])
    except Exception:
        infos = []

    boxes: list[BBox] = []
    for info in infos:
        raw = info.get("bbox")
        if not raw or len(raw) < 4:
            continue
        x0, y0, x1, y1 = (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))
        width, height = x1 - x0, y1 - y0
        # 스트립 조각은 높이가 낮아도 모은 뒤, 병합 결과로 크기를 판정한다.
        if width < _MIN_W or height < _STRIP_MIN_H or width * height < _STRIP_MIN_AREA:
            continue
        if (
            page_width > 0
            and page_height > 0
            and width >= page_width * 0.85
            and height >= page_height * 0.85
        ):
            continue
        boxes.append((x0, y0, x1, y1))
    return boxes


def detect_raster_figures(page: Any) -> list[PdfFigure]:
    """임베드 래스터 이미지를 그림 후보로 모은다(내용 추출 없음)."""
    merged = _merge_image_boxes(_raw_image_boxes(page))
    figures = [
        PdfFigure(bbox=bbox, piece_count=count, confidence=0.9)
        for bbox, count in merged
        if (bbox[2] - bbox[0]) >= _MIN_W
        and (bbox[3] - bbox[1]) >= _MIN_H
        and (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) >= _MIN_AREA
    ]
    return sorted(figures, key=lambda fig: (fig.bbox[1], fig.bbox[0]))


def promote_figures_into_lines(
    lines: list[PdfLine],
    figures: list[PdfFigure],
    *,
    page_number: int,
) -> list[PdfLine]:
    """읽기 순서에 ``[그림]`` 자리표시 행을 끼운다."""
    if not figures:
        return lines
    promoted: list[PdfLine] = []
    for index, figure in enumerate(figures):
        overlap_tops = [
            line.bbox[1]
            for line in lines
            if line.bbox[3] >= figure.bbox[1] - 1.0
            and line.bbox[1] <= figure.bbox[3] + 1.0
        ]
        # 옆에 본문이 있으면 그 블록보다 앞에 두어 읽기 순서를 안정화한다.
        y0 = min([figure.bbox[1]] + overlap_tops) - 0.5
        promoted.append(
            PdfLine(
                id=f"p{page_number}-figure{index}",
                text=FIGURE_INK,
                bbox=(figure.bbox[0], y0, figure.bbox[2], y0 + 1.0),
                span_ids=[],
                page_number=page_number,
                reading_order=0,
            )
        )
    merged = list(lines) + promoted
    merged.sort(
        key=lambda line: (
            line.bbox[1],
            0 if line.text == FIGURE_INK else 1,
            line.bbox[0],
            line.id,
        )
    )
    for index, line in enumerate(merged):
        line.reading_order = index
    return merged
