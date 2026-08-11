"""시험지 공통 레이아웃 프로필 — 2단·헤더·푸터."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

import fitz

from korean_exam_braille.app.pdf.models import PdfSpan

ColumnDetection = Literal["shared", "page_local", "single"]


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
    # shared: 문서 공통 거터 성공
    # page_local: 공통 실패 → 면마다 detect_column_boundary 사용
    # single: 1단으로 확정(명시적)
    column_detection: ColumnDetection = "shared"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PageLayoutProfile:
        detection = data.get("column_detection", "shared")
        if detection not in ("shared", "page_local", "single"):
            detection = "shared"
        return cls(
            page_width=float(data["page_width"]),
            page_height=float(data["page_height"]),
            column_cut_x=float(data["column_cut_x"]),
            header_bottom_y=float(data["header_bottom_y"]),
            footer_top_y=float(data["footer_top_y"]),
            left_column_right_x=float(data["left_column_right_x"]),
            right_column_left_x=float(data["right_column_left_x"]),
            column_detection=detection,  # type: ignore[arg-type]
        )

    def band_of_y(self, y: float) -> str:
        if y < self.header_bottom_y:
            return "header"
        if y >= self.footer_top_y:
            return "footer"
        return "body"

    def uses_page_local_columns(self) -> bool:
        return self.column_detection == "page_local"

    def uses_shared_columns(self) -> bool:
        return self.column_detection == "shared"

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


def _detect_vector_separator_bottom(page: fitz.Page) -> float | None:
    """본문 위 전폭에 가까운 가로 벡터 선의 y(하단)를 추정."""
    width = float(page.rect.width)
    height = float(page.rect.height)
    y_lo = height * 0.05
    y_hi = height * 0.22
    min_span = width * 0.55
    ys: list[float] = []
    for drawing in page.get_drawings():
        for item in drawing.get("items") or []:
            if not item or item[0] != "l":
                continue
            p1, p2 = item[1], item[2]
            xspan = abs(float(p2.x) - float(p1.x))
            yspan = abs(float(p2.y) - float(p1.y))
            y = (float(p1.y) + float(p2.y)) / 2
            if yspan <= 1.5 and xspan >= min_span and y_lo <= y <= y_hi:
                ys.append(y)
    return _median(ys) if ys else None


def _is_gutter_noise_span(span: PdfSpan, page_width: float) -> bool:
    """거터 추정에서 빼야 하는 전폭·가운데 머리글성 span."""
    text = (span.text or "").strip()
    if not text:
        return True
    x0, _, x1, _ = span.bbox
    width = x1 - x0
    mid = page_width * 0.5
    # 전폭에 가까운 제목
    if width > page_width * 0.45:
        return True
    # 페이지 중앙을 가로지르는 가운데 정렬 표제("국어영역" 등)
    if x0 < mid < x1 and width > page_width * 0.12:
        return True
    return False


def _body_gutter_from_spans(
    spans: list[PdfSpan],
    *,
    header_bottom: float,
    footer_top: float,
    page_width: float,
) -> tuple[float, float, float] | None:
    """본문 영역에서 (left_max_x, right_min_x, cut_x) 추정.

    역전·너무 좁은 거터는 None(실패)을 반환한다. 1단으로 단정하지 않는다.
    """
    body = [
        s
        for s in spans
        if header_bottom <= s.bbox[1] < footer_top
        and (s.text or "").strip()
        and not _is_gutter_noise_span(s, page_width)
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
        if len(left) < 2 or len(right) < 2:
            return None
        left_max = max(s.bbox[2] for s in left)
        right_min = min(s.bbox[0] for s in right)

    min_gap = max(12.0, page_width * 0.015)
    if right_min - left_max < min_gap:
        return None

    cut = (left_max + right_min) / 2
    return left_max, right_min, cut


def infer_layout_profile(
    doc: fitz.Document,
    *,
    sample_pages: int | None = None,
) -> PageLayoutProfile:
    """여러 면을 샘플링해 공통 2단·헤더·푸터 프로필을 만든다.

    공통 거터 추정에 실패하면 column_detection=\"page_local\"로 두고
    면 단위 경계 탐지로 넘긴다. 즉시 1단(cut≈오른쪽)으로 단정하지 않는다.
    """
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
        page = doc[idx]
        spans = _spans_from_page(page, idx + 1)
        sep = _detect_separator_bottom(spans)
        if sep is None:
            sep = _detect_vector_separator_bottom(page)
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
        # 거터 폭이 충분히 클 때만 문서 공통 2단으로 확정
        if right_min - left_max >= max(12.0, width * 0.015):
            column_cut = (left_max + right_min) / 2
            detection: ColumnDetection = "shared"
        else:
            left_max = width * 0.45
            right_min = width * 0.55
            column_cut = width * 0.5
            detection = "page_local"
    else:
        # 공통 거터 실패 → 면마다 재탐지 (1단으로 단정하지 않음)
        left_max = width * 0.45
        right_min = width * 0.55
        column_cut = width * 0.5
        detection = "page_local"

    return PageLayoutProfile(
        page_width=width,
        page_height=height,
        column_cut_x=column_cut,
        header_bottom_y=header_bottom,
        footer_top_y=footer_top,
        left_column_right_x=left_max,
        right_column_left_x=right_min,
        column_detection=detection,
    )
