"""오른쪽 여백 [A]~[E] 꺾인 괄호(drawing) → 소속 행 구간 복원.

수능 문제지에서 구간 표지는 보통 이렇게 들어 있다::

    본문 행들 …        ┐
                       │
                       │  [A]   ← 세로선 사이 ~14pt 공백
                       │
                       ┘

가로·세로선은 각각 독립 ``line`` drawing 이고, OCR 없이 ``get_drawings()``
와 ``[A]`` 텍스트 좌표만으로 복원할 수 있다.
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
_MIN_VERT_LEN = 12.0
# 왼쪽 턱(짧은 가로선) — 박스 긴 변과 구분
_MIN_TICK = 4.0
_MAX_TICK = 28.0
# 라벨이 끼는 세로선 공백
_MIN_GAP = 6.0
_MAX_GAP = 36.0
_X_GROUP_TOL = 2.5
_JOIN_TOL = 2.5
_LABEL_X_PAD = 30.0
_LABEL_Y_PAD = 6.0
# 본문 행은 괄호 줄기보다 왼쪽에서 시작
_LINE_LEFT_OF_STEM = 8.0


@dataclass
class BracketGroup:
    """한 페이지의 [A] 등 꺾인 괄호 구간."""

    label: str  # "[A]"
    stem_x: float
    y0: float
    y1: float
    gap_y0: float
    gap_y1: float
    tick_x0: float
    label_bbox: BBox
    line_ids: list[str] = field(default_factory=list)

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
            "line_ids": list(self.line_ids),
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
            line_ids=list(data.get("line_ids") or []),
        )


def _collect_segments(
    page: Any,
) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    """수직 (y0,y1,x), 짧은 왼쪽턱 후보 수평 (x0,x1,y)."""
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
) -> tuple[float, float, float] | None:
    """줄기 x·끝점 y에 붙은 왼쪽 짧은 가로선."""
    for x0, x1, ty in ticks:
        if abs(ty - y) > _JOIN_TOL:
            continue
        if abs(x1 - stem_x) > _JOIN_TOL * 1.5:
            continue
        if x0 >= stem_x - 3.0:
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


def detect_bracket_geometries(page: Any) -> list[BracketGroup]:
    """드로잉+라벨로 BracketGroup 골격(line_ids 비움)을 만든다."""
    verts, ticks = _collect_segments(page)
    labels = _iter_label_bboxes(page)
    groups: list[BracketGroup] = []
    for cluster in _group_verts_by_x(verts):
        for i in range(len(cluster)):
            for j in range(i + 1, len(cluster)):
                upper, lower = cluster[i], cluster[j]
                gap = lower[0] - upper[1]
                if not (_MIN_GAP <= gap <= _MAX_GAP):
                    continue
                stem_x = (upper[2] + lower[2]) / 2.0
                top_tick = _has_left_tick(ticks, stem_x=stem_x, y=upper[0])
                bot_tick = _has_left_tick(ticks, stem_x=stem_x, y=lower[1])
                if top_tick is None or bot_tick is None:
                    continue
                hit = _label_in_gap(
                    labels,
                    stem_x=stem_x,
                    gap_y0=upper[1],
                    gap_y1=lower[0],
                )
                if hit is None:
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
                        tick_x0=min(top_tick[0], bot_tick[0]),
                        label_bbox=lbb,
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
        if len(span.char_bboxes) == len(old_text):
            for group in groups:
                for i, char_bbox in enumerate(span.char_bboxes):
                    if _center_in_bbox(char_bbox, group.label_bbox):
                        remove[i] = True
        else:
            # char bbox가 없는 PDF에서는 label과 거의 같은 span만 제한적으로 제거한다.
            for group in groups:
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
    """y 범위·왼쪽 열 조건으로 행을 괄호에 소속시키고 line.bracket_label 설정."""
    if not lines or not groups:
        return groups

    # 한 행이 여러 괄호에 걸리면 줄기 x가 더 가까운(같은 열) 쪽
    for ln in lines:
        ln.bracket_label = None

    for g in groups:
        g.line_ids = []

    for ln in lines:
        best: BracketGroup | None = None
        best_score = 1e9
        for g in groups:
            if ln.bbox[3] <= g.y0 or ln.bbox[1] >= g.y1:
                continue
            # 본문은 줄기보다 왼쪽에서 시작 (줄 끝 [A] 부착으로 오른쪽이 넘칠 수 있음)
            if ln.bbox[0] >= g.stem_x - _LINE_LEFT_OF_STEM:
                continue
            # 줄 오른쪽 끝과 줄기 사이 거리가 가장 가까운 괄호(같은 열)
            dist = g.stem_x - ln.bbox[2]
            if dist < -28.0:
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
        # 읽기 순 유지
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
) -> list[BracketGroup]:
    """감지 + 행 소속까지 한 번에."""
    groups = detect_bracket_geometries(page)
    return assign_lines_to_brackets(lines, groups)
