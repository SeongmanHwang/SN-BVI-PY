"""시험지 공통 레이아웃 프로필 — 2단·헤더·푸터."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import fitz

from korean_exam_braille.app.pdf.models import PdfSpan


@dataclass(frozen=True)
class PageLayoutProfile:
    """문서 전체에 공유하는 면 레이아웃."""

    page_width: float
    page_height: float
    column_cut_x: float
    header_bottom_y: float
    footer_top_y: float
    left_column_right_x: float
    right_column_left_x: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PageLayoutProfile:
        return cls(
            page_width=float(data["page_width"]),
            page_height=float(data["page_height"]),
            column_cut_x=float(data["column_cut_x"]),
            header_bottom_y=float(data["header_bottom_y"]),
            footer_top_y=float(data["footer_top_y"]),
            left_column_right_x=float(data["left_column_right_x"]),
            right_column_left_x=float(data["right_column_left_x"]),
        )

    def band_of_y(self, y: float) -> str:
        if y < self.header_bottom_y:
            return "header"
        if y >= self.footer_top_y:
            return "footer"
        return "body"

    def column_of_x(self, x_mid: float, *, span_width: float = 0.0) -> int:
        """-1=전폭/헤더성, 0=좌, 1=우."""
        if span_width > self.page_width * 0.50:
            return -1
        return 0 if x_mid < self.column_cut_x else 1


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        raise ValueError("empty")
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _spans_from_page(page: fitz.Page, page_number: int) -> list[PdfSpan]:
    """extractor와 순환 import를 피하기 위해 여기서 직접 추출."""
    spans: list[PdfSpan] = []
    data = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
    index = 0
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text") or ""
                if text == "":
                    continue
                bbox = tuple(float(x) for x in span["bbox"])
                spans.append(
                    PdfSpan(
                        id=f"p{page_number}-s{index}",
                        text=text,
                        bbox=(bbox[0], bbox[1], bbox[2], bbox[3]),
                        font=str(span.get("font", "")),
                        font_size=float(span.get("size", 0.0)),
                        is_bold=bool(int(span.get("flags", 0)) & 16),
                        page_number=page_number,
                        extraction_index=index,
                    )
                )
                index += 1
    return spans


def _detect_separator_bottom(spans: list[PdfSpan]) -> float | None:
    bottoms: list[float] = []
    for span in spans:
        text = (span.text or "").strip()
        if len(text) >= 8 and (
            "━" in text
            or "─" in text
            or (len(set(text)) <= 2 and all(ch in "━─_-=*" for ch in text))
        ):
            # 상단 구분선만
            if span.bbox[1] < 250:
                bottoms.append(span.bbox[3])
    return _median(bottoms) if bottoms else None


def _body_gutter_from_spans(
    spans: list[PdfSpan],
    *,
    header_bottom: float,
    footer_top: float,
    page_width: float,
) -> tuple[float, float, float] | None:
    """본문 영역에서 (left_max_x, right_min_x, cut_x) 추정."""
    body = [
        s
        for s in spans
        if header_bottom <= s.bbox[1] < footer_top and (s.text or "").strip()
    ]
    if len(body) < 4:
        return None

    # 초기 cut 후보: 페이지 중앙
    rough_cut = page_width * 0.5
    left = [s for s in body if (s.bbox[0] + s.bbox[2]) / 2 < rough_cut]
    right = [s for s in body if (s.bbox[0] + s.bbox[2]) / 2 >= rough_cut]
    if len(left) < 2 or len(right) < 2:
        return None

    left_max = max(s.bbox[2] for s in left)
    right_min = min(s.bbox[0] for s in right)
    if right_min <= left_max:
        # 겹치면 mid gap으로 재시도
        mids = sorted((s.bbox[0] + s.bbox[2]) / 2 for s in body)
        best_gap = 0.0
        best_cut = rough_cut
        for a, b in zip(mids, mids[1:]):
            gap = b - a
            cut = (a + b) / 2
            if page_width * 0.35 <= cut <= page_width * 0.65 and gap > best_gap:
                best_gap = gap
                best_cut = cut
        left = [s for s in body if (s.bbox[0] + s.bbox[2]) / 2 < best_cut]
        right = [s for s in body if (s.bbox[0] + s.bbox[2]) / 2 >= best_cut]
        if not left or not right:
            return None
        left_max = max(s.bbox[2] for s in left)
        right_min = min(s.bbox[0] for s in right)

    cut = (left_max + right_min) / 2
    return left_max, right_min, cut


def infer_layout_profile(
    doc: fitz.Document,
    *,
    sample_pages: int | None = None,
) -> PageLayoutProfile:
    """여러 면을 샘플링해 공통 2단·헤더·푸터 프로필을 만든다."""
    if doc.page_count < 1:
        raise ValueError("empty document")

    page0 = doc[0]
    width = float(page0.rect.width)
    height = float(page0.rect.height)

    n = doc.page_count if sample_pages is None else min(sample_pages, doc.page_count)
    # 표지가 달라도 본문 면(2페이지~)을 우선 샘플
    indices = list(range(doc.page_count))
    if doc.page_count >= 3:
        preferred = list(range(1, doc.page_count))  # 0-based: skip first if possible
        indices = (preferred + [0])[:n]
    else:
        indices = indices[:n]

    sep_bottoms: list[float] = []
    gutters: list[tuple[float, float, float]] = []
    footer_ys: list[float] = []

    # 1차: 푸터는 하단 8%에서 반복되는 작은 숫자 대역
    rough_footer = height * 0.90
    for idx in indices:
        spans = _spans_from_page(doc[idx], idx + 1)
        sep = _detect_separator_bottom(spans)
        if sep is not None:
            sep_bottoms.append(sep)
        for span in spans:
            if span.bbox[1] >= rough_footer:
                footer_ys.append(span.bbox[1])

    header_bottom = _median(sep_bottoms) if sep_bottoms else height * 0.06
    footer_top = min(footer_ys) if footer_ys else height * 0.96
    # 본문과 푸터 사이 여유
    footer_top = max(footer_top - 4.0, header_bottom + 50.0)

    for idx in indices:
        spans = _spans_from_page(doc[idx], idx + 1)
        gutter = _body_gutter_from_spans(
            spans,
            header_bottom=header_bottom,
            footer_top=footer_top,
            page_width=width,
        )
        if gutter:
            gutters.append(gutter)

    if gutters:
        left_max = _median([g[0] for g in gutters])
        right_min = _median([g[1] for g in gutters])
        # 거터 폭이 충분히 클 때만 2단으로 확정
        if right_min - left_max >= max(12.0, width * 0.015):
            column_cut = (left_max + right_min) / 2
        else:
            left_max = width * 0.95
            right_min = width * 0.98
            column_cut = width * 0.96
    else:
        # 단일 단 폴백: 거의 모든 본문을 좌열로
        left_max = width * 0.95
        right_min = width * 0.98
        column_cut = width * 0.96

    return PageLayoutProfile(
        page_width=width,
        page_height=height,
        column_cut_x=column_cut,
        header_bottom_y=header_bottom,
        footer_top_y=footer_top,
        left_column_right_x=left_max,
        right_column_left_x=right_min,
    )
