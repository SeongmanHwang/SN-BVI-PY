"""블록 읽기 순서 — 헤더 → 좌열 → 우열 → 푸터."""

from __future__ import annotations

from korean_exam_braille.app.pdf.layout_profile import PageLayoutProfile
from korean_exam_braille.app.pdf.models import PdfBlock


def _estimate_cut(blocks: list[PdfBlock]) -> float | None:
    if len(blocks) < 4:
        return None
    mids = sorted((b.bbox[0] + b.bbox[2]) / 2 for b in blocks)
    right = max(b.bbox[2] for b in blocks)
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
    if best is not None and best_gap >= max(28.0, right * 0.045):
        return best
    return None


def _region_key(block: PdfBlock, profile: PageLayoutProfile | None, cut: float | None) -> tuple:
    if profile is not None:
        band = profile.band_of_y(block.bbox[1])
        if band == "header":
            return (0, block.bbox[1], block.bbox[0])
        if band == "footer":
            return (3, block.bbox[1], block.bbox[0])
        mid = (block.bbox[0] + block.bbox[2]) / 2
        width = block.bbox[2] - block.bbox[0]
        col = profile.column_of_x(mid, span_width=width)
        # 전폭(-1)은 헤더 다음·좌열 앞
        col_order = {-1: 1, 0: 2, 1: 3}.get(col, 2)
        return (col_order, block.bbox[1], block.bbox[0])

    if cut is None:
        return (0, block.bbox[1], block.bbox[0])
    mid = (block.bbox[0] + block.bbox[2]) / 2
    width = block.bbox[2] - block.bbox[0]
    if width > cut and block.bbox[0] < cut < block.bbox[2]:
        return (0, block.bbox[1], block.bbox[0])
    col = 0 if mid < cut else 1
    return (1 + col, block.bbox[1], block.bbox[0])


def assign_reading_order(
    blocks: list[PdfBlock],
    *,
    profile: PageLayoutProfile | None = None,
) -> list[PdfBlock]:
    """헤더 → (전폭) → 좌단 → 우단 → 푸터."""
    cut = profile.column_cut_x if profile is not None else _estimate_cut(blocks)
    ordered = sorted(blocks, key=lambda b: _region_key(b, profile, cut) + (b.id,))
    for i, block in enumerate(ordered):
        block.reading_order = i
    return ordered


def move_block_order(blocks: list[PdfBlock], block_id: str, new_order: int) -> list[PdfBlock]:
    ordered = sorted(blocks, key=lambda b: b.reading_order)
    target = next((b for b in ordered if b.id == block_id), None)
    if target is None:
        raise KeyError(block_id)
    ordered = [b for b in ordered if b.id != block_id]
    new_order = max(0, min(new_order, len(ordered)))
    ordered.insert(new_order, target)
    for i, block in enumerate(ordered):
        block.reading_order = i
    return ordered
