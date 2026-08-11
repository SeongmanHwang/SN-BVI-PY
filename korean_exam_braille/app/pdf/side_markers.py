"""오른쪽 짧은 측면 마커(①~⑤ 등)를 왼쪽 다행 블록에 붙인다.

2단 reading order만 쓰면 마커가 질문들 뒤로 몰린다. 마커 center_y가
왼쪽 질문 블록 y 범위 안에 있으면 그 블록의 trailing_marker로 두고,
독립 Choice 블록에서는 제외한다.
"""

from __future__ import annotations

import re

from korean_exam_braille.app.pdf.models import BBox, PdfBlock, PdfLine

# 마커만 있는 블록/행 (본문 없음)
_MARKER_ONLY = re.compile(
    r"^\s*(?:"
    r"[①②③④⑤⑥⑦⑧⑨⑩]"
    r"|[ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ]"
    r"|[ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ]\s*[\.．]?"
    r"|[1-5]\s*[\)］\]]"
    r")\s*$"
)


def is_marker_only_text(text: str) -> bool:
    return bool(_MARKER_ONLY.match((text or "").strip()))


def _center(bbox: BBox) -> tuple[float, float]:
    return (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0


def _rebuild_block_text(block: PdfBlock, line_map: dict[str, PdfLine]) -> None:
    parts: list[str] = []
    for lid in block.line_ids:
        ln = line_map.get(lid)
        if ln is None or not (ln.text or "").strip():
            continue
        piece = ln.text.rstrip()
        if ln.trailing_marker:
            piece = f"{piece} {ln.trailing_marker}".rstrip()
        parts.append(piece)
    block.text = "\n".join(parts)


def attach_trailing_side_markers(
    blocks: list[PdfBlock],
    lines: list[PdfLine],
    *,
    max_x_gap: float = 140.0,
    min_owner_lines: int = 2,
    max_owner_lines: int = 6,
    max_marker_width: float = 48.0,
) -> list[PdfBlock]:
    """측면 마커 블록을 왼쪽 다행 소유 블록에 붙이고 목록에서 제거한다.

    성공 시 소유자 마지막 행의 ``trailing_marker``와 ``block.text``를 갱신한다.
    진짜 선택지(``① 본문``)나 과다 행 Passage는 건드리지 않는다.
    """
    if not blocks:
        return blocks

    line_map = {ln.id: ln for ln in lines}
    consumed: set[str] = set()
    owners_used: set[str] = set()

    markers = [
        b
        for b in blocks
        if is_marker_only_text(b.text)
        and (b.bbox[2] - b.bbox[0]) <= max_marker_width
    ]

    for marker in markers:
        mx, my = _center(marker.bbox)
        best: PdfBlock | None = None
        best_dist = float("inf")
        for owner in blocks:
            if owner.id == marker.id or owner.id in owners_used:
                continue
            if owner.id in consumed:
                continue
            n_lines = len(owner.line_ids)
            if n_lines < min_owner_lines or n_lines > max_owner_lines:
                continue
            if is_marker_only_text(owner.text):
                continue
            first = (owner.text or "").lstrip().split("\n", 1)[0]
            # 선택지 본문(① 가…)은 소유 후보에서 제외. 문항번호(16.)는 허용.
            if re.match(r"^\s*[①②③④⑤]", first) or re.match(
                r"^\s*[ㄱㄴㄷㄹㅁ]\s*[\.．]", first
            ) or re.match(r"^\s*[1-5]\s*[\)］\]]", first):
                continue

            oy0, oy1 = owner.bbox[1], owner.bbox[3]
            if not (oy0 - 2.0 <= my <= oy1 + 2.0):
                continue
            # 마커가 소유자 오른쪽
            if marker.bbox[0] + 2.0 < owner.bbox[2]:
                # 살짝 겹칠 수는 있으나 mid는 오른쪽이어야 함
                if mx <= _center(owner.bbox)[0]:
                    continue
            gap = marker.bbox[0] - owner.bbox[2]
            if gap > max_x_gap:
                continue
            if gap < -20.0:
                continue
            dist = abs(my - _center(owner.bbox)[1])
            if dist < best_dist:
                best_dist = dist
                best = owner

        if best is None or not best.line_ids:
            continue
        last = line_map.get(best.line_ids[-1])
        if last is None:
            continue
        ink = (marker.text or "").strip()
        if not ink:
            continue
        last.trailing_marker = ink
        _rebuild_block_text(best, line_map)
        owners_used.add(best.id)
        consumed.add(marker.id)

    if not consumed:
        return blocks

    remaining = [b for b in blocks if b.id not in consumed]
    # 마커 행은 소유에 흡수되지 않고 목록에서만 빠짐 — line은 trailing로만 반영
    return remaining
