"""PDF 드로잉에서 보기·표·빈칸 등 사각형(박스) 경계 추출.

실측(수능 토의 제시문 등):
- ``[가]`` 빈칸 박스는 네 변이 각각 ``line`` 으로 존재하며 높이 ~14pt
- 같은 선이 ``get_drawings()``에 거의 동일 좌표로 중복될 수 있음 → 0.5pt 병합
- 큰 제시문 박스의 좌우는 짧은 세로선이 이어진 형태, 하단은 긴 수평선 하나
"""

from __future__ import annotations

from typing import Any

from korean_exam_braille.app.pdf.models import BBox

# 거의 수평/수직 판정
_MAX_AXIS_DY = 1.5
_MAX_AXIS_DX = 1.5
# 큰 보기·표 박스
_MIN_BOX_W = 40.0
_MIN_BOX_H = 28.0
# [가] 빈칸처럼 네 변이 닫힌 낮은 박스
_MIN_SMALL_BOX_W = 40.0
_MIN_SMALL_BOX_H = 10.0
# 선분 끝점 접합 허용 오차
_JOIN_TOL = 3.0
# 동일 선 중복 제거 (실측: 좌표 차 < 0.5pt)
_DEDUP_TOL = 0.5
# 짧은 세로/가로 조각 이어 붙이기
_MERGE_GAP = 2.5
# 제시문 하단 등으로 쓸 긴 수평선
_MIN_RULE_W = 120.0


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


def _collect_raw_axis_segments(
    page: Any,
) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    """수평 선 (x0,x1,y), 수직 선 (y0,y1,x). 짧은 조각도 포함."""
    horiz: list[tuple[float, float, float]] = []
    vert: list[tuple[float, float, float]] = []
    for drawing in page.get_drawings() or []:
        for item in drawing.get("items") or []:
            if not item:
                continue
            if _rect_from_item(item) is not None:
                continue
            if item[0] != "l" or len(item) < 3:
                continue
            p1, p2 = item[1], item[2]
            x_a, y_a = float(p1.x), float(p1.y)
            x_b, y_b = float(p2.x), float(p2.y)
            if abs(y_a - y_b) <= _MAX_AXIS_DY:
                x0, x1 = min(x_a, x_b), max(x_a, x_b)
                if x1 - x0 >= 4.0:
                    horiz.append((x0, x1, (y_a + y_b) / 2.0))
            elif abs(x_a - x_b) <= _MAX_AXIS_DX:
                y0, y1 = min(y_a, y_b), max(y_a, y_b)
                if y1 - y0 >= 4.0:
                    vert.append((y0, y1, (x_a + x_b) / 2.0))
    return horiz, vert


def _dedupe_segments(
    segs: list[tuple[float, float, float]],
    *,
    tol: float = _DEDUP_TOL,
) -> list[tuple[float, float, float]]:
    """같은 방향·좌표·길이의 중복 선 병합."""
    kept: list[tuple[float, float, float]] = []
    for a0, a1, ap in sorted(segs, key=lambda s: (s[2], s[0], s[1])):
        length = a1 - a0
        if any(
            abs(ap - bp) <= tol
            and abs(a0 - b0) <= tol
            and abs(length - (b1 - b0)) <= tol
            for b0, b1, bp in kept
        ):
            continue
        kept.append((a0, a1, ap))
    return kept


def _merge_collinear(
    segs: list[tuple[float, float, float]],
    *,
    axis_tol: float = _DEDUP_TOL,
    gap: float = _MERGE_GAP,
) -> list[tuple[float, float, float]]:
    """동일 축(좌표 ap) 위에서 간격이 작으면 한 선으로 이어 붙인다."""
    if not segs:
        return []
    by_axis: dict[float, list[tuple[float, float]]] = {}
    for a0, a1, ap in segs:
        key = None
        for existing in by_axis:
            if abs(existing - ap) <= axis_tol:
                key = existing
                break
        if key is None:
            key = ap
            by_axis[key] = []
        by_axis[key].append((a0, a1))

    out: list[tuple[float, float, float]] = []
    for ap, parts in by_axis.items():
        parts = sorted(parts)
        cur0, cur1 = parts[0]
        for a0, a1 in parts[1:]:
            if a0 <= cur1 + gap:
                cur1 = max(cur1, a1)
            else:
                out.append((cur0, cur1, ap))
                cur0, cur1 = a0, a1
        out.append((cur0, cur1, ap))
    return out


def _collect_axis_segments(
    page: Any,
) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    horiz, vert = _collect_raw_axis_segments(page)
    horiz = _merge_collinear(_dedupe_segments(horiz))
    vert = _merge_collinear(_dedupe_segments(vert))
    return horiz, vert


def _rects_from_re_items(page: Any) -> list[BBox]:
    out: list[BBox] = []
    for drawing in page.get_drawings() or []:
        for item in drawing.get("items") or []:
            rect = _rect_from_item(item if item else ())
            if rect is None:
                continue
            x0, y0, x1, y1 = rect
            if x1 - x0 >= _MIN_BOX_W and y1 - y0 >= _MIN_SMALL_BOX_H:
                out.append((x0, y0, x1, y1))
    return out


def _nearly(a: float, b: float, tol: float = _JOIN_TOL) -> bool:
    return abs(a - b) <= tol


def _frame_from_edges(
    top: tuple[float, float, float],
    bottom: tuple[float, float, float],
    left: tuple[float, float, float],
    right: tuple[float, float, float],
    *,
    min_w: float,
    min_h: float,
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
    if x1 - x0 < min_w or y1 - y0 < min_h:
        return None
    return (x0, y0, x1, y1)


def _rects_from_axis_frames(
    horiz: list[tuple[float, float, float]],
    vert: list[tuple[float, float, float]],
) -> list[BBox]:
    """수평·수직 선으로 닫힌 프레임 조합.

    - 큰 박스: 긴 수평 + (병합된) 긴 수직
    - 낮은 빈칸 박스: 짧은 수직도 허용, 최소 높이 ``_MIN_SMALL_BOX_H``
    """
    long_h = [h for h in horiz if h[1] - h[0] >= _MIN_BOX_W * 0.85]
    long_v = [v for v in vert if v[1] - v[0] >= _MIN_BOX_H * 0.85]
    # 낮은 박스용: 폭만 충분하면 짧은 세로도 후보
    short_ok_v = [v for v in vert if v[1] - v[0] >= _MIN_SMALL_BOX_H * 0.8]

    out: list[BBox] = []

    def _pair_frames(
        h_cands: list[tuple[float, float, float]],
        v_cands: list[tuple[float, float, float]],
        *,
        min_w: float,
        min_h: float,
    ) -> None:
        for i, top in enumerate(h_cands):
            for bottom in h_cands[i + 1 :]:
                if bottom[2] <= top[2]:
                    continue
                if abs((top[1] - top[0]) - (bottom[1] - bottom[0])) > 12.0:
                    continue
                if abs(top[0] - bottom[0]) > 10.0 or abs(top[1] - bottom[1]) > 10.0:
                    continue
                height = bottom[2] - top[2]
                if height < min_h * 0.85:
                    continue
                for left in v_cands:
                    for right in v_cands:
                        if right[2] <= left[2]:
                            continue
                        framed = _frame_from_edges(
                            top, bottom, left, right, min_w=min_w, min_h=min_h
                        )
                        if framed is not None:
                            out.append(framed)

    _pair_frames(long_h, long_v, min_w=_MIN_BOX_W, min_h=_MIN_BOX_H)
    _pair_frames(long_h, short_ok_v, min_w=_MIN_SMALL_BOX_W, min_h=_MIN_SMALL_BOX_H)
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
    return sorted(kept, key=lambda b: (b[1], b[0], -(b[2] - b[0]) * (b[3] - b[1])))


def iter_box_rects(page: Any) -> list[BBox]:
    """페이지에서 보기·표·빈칸 등 사각 프레임 bbox 목록."""
    from_re = _rects_from_re_items(page)
    horiz, vert = _collect_axis_segments(page)
    from_frames = _rects_from_axis_frames(horiz, vert)
    return _dedupe_rects(from_re + from_frames)


def iter_long_horizontal_rules(
    page: Any,
    *,
    min_width: float = _MIN_RULE_W,
) -> list[tuple[float, float, float]]:
    """긴 수평 벡터 선 (x0, x1, y).

    제시문 박스 하단처럼 텍스트 y만으로 추정하지 않고 시각적으로
    구간 종료를 확정할 때 쓴다.
    """
    horiz, _vert = _collect_axis_segments(page)
    rules = [h for h in horiz if h[1] - h[0] >= min_width]
    return sorted(rules, key=lambda h: (h[2], h[0]))


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
