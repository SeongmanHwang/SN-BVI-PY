"""PDF 드로잉에서 보기·표 등 사각형(박스) 경계 추출."""

from __future__ import annotations

from typing import Any

from korean_exam_braille.app.pdf.models import BBox

# 거의 수평/수직 판정
_MAX_AXIS_DY = 1.5
_MAX_AXIS_DX = 1.5
# 박스 최소 크기 (너무 작은 장식·밑줄 오인 방지)
_MIN_BOX_W = 40.0
_MIN_BOX_H = 28.0
# 선분 끝점 접합 허용 오차
_JOIN_TOL = 3.0


def _rect_from_item(item: tuple[Any, ...]) -> BBox | None:
    """드로잉 item이 사각형이면 bbox."""
    if not item:
        return None
    kind = item[0]
    if kind == "re" and len(item) >= 2:
        r = item[1]
        try:
            return (float(r.x0), float(r.y0), float(r.x1), float(r.y1))
        except AttributeError:
            return None
    return None


def _collect_axis_segments(
    page: Any,
) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    """수평 선 (x0,x1,y), 수직 선 (y0,y1,x)."""
    horiz: list[tuple[float, float, float]] = []
    vert: list[tuple[float, float, float]] = []
    for drawing in page.get_drawings() or []:
        for item in drawing.get("items") or []:
            if not item:
                continue
            rect = _rect_from_item(item)
            if rect is not None:
                x0, y0, x1, y1 = rect
                if x1 - x0 >= _MIN_BOX_W and y1 - y0 >= _MIN_BOX_H:
                    # re 자체는 아래에서 박스로 쓰므로 선분만 모음은 스킵 가능
                    pass
                continue
            if item[0] != "l" or len(item) < 3:
                continue
            p1, p2 = item[1], item[2]
            x_a, y_a = float(p1.x), float(p1.y)
            x_b, y_b = float(p2.x), float(p2.y)
            if abs(y_a - y_b) <= _MAX_AXIS_DY:
                x0, x1 = min(x_a, x_b), max(x_a, x_b)
                if x1 - x0 >= 8.0:
                    horiz.append((x0, x1, (y_a + y_b) / 2.0))
            elif abs(x_a - x_b) <= _MAX_AXIS_DX:
                y0, y1 = min(y_a, y_b), max(y_a, y_b)
                if y1 - y0 >= 8.0:
                    vert.append((y0, y1, (x_a + x_b) / 2.0))
    return horiz, vert


def _rects_from_re_items(page: Any) -> list[BBox]:
    out: list[BBox] = []
    for drawing in page.get_drawings() or []:
        for item in drawing.get("items") or []:
            rect = _rect_from_item(item if item else ())
            if rect is None:
                continue
            x0, y0, x1, y1 = rect
            if x1 - x0 >= _MIN_BOX_W and y1 - y0 >= _MIN_BOX_H:
                out.append((x0, y0, x1, y1))
    return out


def _nearly(a: float, b: float, tol: float = _JOIN_TOL) -> bool:
    return abs(a - b) <= tol


def _frame_from_edges(
    top: tuple[float, float, float],
    bottom: tuple[float, float, float],
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> BBox | None:
    """네 변(가·세)이 맞물리면 박스."""
    tx0, tx1, ty = top
    bx0, bx1, by = bottom
    ly0, ly1, lx = left
    ry0, ry1, rx = right
    if by <= ty:
        return None
    if not (
        _nearly(tx0, bx0)
        and _nearly(tx1, bx1)
        and _nearly(lx, tx0)
        and _nearly(rx, tx1)
        and _nearly(ly0, ty)
        and _nearly(ry0, ty)
        and _nearly(ly1, by)
        and _nearly(ry1, by)
    ):
        # 느슨한 접합: 수평 끝과 수직 x가 가깝고, 수직 끝이 수평 y에 가까우면 OK
        if not (
            _nearly(lx, min(tx0, bx0), _JOIN_TOL * 2)
            and _nearly(rx, max(tx1, bx1), _JOIN_TOL * 2)
            and _nearly(ly0, ty, _JOIN_TOL * 2)
            and _nearly(ry0, ty, _JOIN_TOL * 2)
            and _nearly(ly1, by, _JOIN_TOL * 2)
            and _nearly(ry1, by, _JOIN_TOL * 2)
        ):
            return None
    x0 = min(tx0, bx0, lx, rx)
    x1 = max(tx1, bx1, lx, rx)
    y0 = min(ty, by, ly0, ry0)
    y1 = max(ty, by, ly1, ry1)
    if x1 - x0 < _MIN_BOX_W or y1 - y0 < _MIN_BOX_H:
        return None
    return (x0, y0, x1, y1)


def _rects_from_axis_frames(
    horiz: list[tuple[float, float, float]],
    vert: list[tuple[float, float, float]],
) -> list[BBox]:
    """긴 수평·수직 선으로 닫힌 프레임 조합."""
    # 밑줄(짧은 H) 제외: 박스 윗/아랫변은 상대적으로 김
    long_h = [h for h in horiz if h[1] - h[0] >= _MIN_BOX_W * 0.85]
    long_v = [v for v in vert if v[1] - v[0] >= _MIN_BOX_H * 0.85]
    out: list[BBox] = []
    for i, top in enumerate(long_h):
        for bottom in long_h[i + 1 :]:
            if bottom[2] <= top[2]:
                continue
            # 비슷한 폭·x 정렬
            if abs((top[1] - top[0]) - (bottom[1] - bottom[0])) > 12.0:
                continue
            if abs(top[0] - bottom[0]) > 10.0 or abs(top[1] - bottom[1]) > 10.0:
                continue
            for left in long_v:
                for right in long_v:
                    if right[2] <= left[2]:
                        continue
                    framed = _frame_from_edges(top, bottom, left, right)
                    if framed is not None:
                        out.append(framed)
    return out


def _dedupe_rects(rects: list[BBox], *, tol: float = 4.0) -> list[BBox]:
    kept: list[BBox] = []
    for r in sorted(rects, key=lambda b: ((b[2] - b[0]) * (b[3] - b[1]), b[1], b[0])):
        if any(
            abs(r[0] - k[0]) <= tol
            and abs(r[1] - k[1]) <= tol
            and abs(r[2] - k[2]) <= tol
            and abs(r[3] - k[3]) <= tol
            for k in kept
        ):
            continue
        kept.append(r)
    # 읽기 순: 위→아래, 큰 박스(외곽) 먼저 경계 삽입에 유리하도록 면적 내림차순은
    # insert 쪽에서 처리. 여기선 y,x 정렬.
    return sorted(kept, key=lambda b: (b[1], b[0], -(b[2] - b[0]) * (b[3] - b[1])))


def iter_box_rects(page: Any) -> list[BBox]:
    """페이지에서 보기·표 등 사각 프레임 bbox 목록."""
    from_re = _rects_from_re_items(page)
    horiz, vert = _collect_axis_segments(page)
    from_frames = _rects_from_axis_frames(horiz, vert)
    return _dedupe_rects(from_re + from_frames)


def point_in_bbox(x: float, y: float, box: BBox, *, pad: float = 1.0) -> bool:
    x0, y0, x1, y1 = box
    return (x0 - pad) <= x <= (x1 + pad) and (y0 - pad) <= y <= (y1 + pad)


def line_mostly_in_box(line_bbox: BBox, box: BBox, *, min_overlap: float = 0.55) -> bool:
    """행 bbox가 박스와 충분히 겹치면 True."""
    lx0, ly0, lx1, ly1 = line_bbox
    bx0, by0, bx1, by1 = box
    ox0, oy0 = max(lx0, bx0), max(ly0, by0)
    ox1, oy1 = min(lx1, bx1), min(ly1, by1)
    if ox1 <= ox0 or oy1 <= oy0:
        return False
    line_area = max((lx1 - lx0) * (ly1 - ly0), 1.0)
    return ((ox1 - ox0) * (oy1 - oy0)) / line_area >= min_overlap
