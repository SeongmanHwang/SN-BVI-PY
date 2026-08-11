"""행을 문단/블록으로 묶는다. 구조 표식·간격·문단 구분·열·헤더/푸터를 함께 본다."""

from __future__ import annotations

import re

from korean_exam_braille.app.pdf.layout_profile import PageLayoutProfile
from korean_exam_braille.app.pdf.models import BBox, PdfBlock, PdfLine

_BLOCK_START = re.compile(
    r"^\s*(?:"
    r"\[\s*\d{1,2}\s*[~\-–—]\s*\d{1,2}\s*\]"
    r"|\d{1,2}\s*[\.．。]"
    r"|[①②③④⑤]"
    r"|[1-5]\s*[\)］\]]"
    r"|[ㄱㄴㄷㄹㅁ]\s*[\.．]"
    r"|〈\s*보\s*기\s*\d*\s*〉|<\s*보\s*기\s*\d*\s*>|【\s*보\s*기\s*\d*\s*】"
    r"|━{5,}|─{5,}|_{5,}|={5,}"
    r")"
)


def _union_bbox(boxes: list[BBox]) -> BBox:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _column_key(line: PdfLine, cut: float | None, profile: PageLayoutProfile | None) -> int:
    if profile is not None:
        band = profile.band_of_y(line.bbox[1])
        if band == "header":
            return -2
        if band == "footer":
            return 2
        mid = (line.bbox[0] + line.bbox[2]) / 2
        width = line.bbox[2] - line.bbox[0]
        if profile.uses_page_local_columns() or profile.column_detection == "single":
            if cut is None:
                return 0
            if width > cut and line.bbox[0] < cut < line.bbox[2]:
                return -1
            return 0 if mid < cut else 1
        return profile.column_of_x(mid, span_width=width)

    if cut is None:
        return 0
    mid = (line.bbox[0] + line.bbox[2]) / 2
    width = line.bbox[2] - line.bbox[0]
    if width > cut and line.bbox[0] < cut < line.bbox[2]:
        return -1
    return 0 if mid < cut else 1


def _estimate_cut(lines: list[PdfLine]) -> float | None:
    if len(lines) < 6:
        return None
    mids = sorted((ln.bbox[0] + ln.bbox[2]) / 2 for ln in lines)
    right = max(ln.bbox[2] for ln in lines)
    best_gap = 0.0
    best = None
    for a, b in zip(mids, mids[1:]):
        gap = b - a
        cut = (a + b) / 2
        if cut < right * 0.28 or cut > right * 0.72:
            continue
        if gap > best_gap:
            best_gap = gap
            best = cut
    if best is not None and best_gap >= 24.0:
        return best
    return None


def _starts_new_block(text: str) -> bool:
    return bool(_BLOCK_START.match(text or ""))


def _paragraph_boundary(
    prev: PdfLine,
    line: PdfLine,
    *,
    gap: float,
    median_h: float,
) -> bool:
    """문단 구분: 왼쪽 정렬 복귀 + 중간 세로 간격으로 새 블록.

    제품 대상은 Passage(및 Unknown 재분류 전 무태그 본문).
    Prompt/Paragraph는 문단 구분 대상이 아니며, Exam 소속 게이트는 후속 과제.
    (구칭: 내어쓰기 — 구조 표식·큰 gap에 안 걸린 슬롯만 담당.)
    """
    # 유효 조건: x0이 8pt 이상 왼쪽이고 0.5h < gap (큰 gap은 호출 전에 처리됨)
    if line.bbox[0] + 8 >= prev.bbox[0]:
        return False
    return gap > median_h * 0.5


def build_blocks(
    lines: list[PdfLine],
    page_number: int,
    *,
    gap_factor: float = 0.85,
    profile: PageLayoutProfile | None = None,
) -> list[PdfBlock]:
    """열별·구조 표식·헤더/푸터 기준으로 블록을 나눈다."""
    if not lines:
        return []

    if profile is not None and profile.uses_page_local_columns():
        cut = _estimate_cut(lines)
    elif profile is not None and profile.column_detection == "single":
        cut = None
    elif profile is not None:
        cut = profile.column_cut_x
    else:
        cut = _estimate_cut(lines)
    heights = [max(1.0, ln.bbox[3] - ln.bbox[1]) for ln in lines]
    median_h = sorted(heights)[len(heights) // 2]
    max_gap = median_h * gap_factor

    by_col: dict[int, list[PdfLine]] = {}
    for ln in lines:
        by_col.setdefault(_column_key(ln, cut, profile), []).append(ln)
    for col in by_col:
        by_col[col].sort(key=lambda ln: (ln.bbox[1], ln.bbox[0]))

    groups: list[list[PdfLine]] = []
    for col in sorted(by_col):
        ordered = by_col[col]
        current: list[PdfLine] = [ordered[0]]
        for prev, line in zip(ordered, ordered[1:]):
            gap = line.bbox[1] - prev.bbox[3]
            new_block = False
            if col in (-2, 2):
                new_block = gap > median_h * 0.35 or _starts_new_block(line.text)
            elif _starts_new_block(line.text):
                new_block = True
            elif gap > max_gap:
                new_block = True
            # 문단 구분 일시 비활성 — Mode B에서 PassageGroup L/R 요약 관찰용
            # elif _paragraph_boundary(prev, line, gap=gap, median_h=median_h):
            #     new_block = True

            if new_block:
                groups.append(current)
                current = [line]
            elif prev.bracket_label != line.bracket_label:
                # [A]~[E] 소속 전환 — 점역 ┌──── 표지가 앞 서술까지 감싸지 않도록
                groups.append(current)
                current = [line]
            else:
                current.append(line)
        groups.append(current)

    blocks: list[PdfBlock] = []
    for idx, group in enumerate(groups):
        text = "\n".join(ln.text for ln in group if ln.text is not None)
        bbox = _union_bbox([ln.bbox for ln in group])
        blocks.append(
            PdfBlock(
                id=f"p{page_number}-b{idx}",
                text=text,
                bbox=bbox,
                line_ids=[ln.id for ln in group],
                page_number=page_number,
                reading_order=idx,
            )
        )
    return blocks


def merge_blocks(blocks: list[PdfBlock], left_id: str, right_id: str) -> list[PdfBlock]:
    """두 블록을 하나로 합친다. reading_order가 앞인 쪽 텍스트가 먼저."""
    by_id = {b.id: b for b in blocks}
    if left_id not in by_id or right_id not in by_id:
        raise KeyError("block id not found")
    a, b = by_id[left_id], by_id[right_id]
    if a.reading_order <= b.reading_order:
        first, second = a, b
    else:
        first, second = b, a
    merged = PdfBlock(
        id=first.id,
        text=first.text + ("\n" if first.text and second.text else "") + second.text,
        bbox=_union_bbox([first.bbox, second.bbox]),
        line_ids=list(first.line_ids) + list(second.line_ids),
        page_number=first.page_number,
        reading_order=min(first.reading_order, second.reading_order),
        candidate_tags=list(dict.fromkeys(first.candidate_tags + second.candidate_tags)),
        tags=list(dict.fromkeys(first.tags + second.tags)),
        notes=first.notes or second.notes,
    )
    out = [merged if blk.id == first.id else blk for blk in blocks if blk.id != second.id]
    for i, blk in enumerate(sorted(out, key=lambda x: (x.bbox[1], x.bbox[0]))):
        blk.reading_order = i
    return sorted(out, key=lambda x: x.reading_order)


def split_block(block: PdfBlock, lines: list[PdfLine], split_after_line_id: str) -> tuple[PdfBlock, PdfBlock]:
    """지정 행 뒤에서 블록을 둘로 나눈다."""
    if split_after_line_id not in block.line_ids:
        raise KeyError(f"line {split_after_line_id} not in block")
    idx = block.line_ids.index(split_after_line_id)
    left_ids = block.line_ids[: idx + 1]
    right_ids = block.line_ids[idx + 1 :]
    if not right_ids:
        raise ValueError("split would create an empty block")
    line_map = {ln.id: ln for ln in lines}
    left_lines = [line_map[i] for i in left_ids if i in line_map]
    right_lines = [line_map[i] for i in right_ids if i in line_map]
    left = PdfBlock(
        id=block.id,
        text="\n".join(ln.text for ln in left_lines),
        bbox=_union_bbox([ln.bbox for ln in left_lines]),
        line_ids=left_ids,
        page_number=block.page_number,
        reading_order=block.reading_order,
        candidate_tags=list(block.candidate_tags),
        tags=list(block.tags),
        notes=block.notes,
    )
    right = PdfBlock(
        id=f"{block.id}-split",
        text="\n".join(ln.text for ln in right_lines),
        bbox=_union_bbox([ln.bbox for ln in right_lines]),
        line_ids=right_ids,
        page_number=block.page_number,
        reading_order=block.reading_order + 1,
        candidate_tags=[],
        tags=[],
        notes=None,
    )
    return left, right
