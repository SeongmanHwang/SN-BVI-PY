"""보기 그래픽 → 선형 묵자: 박스 표선 + 향찰 2행 직렬화.

입체(글자 아래 밑줄·더 아래 원문자)를 합치지 않고 두 줄로 편다::

    [향찰 표기] <u>오</u>은 <u>수</u><u>을</u> <u>음</u><u>다</u>
    ⓐ ⓑ ⓒ ⓓ ⓔ

    박스 경계 → ──── 행 (점역 시 표선 !333…4)

원문자는 ``7a7``…(ⓐ…) 로 점역한다. 참고 BRF ``70a7``/‘a’ 는 쓰지 않는다.
"""

from __future__ import annotations

import re

from korean_exam_braille.app.pdf.boxes import iter_box_rects, line_mostly_in_box
from korean_exam_braille.app.pdf.models import BBox, PdfLine

_CIRCLED_LATIN = set("ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ")
_CIRCLED_RE = re.compile(r"[ⓐ-ⓩ]")

BOX_RULE_INK = "─" * 16

# 라벨 전용 행으로 볼 y 간격 (연속 행 병합)
_LABEL_LINE_Y_GAP = 18.0


def _union_bbox(boxes: list[BBox]) -> BBox:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _circled_chars(text: str) -> list[str]:
    return [ch for ch in text if ch in _CIRCLED_LATIN]


def _is_label_only_line(text: str) -> bool:
    """원문자·공백만 있는 행."""
    body = "".join(ch for ch in (text or "") if not ch.isspace())
    return bool(body) and all(ch in _CIRCLED_LATIN for ch in body)


def _has_underline_markup(text: str) -> bool:
    return "<u>" in (text or "")


def _strip_circled_from_text(text: str) -> tuple[str, list[str]]:
    """본문에서 원문자를 떼어 (남은 본문, 원문자 목록)."""
    labels: list[str] = []
    parts: list[str] = []
    for ch in text or "":
        if ch in _CIRCLED_LATIN:
            labels.append(ch)
        else:
            parts.append(ch)
    body = "".join(parts)
    body = " ".join(body.split()) if body.strip() else body
    return body, labels


def format_two_line_hyangchal(hanja_line: str, labels: list[str] | str) -> str:
    """향찰 2행 묵자 (검수·테스트용)."""
    if isinstance(labels, str):
        label_line = " ".join(_circled_chars(labels)) or labels.strip()
    else:
        label_line = " ".join(labels)
    return f"{hanja_line.rstrip()}\n{label_line}".rstrip()


def split_stacked_hyangchal_lines(lines: list[PdfLine]) -> list[PdfLine]:
    """한 행에 밑줄 본문+원문자가 섞이면 본문 행 / 원문자 행으로 나눈다."""
    if not lines:
        return lines
    out: list[PdfLine] = []
    seq = 0
    for ln in lines:
        text = ln.text or ""
        if not (_has_underline_markup(text) and _CIRCLED_RE.search(text)):
            out.append(ln)
            continue
        body, labels = _strip_circled_from_text(text)
        if not labels:
            out.append(ln)
            continue
        body_line = PdfLine(
            id=ln.id,
            text=body,
            bbox=ln.bbox,
            span_ids=list(ln.span_ids),
            page_number=ln.page_number,
            reading_order=ln.reading_order,
        )
        seq += 1
        y1 = ln.bbox[3]
        label_line = PdfLine(
            id=f"{ln.id}-labels-{seq}",
            text=" ".join(labels),
            bbox=(ln.bbox[0], y1, ln.bbox[2], y1 + 2.0),
            span_ids=[],
            page_number=ln.page_number,
            reading_order=ln.reading_order,
        )
        out.append(body_line)
        out.append(label_line)
    return out


def merge_circled_label_lines(lines: list[PdfLine]) -> list[PdfLine]:
    """가로로 흩어진 원문자 전용 행을 한 줄로 합친다 (ⓐ ⓑ ⓒ …)."""
    if not lines:
        return lines
    out: list[PdfLine] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not _is_label_only_line(ln.text):
            out.append(ln)
            i += 1
            continue
        run = [ln]
        j = i + 1
        while j < len(lines) and _is_label_only_line(lines[j].text):
            prev = run[-1]
            # 바로 아래·같은 밴드의 라벨 행만 병합 (본문이 끼면 중단)
            if lines[j].bbox[1] - prev.bbox[3] > _LABEL_LINE_Y_GAP:
                break
            run.append(lines[j])
            j += 1
        run_sorted = sorted(run, key=lambda L: (L.bbox[0], L.bbox[1]))
        labels: list[str] = []
        for piece in run_sorted:
            labels.extend(_circled_chars(piece.text))
        # 중복 없이 등장 순 유지
        seen: set[str] = set()
        ordered: list[str] = []
        for ch in labels:
            if ch not in seen:
                seen.add(ch)
                ordered.append(ch)
        merged = PdfLine(
            id=run[0].id,
            text=" ".join(ordered),
            bbox=_union_bbox([p.bbox for p in run]),
            span_ids=[sid for p in run for sid in p.span_ids],
            page_number=run[0].page_number,
            reading_order=run[0].reading_order,
        )
        out.append(merged)
        i = j

    for k, ln in enumerate(out):
        ln.reading_order = k
    return out


def insert_box_rule_lines(
    lines: list[PdfLine],
    boxes: list[BBox],
    *,
    page_number: int,
    rule_text: str = BOX_RULE_INK,
) -> list[PdfLine]:
    """박스에 속한 행 앞·뒤에 표선 묵자 행을 끼운다. 연속 중복 표선은 합친다."""
    if not lines or not boxes:
        return lines

    ordered_boxes = sorted(
        boxes,
        key=lambda b: ((b[2] - b[0]) * (b[3] - b[1]), b[1], b[0]),
    )

    before = [0] * len(lines)
    after = [0] * len(lines)
    for box in ordered_boxes:
        idxs = [i for i, ln in enumerate(lines) if line_mostly_in_box(ln.bbox, box)]
        if not idxs:
            continue
        before[idxs[0]] += 1
        after[idxs[-1]] += 1

    out: list[PdfLine] = []
    seq = 0

    def _rule_line(y: float, x0: float, x1: float) -> PdfLine:
        nonlocal seq
        seq += 1
        return PdfLine(
            id=f"p{page_number}-rule-{seq}",
            text=rule_text,
            bbox=(x0, y, x1, y + 1.0),
            span_ids=[],
            page_number=page_number,
            reading_order=0,
        )

    for i, ln in enumerate(lines):
        for _ in range(before[i]):
            out.append(_rule_line(ln.bbox[1] - 1.0, ln.bbox[0], ln.bbox[2]))
        out.append(ln)
        for _ in range(after[i]):
            out.append(_rule_line(ln.bbox[3] + 1.0, ln.bbox[0], ln.bbox[2]))

    compacted: list[PdfLine] = []
    for ln in out:
        if compacted and compacted[-1].text == rule_text and ln.text == rule_text:
            continue
        compacted.append(ln)

    for i, ln in enumerate(compacted):
        ln.reading_order = i
    return compacted


def linearize_page_graphics(page: object, lines: list[PdfLine]) -> list[PdfLine]:
    """향찰 2행 직렬화 + 박스 표선."""
    if not lines:
        return lines
    page_number = lines[0].page_number
    lines = split_stacked_hyangchal_lines(lines)
    lines = merge_circled_label_lines(lines)
    boxes = iter_box_rects(page)
    return insert_box_rule_lines(lines, boxes, page_number=page_number)
