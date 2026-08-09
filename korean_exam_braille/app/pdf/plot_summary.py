"""중략 줄거리 구간 — 표지 + 글꼴·크기 런 끝 표시."""

from __future__ import annotations

import re
from collections import Counter

from korean_exam_braille.app.common.plot_summary_markup import PLOT_SUMMARY_END_INK
from korean_exam_braille.app.pdf.models import PdfLine, PdfSpan

# [중략 부분의 줄거리] / …줄거리] 등 표지
_CUE_RE = re.compile(r"\[?\s*중략[^\]]*줄거리\s*\]|줄거리\s*\]")
_SIZE_TOL = 0.75
_MAX_Y_GAP = 28.0


def _norm_font(name: str) -> str:
    base = (name or "").split("+")[-1]
    lower = base.lower()
    lower = re.sub(r"[-_]?(bold|italic|regular|medium|light|mt).*$", "", lower)
    return lower.strip()


def _font_family_bucket(name: str) -> str:
    n = _norm_font(name)
    if any(k in n for k in ("dotum", "gulim", "gothic", "malgun", "sans", "arial", "helv")):
        return "sans"
    if any(k in n for k in ("batang", "myeong", "serif", "times", "roman")):
        return "serif"
    return n or "unknown"


def _line_style(
    line: PdfLine, by_id: dict[str, PdfSpan]
) -> tuple[str, float] | None:
    """행 지배 글꼴 버킷·크기 (문자 수 가중)."""
    weights: Counter[tuple[str, float]] = Counter()
    for sid in line.span_ids:
        span = by_id.get(sid)
        if span is None or not (span.text or "").strip():
            continue
        size = round(float(span.font_size), 2)
        key = (_font_family_bucket(span.font), size)
        weights[key] += max(len(span.text.replace(" ", "")), 1)
    if not weights:
        return None
    (family, size), _ = weights.most_common(1)[0]
    return family, size


def _styles_match(
    seed: tuple[str, float], other: tuple[str, float] | None
) -> bool:
    if other is None:
        return False
    if seed[0] != other[0]:
        return False
    return abs(seed[1] - other[1]) <= _SIZE_TOL


def _has_cue(text: str) -> bool:
    return bool(_CUE_RE.search(text or ""))


def annotate_plot_summary_lines(
    lines: list[PdfLine],
    spans: list[PdfSpan],
    *,
    page_number: int,
) -> list[PdfLine]:
    """표지 줄부터 동일 글씨체 런 끝에 ``[줄거리 끝]`` 행을 삽입한다.

    시작 묵자 표지는 PDF에 이미 있는 경우가 많아 넣지 않는다.
    """
    if not lines or not spans:
        return lines

    by_id = {s.id: s for s in spans}
    styles = [_line_style(ln, by_id) for ln in lines]
    end_after: set[int] = set()

    i = 0
    n = len(lines)
    while i < n:
        if not _has_cue(lines[i].text or ""):
            i += 1
            continue
        seed = styles[i]
        if seed is None:
            i += 1
            continue
        last = i
        j = i + 1
        while j < n:
            prev = lines[j - 1]
            cur = lines[j]
            gap = cur.bbox[1] - prev.bbox[3]
            if gap > _MAX_Y_GAP:
                break
            if not _styles_match(seed, styles[j]):
                break
            last = j
            j += 1
        end_after.add(last)
        i = last + 1

    if not end_after:
        return lines

    out: list[PdfLine] = []
    seq = 0
    for idx, ln in enumerate(lines):
        out.append(ln)
        if idx not in end_after:
            continue
        # 이미 붙어 있으면 중복 삽입 안 함
        if ln.text.strip() == PLOT_SUMMARY_END_INK:
            continue
        if idx + 1 < n and (lines[idx + 1].text or "").strip() == PLOT_SUMMARY_END_INK:
            continue
        seq += 1
        y = ln.bbox[3] + 0.5
        out.append(
            PdfLine(
                id=f"p{page_number}-plot-end-{seq}",
                text=PLOT_SUMMARY_END_INK,
                bbox=(ln.bbox[0], y, ln.bbox[2], y + 1.0),
                span_ids=[],
                page_number=page_number,
                reading_order=0,
            )
        )

    for k, line in enumerate(out):
        line.reading_order = k
    return out
