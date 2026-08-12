"""여백 [A]~[E] 꺾인 괄호(drawing) → 소속 행 구간 복원.

수능 문제지에서 구간 표지는 보통 이렇게 들어 있다::

    본문 행들 …        ┐          또는          ┌   … 본문 행들
                       │                       │
                       │  [A]                  │  [A]
                       │                       │
                       ┘                       └

가로·세로선은 각각 독립 ``line`` drawing 이고, OCR 없이 ``get_drawings()``
와 ``[A]`` 텍스트 좌표만으로 복원할 수 있다. 오른쪽 여백(왼쪽 방향 턱)과
왼쪽 여백(오른쪽 방향 턱)을 모두 인식한다.

페이지를 넘는 괄호는 한 면에서 위·아래 턱이 동시에 있지 않다.
시작 면(아래 열림)과 다음 면(위 열림)을 붙인 뒤 같은 라벨로 승격한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from korean_exam_braille.app.pdf.emphasis import merge_underline_flags
from korean_exam_braille.app.pdf.models import BBox, PdfBlock, PdfLine, PdfSpan

_LABEL_RE = re.compile(r"\[([A-E])\]")

# 거의 수직/수평
_MAX_AXIS_DX = 1.5
_MAX_AXIS_DY = 1.5
# 실측 10면의 왼쪽 [A]는 위·아래 줄기가 각각 약 11.75pt이다.
# 라벨+상하 턱을 모두 요구하므로 10pt까지 낮춰도 박스선 오검출은 제한된다.
_MIN_VERT_LEN = 10.0
# 짧은 가로 턱 — 박스 긴 변과 구분
_MIN_TICK = 4.0
_MAX_TICK = 28.0
# 라벨이 끼는 세로선 공백
_MIN_GAP = 6.0
_MAX_GAP = 36.0
_X_GROUP_TOL = 2.5
_JOIN_TOL = 2.5
_LABEL_X_PAD = 30.0
_LABEL_Y_PAD = 6.0
# 본문 행이 줄기 쪽으로 넘어가도 허용하는 여유
_LINE_STEM_PAD = 8.0
_LINE_OVERFLOW_PAD = 28.0
# 같은 단 본문만. 다른 열(300pt+)은 제외하고, 1단 오른쪽 여백 괄호(본문이 왼쪽)는 허용
_MAX_BODY_GAP = 140.0
# 페이지를 넘는 열린 괄호: 짧은 턱만 (박스 모서리 ~21pt 제외)
_MAX_OPEN_TICK = 16.0
_TOP_SLACK = 80.0
_BOTTOM_SLACK = 40.0
_INSET_TOL = 12.0
_LEFT_COL_ORIGIN = 88.0


@dataclass
class BracketGroup:
    """한 페이지의 [A] 등 꺾인 괄호 구간."""

    label: str  # "[A]"
    stem_x: float
    y0: float
    y1: float
    gap_y0: float
    gap_y1: float
    tick_x0: float  # 본문 쪽을 향한 턱 끝 x
    label_bbox: BBox
    # 본문이 줄기 기준 어느쪽인지: "left"(오른쪽 여백 괄호) / "right"(왼쪽 여백)
    body_side: str = "left"
    line_ids: list[str] = field(default_factory=list)
    # 페이지를 넘어 이어지는 조각: "bottom" = 아래가 열림, "top" = 위가 열림
    open_end: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "stem_x": self.stem_x,
            "y0": self.y0,
            "y1": self.y1,
            "gap_y0": self.gap_y0,
            "gap_y1": self.gap_y1,
            "tick_x0": self.tick_x0,
            "label_bbox": list(self.label_bbox),
            "body_side": self.body_side,
            "line_ids": list(self.line_ids),
            "open_end": self.open_end,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BracketGroup:
        bb = data["label_bbox"]
        return cls(
            label=str(data["label"]),
            stem_x=float(data["stem_x"]),
            y0=float(data["y0"]),
            y1=float(data["y1"]),
            gap_y0=float(data["gap_y0"]),
            gap_y1=float(data["gap_y1"]),
            tick_x0=float(data["tick_x0"]),
            label_bbox=(float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])),
            body_side=str(data.get("body_side") or "left"),
            line_ids=list(data.get("line_ids") or []),
            open_end=data.get("open_end"),
        )


@dataclass
class RegionSpan:
    """페이지를 넘을 수 있는 [A] 구간. 시작·끝은 괄호 도형이지 문자 표지가 아니다."""

    label: str
    start_page: int
    end_page: int
    start_y: float
    end_y: float
    start_column: int = 0
    end_column: int = 0
    start_line_id: str | None = None
    end_line_id: str | None = None
    start_text: str = ""
    end_text: str = ""
    label_anchor: BBox | None = None

    @property
    def start_pos(self) -> tuple[int, int, float]:
        return (self.start_page, self.start_column, self.start_y)

    @property
    def end_pos(self) -> tuple[int, int, float]:
        return (self.end_page, self.end_column, self.end_y)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "start_y": self.start_y,
            "end_y": self.end_y,
            "start_column": self.start_column,
            "end_column": self.end_column,
            "start_line_id": self.start_line_id,
            "end_line_id": self.end_line_id,
            "start_text": self.start_text,
            "end_text": self.end_text,
            "label_anchor": list(self.label_anchor) if self.label_anchor else None,
        }


def _collect_segments(
    page: Any,
) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    """수직 (y0,y1,x), 짧은 턱 후보 수평 (x0,x1,y)."""
    verts: list[tuple[float, float, float]] = []
    ticks: list[tuple[float, float, float]] = []
    for drawing in page.get_drawings() or []:
        for item in drawing.get("items") or []:
            if not item or item[0] != "l" or len(item) < 3:
                continue
            p1, p2 = item[1], item[2]
            xa, ya = float(p1.x), float(p1.y)
            xb, yb = float(p2.x), float(p2.y)
            if abs(xa - xb) <= _MAX_AXIS_DX and abs(ya - yb) >= _MIN_VERT_LEN:
                verts.append((min(ya, yb), max(ya, yb), (xa + xb) / 2.0))
            elif abs(ya - yb) <= _MAX_AXIS_DY:
                x0, x1 = min(xa, xb), max(xa, xb)
                w = x1 - x0
                if _MIN_TICK <= w <= _MAX_TICK:
                    ticks.append((x0, x1, (ya + yb) / 2.0))
    # 이중 stroke 제거
    verts = sorted(set((round(a, 3), round(b, 3), round(c, 3)) for a, b, c in verts))
    ticks = sorted(set((round(a, 3), round(b, 3), round(c, 3)) for a, b, c in ticks))
    return verts, ticks


def _group_verts_by_x(
    verts: list[tuple[float, float, float]],
) -> list[list[tuple[float, float, float]]]:
    if not verts:
        return []
    ordered = sorted(verts, key=lambda v: (v[2], v[0]))
    groups: list[list[tuple[float, float, float]]] = [[ordered[0]]]
    for seg in ordered[1:]:
        if abs(seg[2] - groups[-1][-1][2]) <= _X_GROUP_TOL:
            groups[-1].append(seg)
        else:
            groups.append([seg])
    for g in groups:
        g.sort(key=lambda v: v[0])
    return groups


def _has_left_tick(
    ticks: list[tuple[float, float, float]],
    *,
    stem_x: float,
    y: float,
    max_width: float | None = None,
) -> tuple[float, float, float] | None:
    """줄기 x·끝점 y에 붙은 왼쪽 짧은 가로선 (오른쪽 여백 괄호)."""
    for x0, x1, ty in ticks:
        if abs(ty - y) > _JOIN_TOL:
            continue
        if abs(x1 - stem_x) > _JOIN_TOL * 1.5:
            continue
        if x0 >= stem_x - 3.0:
            continue
        if max_width is not None and (x1 - x0) > max_width:
            continue
        return (x0, x1, ty)
    return None


def _has_right_tick(
    ticks: list[tuple[float, float, float]],
    *,
    stem_x: float,
    y: float,
    max_width: float | None = None,
) -> tuple[float, float, float] | None:
    """줄기 x·끝점 y에 붙은 오른쪽 짧은 가로선 (왼쪽 여백 괄호)."""
    for x0, x1, ty in ticks:
        if abs(ty - y) > _JOIN_TOL:
            continue
        if abs(x0 - stem_x) > _JOIN_TOL * 1.5:
            continue
        if x1 <= stem_x + 3.0:
            continue
        if max_width is not None and (x1 - x0) > max_width:
            continue
        return (x0, x1, ty)
    return None


def _iter_label_bboxes(page: Any) -> list[tuple[str, BBox]]:
    """페이지에서 [A]~[E] bbox 목록."""
    out: list[tuple[str, BBox]] = []
    search = getattr(page, "search_for", None)
    if callable(search):
        for letter in "ABCDE":
            lab = f"[{letter}]"
            try:
                hits = search(lab) or []
            except Exception:
                hits = []
            for r in hits:
                out.append((lab, (float(r.x0), float(r.y0), float(r.x1), float(r.y1))))
        if out:
            return out

    # fallback: get_text dict spans
    data = page.get_text("dict") if hasattr(page, "get_text") else {}
    for block in data.get("blocks", []) if isinstance(data, dict) else []:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text") or ""
                for m in _LABEL_RE.finditer(text):
                    lab = m.group(0)
                    bb = span.get("bbox") or (0, 0, 0, 0)
                    out.append((lab, (float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3]))))
    return out


def _label_in_gap(
    labels: list[tuple[str, BBox]],
    *,
    stem_x: float,
    gap_y0: float,
    gap_y1: float,
) -> tuple[str, BBox] | None:
    best: tuple[str, BBox] | None = None
    best_dist = 1e9
    for lab, bb in labels:
        cx = (bb[0] + bb[2]) / 2.0
        cy = (bb[1] + bb[3]) / 2.0
        if cy < gap_y0 - _LABEL_Y_PAD or cy > gap_y1 + _LABEL_Y_PAD:
            continue
        if abs(cx - stem_x) > _LABEL_X_PAD:
            continue
        dist = abs(cx - stem_x) + abs(cy - (gap_y0 + gap_y1) / 2.0)
        if dist < best_dist:
            best_dist = dist
            best = (lab, bb)
    return best


def _page_band_limits(
    page: Any,
    *,
    profile: Any | None,
) -> tuple[float, float]:
    """헤더 아래·푸터 위. 프로필이 없으면 면 높이로 추정."""
    height = float(getattr(getattr(page, "rect", None), "height", 0) or 0)
    header_bottom = 160.0
    footer_top = height - 80.0 if height else 1000.0
    if profile is not None:
        header_bottom = float(getattr(profile, "header_bottom_y", header_bottom))
        footer_top = float(getattr(profile, "footer_top_y", footer_top))
    return header_bottom, footer_top


def _page_height(page: Any) -> float:
    return float(getattr(getattr(page, "rect", None), "height", 0) or 0)


def _touches_bottom(y1: float, *, footer_top: float, page: Any) -> bool:
    height = _page_height(page)
    if y1 >= footer_top - _BOTTOM_SLACK:
        return True
    return bool(height) and y1 >= height * 0.88


def _touches_top(y0: float, *, header_bottom: float, page: Any) -> bool:
    height = _page_height(page)
    if y0 <= header_bottom + _TOP_SLACK:
        return True
    return bool(height) and y0 <= height * 0.20


def detect_bracket_geometries(
    page: Any,
    *,
    profile: Any | None = None,
) -> list[BracketGroup]:
    """드로잉+라벨로 BracketGroup 골격(line_ids 비움)을 만든다.

    한 면에서 위·아래 턱이 모두 있으면 완결 괄호.
    아래 턱만 없고 라벨이 있으면 페이지를 넘는 시작 조각(open_end=bottom).
    위 턱만 없고 본문 상단에 있으면 이어짐 조각(open_end=top, 라벨은 이후 연결).
    """
    verts, ticks = _collect_segments(page)
    labels = _iter_label_bboxes(page)
    header_bottom, footer_top = _page_band_limits(page, profile=profile)
    groups: list[BracketGroup] = []
    for cluster in _group_verts_by_x(verts):
        for i in range(len(cluster)):
            for j in range(i + 1, len(cluster)):
                upper, lower = cluster[i], cluster[j]
                gap = lower[0] - upper[1]
                if not (_MIN_GAP <= gap <= _MAX_GAP):
                    continue
                stem_x = (upper[2] + lower[2]) / 2.0
                top_left = _has_left_tick(ticks, stem_x=stem_x, y=upper[0])
                bot_left = _has_left_tick(ticks, stem_x=stem_x, y=lower[1])
                top_right = _has_right_tick(ticks, stem_x=stem_x, y=upper[0])
                bot_right = _has_right_tick(ticks, stem_x=stem_x, y=lower[1])
                hit = _label_in_gap(
                    labels,
                    stem_x=stem_x,
                    gap_y0=upper[1],
                    gap_y1=lower[0],
                )

                body_side: str | None = None
                tick_tip = 0.0
                open_end: str | None = None
                if top_left is not None and bot_left is not None:
                    body_side = "left"
                    tick_tip = min(top_left[0], bot_left[0])
                elif top_right is not None and bot_right is not None:
                    body_side = "right"
                    tick_tip = max(top_right[1], bot_right[1])
                elif (
                    hit is not None
                    and (top_left is not None or top_right is not None)
                    and bot_left is None
                    and bot_right is None
                    and _touches_bottom(lower[1], footer_top=footer_top, page=page)
                ):
                    open_end = "bottom"
                    if top_left is not None:
                        body_side = "left"
                        tick_tip = top_left[0]
                    else:
                        assert top_right is not None
                        body_side = "right"
                        tick_tip = top_right[1]
                else:
                    continue

                if hit is None or body_side is None:
                    continue
                lab, lbb = hit
                groups.append(
                    BracketGroup(
                        label=lab,
                        stem_x=stem_x,
                        y0=upper[0],
                        y1=lower[1],
                        gap_y0=upper[1],
                        gap_y1=lower[0],
                        tick_x0=tick_tip,
                        label_bbox=lbb,
                        body_side=body_side,
                        open_end=open_end,
                    )
                )

        # 다음 면 상단에서 이어지는 줄기: 위 턱 없음, 아래 짧은 턱, 라벨 없음
        for seg in cluster:
            y0, y1, stem_x = seg
            if not _touches_top(y0, header_bottom=header_bottom, page=page):
                continue
            if any(
                abs(g.stem_x - stem_x) <= _X_GROUP_TOL
                and g.y0 - 2 <= y0
                and y1 <= g.y1 + 2
                for g in groups
            ):
                continue
            top_left = _has_left_tick(ticks, stem_x=stem_x, y=y0)
            top_right = _has_right_tick(ticks, stem_x=stem_x, y=y0)
            if top_left is not None or top_right is not None:
                continue
            bot_left = _has_left_tick(
                ticks, stem_x=stem_x, y=y1, max_width=_MAX_OPEN_TICK
            )
            bot_right = _has_right_tick(
                ticks, stem_x=stem_x, y=y1, max_width=_MAX_OPEN_TICK
            )
            if bot_left is not None:
                body_side = "left"
                tick_tip = bot_left[0]
            elif bot_right is not None:
                body_side = "right"
                tick_tip = bot_right[1]
            else:
                continue
            groups.append(
                BracketGroup(
                    label="",
                    stem_x=stem_x,
                    y0=y0,
                    y1=y1,
                    gap_y0=y0,
                    gap_y1=y0,
                    tick_x0=tick_tip,
                    label_bbox=(stem_x, y0, stem_x, y0),
                    body_side=body_side,
                    open_end="top",
                )
            )
    # 겹치는 후보가 있으면 더 짧은(정확한) 쪽 우선
    groups.sort(key=lambda g: (g.y0, g.stem_x, g.y1 - g.y0))
    kept: list[BracketGroup] = []
    for g in groups:
        if any(
            abs(g.stem_x - k.stem_x) <= _X_GROUP_TOL
            and abs(g.y0 - k.y0) <= 4.0
            and abs(g.y1 - k.y1) <= 4.0
            for k in kept
        ):
            continue
        kept.append(g)
    return kept


def _center_in_bbox(char_bbox: BBox, target: BBox, *, pad: float = 1.5) -> bool:
    cx = (char_bbox[0] + char_bbox[2]) / 2.0
    cy = (char_bbox[1] + char_bbox[3]) / 2.0
    return (
        target[0] - pad <= cx <= target[2] + pad
        and target[1] - pad <= cy <= target[3] + pad
    )


def _union_bbox(boxes: list[BBox]) -> BBox:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def remove_detected_label_text(
    spans: list[PdfSpan],
    groups: list[BracketGroup],
) -> None:
    """괄호 공백에 인쇄된 물리적 ``[A]`` 텍스트만 span에서 제거한다.

    문항 본문의 ``[A]의 학생 2`` 같은 참조는 label bbox 밖이므로 보존된다.
    괄호 의미는 ``BracketGroup``/행·블록 메타데이터로 계속 유지된다.
    """
    if not spans or not groups:
        return

    for span in spans:
        old_text = span.text
        if not old_text:
            continue
        old_flags = [False] * len(old_text)
        for start, end in span.underline_ranges:
            for i in range(max(0, start), min(len(old_flags), end)):
                old_flags[i] = True

        remove = [False] * len(old_text)
        labeled = [g for g in groups if g.label]
        if not labeled:
            continue
        if len(span.char_bboxes) == len(old_text):
            for group in labeled:
                for i, char_bbox in enumerate(span.char_bboxes):
                    if _center_in_bbox(char_bbox, group.label_bbox):
                        remove[i] = True
        else:
            # char bbox가 없는 PDF에서는 label과 거의 같은 span만 제한적으로 제거한다.
            for group in labeled:
                if old_text.strip() != group.label:
                    continue
                sx0, sy0, sx1, sy1 = span.bbox
                lx0, ly0, lx1, ly1 = group.label_bbox
                if sx1 < lx0 - 2 or sx0 > lx1 + 2 or sy1 < ly0 - 2 or sy0 > ly1 + 2:
                    continue
                remove = [True] * len(old_text)
                break

        if not any(remove):
            continue

        kept_indices = [i for i, removed in enumerate(remove) if not removed]
        span.text = "".join(old_text[i] for i in kept_indices)
        span.underline_ranges = merge_underline_flags(
            [old_flags[i] for i in kept_indices]
        )
        if len(span.char_bboxes) == len(old_text):
            span.char_bboxes = [span.char_bboxes[i] for i in kept_indices]
            if span.char_bboxes:
                span.bbox = _union_bbox(span.char_bboxes)


def assign_lines_to_brackets(
    lines: list[PdfLine],
    groups: list[BracketGroup],
) -> list[BracketGroup]:
    """y 범위·줄기 좌/우 본문 조건으로 행을 괄호에 소속시키고 line.bracket_label 설정."""
    if not lines or not groups:
        return groups

    for ln in lines:
        ln.bracket_label = None

    for g in groups:
        g.line_ids = []

    for ln in lines:
        best: BracketGroup | None = None
        best_score = 1e9
        for g in groups:
            if not g.label:
                continue
            if ln.bbox[3] <= g.y0 or ln.bbox[1] >= g.y1:
                continue
            if g.body_side == "right":
                # 왼쪽 여백 괄호: 본문은 바로 오른쪽 단. 다음 열(300pt+)은 제외.
                if ln.bbox[2] <= g.stem_x + _LINE_STEM_PAD:
                    continue
                dist = ln.bbox[0] - g.stem_x
                if dist < -_LINE_OVERFLOW_PAD or dist > _MAX_BODY_GAP:
                    continue
            else:
                # 오른쪽 여백 괄호: 짧은 줄은 줄기에서 멀 수 있어 상한을 두지 않는다.
                if ln.bbox[0] >= g.stem_x - _LINE_STEM_PAD:
                    continue
                dist = g.stem_x - ln.bbox[2]
                if dist < -_LINE_OVERFLOW_PAD:
                    continue
            score = abs(dist)
            if score < best_score:
                best_score = score
                best = g
        if best is None:
            continue
        ln.bracket_label = best.label
        best.line_ids.append(ln.id)

    for g in groups:
        order = {ln.id: i for i, ln in enumerate(lines)}
        g.line_ids.sort(key=lambda lid: order.get(lid, 10**9))
    return groups


def annotate_blocks_with_brackets(
    blocks: list[PdfBlock],
    lines: list[PdfLine],
    groups: list[BracketGroup],
) -> None:
    """블록에 구간 소속과 시작 표지를 메타 태그로 표시."""
    if not blocks or not groups:
        return
    line_map = {ln.id: ln for ln in lines}
    for block in blocks:
        labels: list[str] = []
        for lid in block.line_ids:
            ln = line_map.get(lid)
            if ln is None or not ln.bracket_label:
                continue
            if ln.bracket_label not in labels:
                labels.append(ln.bracket_label)
        if not labels:
            continue
        tag = f"bracket:{','.join(labels)}"
        if tag not in block.candidate_tags:
            block.candidate_tags.append(tag)
        starts = [
            group.label
            for group in groups
            if group.line_ids
            and group.line_ids[0] in block.line_ids
            and group.label in labels
            and group.open_end != "top"
        ]
        if starts:
            start_tag = f"bracket-start:{','.join(starts)}"
            if start_tag not in block.candidate_tags:
                block.candidate_tags.append(start_tag)
        ends = [
            group.label
            for group in groups
            if group.line_ids
            and group.line_ids[-1] in block.line_ids
            and group.label in labels
            and group.open_end != "bottom"
        ]
        if ends:
            end_tag = f"bracket-end:{','.join(ends)}"
            if end_tag not in block.candidate_tags:
                block.candidate_tags.append(end_tag)
        note = "구간 " + ", ".join(labels)
        if block.notes:
            if note not in block.notes:
                block.notes = f"{block.notes}; {note}"
        else:
            block.notes = note


def detect_and_assign_bracket_groups(
    page: Any,
    lines: list[PdfLine],
    *,
    profile: Any | None = None,
) -> list[BracketGroup]:
    """감지 + 행 소속까지 한 번에."""
    groups = detect_bracket_geometries(page, profile=profile)
    return assign_lines_to_brackets(lines, groups)


def _column_inset(stem_x: float, page_width: float, profile: Any | None) -> float:
    """단 왼쪽 기준 줄기 상대 x. 2단에서 우열→다음 면 좌열 이어짐 비교용."""
    cut = page_width * 0.5
    right_left = cut
    if profile is not None:
        cut = float(getattr(profile, "column_cut_x", cut) or cut)
        right_left = float(getattr(profile, "right_column_left_x", cut) or cut)
    if stem_x >= cut:
        return stem_x - right_left
    return stem_x - _LEFT_COL_ORIGIN


def _refresh_bracket_annotations(page: Any) -> None:
    for block in page.blocks:
        block.candidate_tags = [
            tag
            for tag in block.candidate_tags
            if not str(tag).startswith("bracket")
        ]
    annotate_blocks_with_brackets(page.blocks, page.lines, page.bracket_groups)


def link_cross_page_brackets(
    pages: list[Any],
    *,
    profile: Any | None = None,
) -> None:
    """아래가 열린 [A]와 다음 면 위가 열린 줄기를 같은 구간으로 잇는다.

    절대 y를 이어 붙이지 않는다. 시작 면이 푸터 근처에서 열리고,
    다음 면 같은 여백(body_side) 상단에서 닫히면 라벨을 승격한다.
    2단이면 우열→다음 면 좌열처럼 x가 달라도 단 상대 inset으로 맞춘다.
    """
    if len(pages) < 2:
        for page in pages:
            page.bracket_groups = [g for g in page.bracket_groups if g.label]
        return
    for prev, nxt in zip(pages, pages[1:]):
        prev_no = int(getattr(prev, "page_number", 0) or 0)
        nxt_no = int(getattr(nxt, "page_number", 0) or 0)
        if nxt_no != prev_no + 1:
            continue
        bottoms = [
            g
            for g in prev.bracket_groups
            if g.open_end == "bottom" and g.label
        ]
        tops = [g for g in nxt.bracket_groups if g.open_end == "top"]
        used: set[int] = set()
        linked_prev: set[int] = set()
        for g in bottoms:
            cand = [
                h
                for h in tops
                if id(h) not in used
                and h.body_side == g.body_side
                and not h.label
            ]
            if not cand:
                continue

            def score(h: BracketGroup, src: BracketGroup = g) -> float:
                abs_d = abs(src.stem_x - h.stem_x)
                ins_d = abs(
                    _column_inset(src.stem_x, prev.width, profile)
                    - _column_inset(h.stem_x, nxt.width, profile)
                )
                return min(abs_d, ins_d)

            h = min(cand, key=score)
            if len(cand) > 1 and score(h) > _INSET_TOL + 20.0:
                continue
            h.label = g.label
            used.add(id(h))
            linked_prev.add(id(g))
        if used:
            nxt.bracket_groups = [g for g in nxt.bracket_groups if g.label]
            assign_lines_to_brackets(nxt.lines, nxt.bracket_groups)
            _refresh_bracket_annotations(nxt)
            _refresh_bracket_annotations(prev)
        for g in prev.bracket_groups:
            if g.open_end == "bottom" and id(g) not in linked_prev:
                g.open_end = None
    for page in pages:
        page.bracket_groups = [g for g in page.bracket_groups if g.label]


def _column_of_x(x: float, cut: float | None) -> int:
    if cut is None:
        return 0
    return 0 if x < cut else 1


def _group_endpoints(
    group: BracketGroup,
    lines: list[PdfLine],
) -> tuple[PdfLine | None, PdfLine | None]:
    by_id = {ln.id: ln for ln in lines}
    first = by_id.get(group.line_ids[0]) if group.line_ids else None
    last = by_id.get(group.line_ids[-1]) if group.line_ids else None
    return first, last


def _real_label_anchor(group: BracketGroup) -> BBox | None:
    bb = group.label_bbox
    if not group.label:
        return None
    if abs(bb[2] - bb[0]) < 1.0 and abs(bb[3] - bb[1]) < 1.0:
        return None
    return bb


def build_region_spans(
    pages: list[Any],
    *,
    profile: Any | None = None,
    column_cut_x: float | None = None,
) -> list[RegionSpan]:
    """연결된 괄호 조각을 하나의 RegionSpan으로 승격한다.

    시작·끝 y는 문자 ``[A]``가 아니라 괄호 도형의 수직 범위다.
    """
    cut = column_cut_x
    if cut is None and profile is not None:
        raw = getattr(profile, "column_cut_x", None)
        if raw is not None:
            cut = float(raw)
    spans: list[RegionSpan] = []
    open_span: RegionSpan | None = None
    for page in sorted(pages, key=lambda p: int(getattr(p, "page_number", 0) or 0)):
        page_no = int(page.page_number)
        groups = sorted(
            (g for g in page.bracket_groups if g.label),
            key=lambda g: (g.y0, g.stem_x),
        )
        for group in groups:
            col = _column_of_x(group.stem_x, cut)
            first, last = _group_endpoints(group, page.lines)
            anchor = _real_label_anchor(group)
            if (
                open_span is not None
                and group.open_end == "top"
                and group.label == open_span.label
                and page_no == open_span.end_page + 1
            ):
                open_span.end_page = page_no
                open_span.end_y = group.y1
                open_span.end_column = col
                open_span.end_line_id = last.id if last else open_span.end_line_id
                open_span.end_text = (last.text or "") if last else open_span.end_text
                spans.append(open_span)
                open_span = None
                continue
            if open_span is not None:
                spans.append(open_span)
                open_span = None
            span = RegionSpan(
                label=group.label,
                start_page=page_no,
                end_page=page_no,
                start_y=group.y0,
                end_y=group.y1,
                start_column=col,
                end_column=col,
                start_line_id=first.id if first else None,
                end_line_id=last.id if last else None,
                start_text=(first.text or "") if first else "",
                end_text=(last.text or "") if last else "",
                label_anchor=anchor,
            )
            if group.open_end == "bottom":
                open_span = span
            else:
                spans.append(span)
    if open_span is not None:
        spans.append(open_span)
    return spans
