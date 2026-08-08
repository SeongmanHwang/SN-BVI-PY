"""생성 BRF ↔ 참고 BRF 검토 — 참고 면 기준 창 배정 비교.

참고 BRF는 이미 면(`\\x0c`)으로 나뉜다. 각 참고 면에 대해
아직 배정되지 않은 생성 구간에서 **최장 연속 일치**를 찾고,
그 일치를 앵커로 참고 면과 **같은 내용 길이**(공백·줄바꿈 제외)의
생성 창을 잘라 짝짓는다.
비교·앵커 탐색 시 공백·줄바꿈·면구분 문자는 무시한다.
창끼리 겹치지 않으며, 어떤 면에도 안 들어간 생성 구간은 누락으로 집계한다.
면 안 글자 음영은 길이 하한 이상 최장 일치 앵커를 최대 5개만 인정한다.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from difflib import Match, SequenceMatcher

from korean_exam_braille.app.brf.ascii_braille import ascii_to_unicode, normalize_brf_ascii
from korean_exam_braille.app.brf.compare import compare_brf_texts
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line

DEFAULT_MIN_ANCHOR = 16
DEFAULT_MAX_ANCHORS = 5
_PAGE_BREAK_MARK = "── 면 구분 ──"
# 비교 시 무시: ASCII 공백류 + 면 구분 + 유니코드 공백
_IGNORE_CHARS = frozenset(" \t\r\n\x0c\u00a0\u3000\u2800")

ProgressCallback = Callable[[int, int, str], None]


def _is_ignorable(ch: str) -> bool:
    return ch in _IGNORE_CHARS or ch.isspace()


def compact_index_map(text: str) -> tuple[str, list[int]]:
    """공백·줄바꿈을 뺀 문자열과 compact→원문 인덱스 맵."""
    chars: list[str] = []
    indices: list[int] = []
    for i, ch in enumerate(text):
        if _is_ignorable(ch):
            continue
        chars.append(ch)
        indices.append(i)
    return "".join(chars), indices


def original_range_to_compact(
    indices: list[int], lo: int, hi: int
) -> tuple[int, int]:
    """원문 [lo, hi) → compact [c_lo, c_hi)."""
    c_lo = 0
    while c_lo < len(indices) and indices[c_lo] < lo:
        c_lo += 1
    c_hi = c_lo
    while c_hi < len(indices) and indices[c_hi] < hi:
        c_hi += 1
    return c_lo, c_hi


def compact_span_to_original(
    indices: list[int], start: int, size: int
) -> tuple[int, int]:
    """compact [start, start+size) → 원문 [lo, hi)."""
    if size <= 0 or not indices or start >= len(indices):
        return 0, 0
    end = min(start + size, len(indices))
    if end <= start:
        return 0, 0
    return indices[start], indices[end - 1] + 1


def brf_text_to_display_pages(brf_text: str) -> list[dict[str, object]]:
    """BRF 텍스트 → 면별 유니코드 점자·역점역."""
    pages: list[dict[str, object]] = []
    for index, page in enumerate(brf_text.split("\x0c"), start=1):
        raw_lines = page.splitlines()
        if not any(line.strip() for line in raw_lines):
            continue
        ascii_lines: list[str] = []
        uni_lines: list[str] = []
        rev_lines: list[str] = []
        for line in raw_lines:
            if line.strip() == "":
                ascii_lines.append("")
                uni_lines.append("")
                rev_lines.append("")
            else:
                ascii_lines.append(normalize_brf_ascii(line))
                uni_lines.append(ascii_to_unicode(line))
                rev_lines.append(reverse_translate_line(line))
        pages.append(
            {
                "index": index,
                "ascii_lines": ascii_lines,
                "unicode_lines": uni_lines,
                "reverse_lines": rev_lines,
                "ascii": "\n".join(ascii_lines),
                "unicode": "\n".join(uni_lines),
                "reverse": "\n".join(rev_lines),
            }
        )
    return pages


def flatten_brf_document(brf_text: str) -> dict[str, object]:
    """BRF 전체를 면 구분(`\\x0c`)이 섞인 한 문자열로 펼친다."""
    pages = brf_text_to_display_pages(brf_text)
    ascii_parts: list[str] = []
    uni_parts: list[str] = []
    for i, page in enumerate(pages):
        if i:
            ascii_parts.append("\x0c")
            uni_parts.append("\x0c")
        ascii_parts.append(str(page["ascii"]))
        uni_parts.append(str(page["unicode"]))
    ascii_flat = "".join(ascii_parts)
    uni_flat = "".join(uni_parts)
    return {
        "pages": pages,
        "page_count": len(pages),
        "ascii": ascii_flat,
        "unicode": uni_flat,
    }


def flatten_reference_document(brf_text: str) -> dict[str, object]:
    """하위 호환 — ``flatten_brf_document``와 동일."""
    return flatten_brf_document(brf_text)


@dataclass(frozen=True)
class AnchorSpan:
    a: int
    b: int
    size: int

    @property
    def a_end(self) -> int:
        return self.a + self.size

    @property
    def b_end(self) -> int:
        return self.b + self.size


def free_intervals(claimed: list[bool]) -> list[tuple[int, int]]:
    """미배정(False) 연속 구간 목록."""
    out: list[tuple[int, int]] = []
    n = len(claimed)
    i = 0
    while i < n:
        if claimed[i]:
            i += 1
            continue
        j = i + 1
        while j < n and not claimed[j]:
            j += 1
        out.append((i, j))
        i = j
    return out


def find_longest_anchors(
    a: str,
    b: str,
    *,
    min_match: int = DEFAULT_MIN_ANCHOR,
    max_anchors: int = DEFAULT_MAX_ANCHORS,
) -> list[AnchorSpan]:
    """공백·줄바꿈을 무시한 뒤 최장 연속 일치를 최대 ``max_anchors``개 고른다.

    반환 span의 a/b/size는 **압축 문자열** 기준이다.
    """
    a_c, _ = compact_index_map(a)
    b_c, _ = compact_index_map(b)
    if not a_c or not b_c or max_anchors <= 0 or min_match <= 0:
        return []
    matcher = SequenceMatcher(a=a_c, b=b_c, autojunk=False)
    regions: list[tuple[int, int, int, int]] = [(0, len(a_c), 0, len(b_c))]
    anchors: list[AnchorSpan] = []

    while regions and len(anchors) < max_anchors:
        best: Match | None = None
        best_idx = -1
        for idx, (alo, ahi, blo, bhi) in enumerate(regions):
            if alo >= ahi or blo >= bhi:
                continue
            match = matcher.find_longest_match(alo, ahi, blo, bhi)
            if match.size < min_match:
                continue
            if best is None or match.size > best.size:
                best = match
                best_idx = idx
        if best is None or best_idx < 0:
            break
        alo, ahi, blo, bhi = regions.pop(best_idx)
        anchors.append(AnchorSpan(a=best.a, b=best.b, size=best.size))
        left = (alo, best.a, blo, best.b)
        right = (best.a + best.size, ahi, best.b + best.size, bhi)
        if left[0] < left[1] and left[2] < left[3]:
            regions.append(left)
        if right[0] < right[1] and right[2] < right[3]:
            regions.append(right)

    anchors.sort(key=lambda span: span.a)
    return anchors


def char_mismatch_masks(
    a: str,
    b: str,
    *,
    min_match: int = DEFAULT_MIN_ANCHOR,
    max_anchors: int = DEFAULT_MAX_ANCHORS,
) -> tuple[list[bool], list[bool]]:
    """앵커(최대 ``max_anchors``개)만 일치, 나머지 True=불일치.

    공백·줄바꿈은 비교에서 빼고, 표시상으로는 불일치 음영을 치지 않는다.
    """
    a_mask = [True] * len(a)
    b_mask = [True] * len(b)
    if not a and not b:
        return [], []
    for i, ch in enumerate(a):
        if _is_ignorable(ch):
            a_mask[i] = False
    for i, ch in enumerate(b):
        if _is_ignorable(ch):
            b_mask[i] = False

    a_c, a_map = compact_index_map(a)
    b_c, b_map = compact_index_map(b)
    if not a_c and not b_c:
        return a_mask, b_mask

    for span in find_longest_anchors(
        a, b, min_match=min_match, max_anchors=max_anchors
    ):
        for offset in range(span.size):
            a_mask[a_map[span.a + offset]] = False
            b_mask[b_map[span.b + offset]] = False
    return a_mask, b_mask


def _longest_match_in_free(
    page: str,
    source: str,
    claimed: list[bool],
    *,
    min_match: int,
) -> tuple[Match, list[int], list[int]] | None:
    """미배정 원문 구간에서 공백 무시 최장 일치. Match는 compact 좌표."""
    page_c, page_map = compact_index_map(page)
    source_c, source_map = compact_index_map(source)
    if len(page_c) < min_match or not source_c:
        return None
    matcher = SequenceMatcher(a=page_c, b=source_c, autojunk=False)
    best: Match | None = None
    for lo, hi in free_intervals(claimed):
        c_lo, c_hi = original_range_to_compact(source_map, lo, hi)
        if c_hi - c_lo < min_match:
            continue
        match = matcher.find_longest_match(0, len(page_c), c_lo, c_hi)
        if match.size < min_match:
            continue
        if best is None or match.size > best.size:
            best = match
    if best is None:
        return None
    return best, page_map, source_map


def _place_same_length_window(
    page_compact_len: int,
    match: Match,
    source_map: list[int],
    claimed: list[bool],
) -> tuple[int, int] | None:
    """compact 일치 앵커 기준 — 참고 면과 같은 내용 길이의 생성 원문 창."""
    if match.size <= 0 or match.b >= len(source_map):
        return None
    match_orig_b = source_map[match.b]
    match_orig_end = source_map[match.b + match.size - 1] + 1
    containing: tuple[int, int] | None = None
    for lo, hi in free_intervals(claimed):
        if lo <= match_orig_b and match_orig_end <= hi:
            containing = (lo, hi)
            break
    if containing is None:
        return None
    lo, hi = containing
    free_c_lo, free_c_hi = original_range_to_compact(source_map, lo, hi)
    c_start = match.b - match.a
    c_end = c_start + page_compact_len
    c_start = max(c_start, free_c_lo)
    c_end = min(c_end, free_c_hi)
    if c_end <= c_start:
        return None
    return compact_span_to_original(source_map, c_start, c_end - c_start)


def _claim(claimed: list[bool], start: int, end: int) -> None:
    for i in range(start, end):
        claimed[i] = True


def _reverse_from_ascii_slice(ascii_slice: str) -> str:
    """ASCII 창 → 역점역 표시 문자열 (면 구분은 표식 한 줄)."""
    out_lines: list[str] = []
    for pi, part in enumerate(ascii_slice.split("\x0c")):
        if pi:
            out_lines.append(_PAGE_BREAK_MARK)
        for line in part.split("\n"):
            if line.strip() == "":
                out_lines.append("")
            else:
                out_lines.append(reverse_translate_line(line))
    return "\n".join(out_lines)


def _display_with_page_breaks(uni_slice: str) -> str:
    return uni_slice.replace("\x0c", _PAGE_BREAK_MARK)


def _empty_line() -> dict[str, object]:
    return {"text": "", "mismatch": [], "line_equal": False, "page_break": False}


def _line_from_mask(text: str, mask: list[bool]) -> dict[str, object]:
    if len(mask) != len(text):
        mask = (mask + [True] * len(text))[: len(text)]
    if not text:
        return _empty_line()
    return {
        "text": text,
        "mismatch": mask,
        "line_equal": not any(mask),
        "page_break": text == _PAGE_BREAK_MARK,
    }


def _split_masked_lines(text: str, mask: list[bool]) -> list[dict[str, object]]:
    if not text:
        return []
    lines: list[dict[str, object]] = []
    start = 0
    for i, ch in enumerate(text):
        if ch == "\n":
            lines.append(_line_from_mask(text[start:i], mask[start:i]))
            start = i + 1
    lines.append(_line_from_mask(text[start:], mask[start:]))
    return lines


def _annotate_pair(
    gen_text: str,
    ref_text: str,
    *,
    min_match: int,
    max_anchors: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[AnchorSpan]]:
    anchors = find_longest_anchors(
        gen_text, ref_text, min_match=min_match, max_anchors=max_anchors
    )
    g_mask, r_mask = char_mismatch_masks(
        gen_text, ref_text, min_match=min_match, max_anchors=max_anchors
    )
    return (
        _split_masked_lines(gen_text, g_mask),
        _split_masked_lines(ref_text, r_mask),
        anchors,
    )


def assign_generated_windows(
    ref_pages: list[dict[str, object]],
    gen_unicode: str,
    gen_ascii: str,
    *,
    min_match: int = DEFAULT_MIN_ANCHOR,
    on_progress: ProgressCallback | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """참고 면마다 미배정 생성 구간에서 창을 배정. 겹침 없음, 생성 누락 구간 반환."""
    claimed = [False] * len(gen_unicode)
    assignments: list[dict[str, object]] = []
    total = len(ref_pages)

    for page_i, page in enumerate(ref_pages):
        if on_progress is not None:
            on_progress(
                page_i,
                total * 2,
                f"생성 구간 배정 중 — 참고 {page['index']}면 ({page_i + 1}/{total})",
            )
        ref_uni = str(page["unicode"])
        ref_rev = str(page["reverse"])
        page_index = int(page["index"])
        found = _longest_match_in_free(
            ref_uni, gen_unicode, claimed, min_match=min_match
        )
        if found is None:
            assignments.append(
                {
                    "index": page_index,
                    "matched": False,
                    "ref_unicode": ref_uni,
                    "ref_reverse": ref_rev,
                    "gen_unicode": "",
                    "gen_reverse": "",
                    "gen_start": None,
                    "gen_end": None,
                    "anchor_size": 0,
                    "window_len": 0,
                    "clipped": False,
                }
            )
            continue

        match, page_map, gen_map = found
        page_compact_len = len(page_map)
        window = _place_same_length_window(
            page_compact_len, match, gen_map, claimed
        )
        if window is None:
            assignments.append(
                {
                    "index": page_index,
                    "matched": False,
                    "ref_unicode": ref_uni,
                    "ref_reverse": ref_rev,
                    "gen_unicode": "",
                    "gen_reverse": "",
                    "gen_start": None,
                    "gen_end": None,
                    "anchor_size": match.size,
                    "window_len": 0,
                    "clipped": False,
                }
            )
            continue

        start, end = window
        _claim(claimed, start, end)
        gen_uni_slice = gen_unicode[start:end]
        gen_ascii_slice = (
            gen_ascii[start:end] if len(gen_ascii) == len(gen_unicode) else ""
        )
        if gen_ascii_slice:
            gen_rev = _reverse_from_ascii_slice(gen_ascii_slice)
        else:
            gen_rev = _display_with_page_breaks(gen_uni_slice)
        gen_compact_len = len(compact_index_map(gen_uni_slice)[1])
        assignments.append(
            {
                "index": page_index,
                "matched": True,
                "ref_unicode": ref_uni,
                "ref_reverse": ref_rev,
                "gen_unicode": _display_with_page_breaks(gen_uni_slice),
                "gen_reverse": gen_rev,
                "gen_start": start,
                "gen_end": end,
                "anchor_size": match.size,
                "anchor_ref": match.a,
                "anchor_gen": match.b,
                "window_len": end - start,
                "clipped": gen_compact_len != page_compact_len,
            }
        )

    unassigned: list[dict[str, object]] = []
    for lo, hi in free_intervals(claimed):
        size = hi - lo
        if size <= 0:
            continue
        preview = _display_with_page_breaks(gen_unicode[lo:hi])[:80]
        if not preview.strip() and not any(
            ch not in "\n\r\t \x0c" for ch in gen_unicode[lo:hi]
        ):
            continue
        unassigned.append(
            {
                "start": lo,
                "end": hi,
                "size": size,
                "preview": preview,
            }
        )
    return assignments, unassigned


def build_review_pages(
    generated_brf: str,
    reference_brf: str,
    *,
    min_match: int = DEFAULT_MIN_ANCHOR,
    max_anchors: int = DEFAULT_MAX_ANCHORS,
    on_progress: ProgressCallback | None = None,
) -> dict[str, object]:
    """참고 면 기준 창 배정 + 면 안 최장일치(최대 5) 음영."""
    ref_pages = brf_text_to_display_pages(reference_brf)
    gen_flat = flatten_brf_document(generated_brf)
    total_pages = len(ref_pages)
    total_steps = max(total_pages * 2, 1)

    if on_progress is not None:
        on_progress(0, total_steps, "비교 준비 중…")

    cmp = compare_brf_texts(generated_brf, reference_brf)

    assignments, unassigned = assign_generated_windows(
        ref_pages,
        str(gen_flat["unicode"]),
        str(gen_flat["ascii"]),
        min_match=min_match,
        on_progress=on_progress,
    )

    review_pages: list[dict[str, object]] = []
    for asg_i, asg in enumerate(assignments):
        if on_progress is not None:
            on_progress(
                total_pages + asg_i,
                total_steps,
                f"면 안 차이 표시 중 — 참고 {asg['index']}면 ({asg_i + 1}/{total_pages})",
            )
        gen_uni = str(asg["gen_unicode"])
        ref_uni = str(asg["ref_unicode"])
        gen_rev = str(asg["gen_reverse"])
        ref_rev = str(asg["ref_reverse"])
        if asg["matched"] and gen_uni:
            g_uni, r_uni, uni_anchors = _annotate_pair(
                gen_uni, ref_uni, min_match=min_match, max_anchors=max_anchors
            )
            g_rev, r_rev, rev_anchors = _annotate_pair(
                gen_rev, ref_rev, min_match=min_match, max_anchors=max_anchors
            )
        else:
            g_uni = []
            r_uni = _split_masked_lines(ref_uni, [True] * len(ref_uni))
            g_rev = []
            r_rev = _split_masked_lines(ref_rev, [True] * len(ref_rev))
            uni_anchors = []
            rev_anchors = []

        review_pages.append(
            {
                "index": asg["index"],
                "matched": asg["matched"],
                "clipped": asg["clipped"],
                "anchor_size": asg["anchor_size"],
                "gen_start": asg["gen_start"],
                "gen_end": asg["gen_end"],
                "window_len": asg["window_len"],
                "generated": {
                    "unicode_lines": g_uni,
                    "reverse_lines": g_rev,
                },
                "reference": {
                    "unicode_lines": r_uni,
                    "reverse_lines": r_rev,
                },
                "anchors": {
                    "unicode": [
                        {"a": s.a, "b": s.b, "size": s.size} for s in uni_anchors
                    ],
                    "reverse": [
                        {"a": s.a, "b": s.b, "size": s.size} for s in rev_anchors
                    ],
                },
            }
        )

    if on_progress is not None:
        on_progress(total_steps, total_steps, "비교 완료")

    matched_n = sum(1 for p in review_pages if p["matched"])
    unassigned_chars = sum(int(g["size"]) for g in unassigned)
    return {
        "review_pages": review_pages,
        "unassigned_generated": unassigned,
        "assignment_summary": {
            "generated_pages": gen_flat["page_count"],
            "reference_pages": len(ref_pages),
            "matched_pages": matched_n,
            "unmatched_pages": len(ref_pages) - matched_n,
            "unassigned_spans": len(unassigned),
            "unassigned_chars": unassigned_chars,
            "min_match": min_match,
            "max_anchors": max_anchors,
        },
        "compare": {
            "generated_pages": cmp.generated_pages,
            "reference_pages": cmp.reference_pages,
            "generated_lines": cmp.generated_lines,
            "reference_lines": cmp.reference_lines,
            "matched_lines": cmp.matched_lines,
            "line_match_ratio": cmp.line_match_ratio,
            "cell_equal": cmp.cell_equal,
            "cell_total": cmp.cell_total,
            "cell_match_ratio": cmp.cell_match_ratio,
            "diff_count": len(cmp.diffs),
        },
    }


def build_review_document(
    generated_brf: str,
    reference_brf: str,
    *,
    min_match: int = DEFAULT_MIN_ANCHOR,
    max_anchors: int = DEFAULT_MAX_ANCHORS,
) -> dict[str, object]:
    """하위 호환 — 면 배정 결과를 그대로 반환."""
    return build_review_pages(
        generated_brf,
        reference_brf,
        min_match=min_match,
        max_anchors=max_anchors,
    )
