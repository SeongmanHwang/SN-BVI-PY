"""PDF 물리 구조 모델."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from korean_exam_braille.app.pdf.bracket_groups import BracketGroup

BBox = tuple[float, float, float, float]


@dataclass
class PdfSpan:
    """글자·단어 단위 텍스트 조각."""

    id: str
    text: str
    bbox: BBox
    font: str
    font_size: float
    is_bold: bool
    page_number: int
    extraction_index: int
    is_underline: bool = False
    # 부분 밑줄: [start, end) 문자 오프셋. 글자 bbox가 있을 때만 채움.
    underline_ranges: list[tuple[int, int]] = field(default_factory=list)
    # 추출 시 rawdict 글자 bbox (표시·부분 강조용). 직렬화 시 생략 가능.
    char_bboxes: list[BBox] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "bbox": list(self.bbox),
            "font": self.font,
            "font_size": self.font_size,
            "is_bold": self.is_bold,
            "is_underline": self.is_underline,
            "underline_ranges": [list(r) for r in self.underline_ranges],
            "page_number": self.page_number,
            "extraction_index": self.extraction_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PdfSpan:
        bbox = data["bbox"]
        ranges_raw = data.get("underline_ranges") or []
        ranges: list[tuple[int, int]] = []
        for r in ranges_raw:
            if isinstance(r, (list, tuple)) and len(r) >= 2:
                ranges.append((int(r[0]), int(r[1])))
        return cls(
            id=str(data["id"]),
            text=str(data["text"]),
            bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
            font=str(data.get("font", "")),
            font_size=float(data.get("font_size", 0.0)),
            is_bold=bool(data.get("is_bold", False)),
            page_number=int(data["page_number"]),
            extraction_index=int(data.get("extraction_index", 0)),
            is_underline=bool(data.get("is_underline", False)),
            underline_ranges=ranges,
        )


@dataclass
class PdfLine:
    id: str
    text: str
    bbox: BBox
    span_ids: list[str]
    page_number: int
    reading_order: int = 0
    # 오른쪽 여백 꺾인 괄호 소속 — 예: "[A]"
    bracket_label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "bbox": list(self.bbox),
            "span_ids": list(self.span_ids),
            "page_number": self.page_number,
            "reading_order": self.reading_order,
            "bracket_label": self.bracket_label,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PdfLine:
        bbox = data["bbox"]
        return cls(
            id=str(data["id"]),
            text=str(data["text"]),
            bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
            span_ids=list(data.get("span_ids") or []),
            page_number=int(data["page_number"]),
            reading_order=int(data.get("reading_order", 0)),
            bracket_label=data.get("bracket_label"),
        )


@dataclass
class PdfBlock:
    id: str
    text: str
    bbox: BBox
    line_ids: list[str]
    page_number: int
    reading_order: int = 0
    candidate_tags: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "bbox": list(self.bbox),
            "line_ids": list(self.line_ids),
            "page_number": self.page_number,
            "reading_order": self.reading_order,
            "candidate_tags": list(self.candidate_tags),
            "tags": list(self.tags),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PdfBlock:
        bbox = data["bbox"]
        return cls(
            id=str(data["id"]),
            text=str(data["text"]),
            bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
            line_ids=list(data.get("line_ids") or []),
            page_number=int(data["page_number"]),
            reading_order=int(data.get("reading_order", 0)),
            candidate_tags=list(data.get("candidate_tags") or []),
            tags=list(data.get("tags") or []),
            notes=data.get("notes"),
        )


@dataclass
class PdfPageStructure:
    page_number: int  # 1-based
    width: float
    height: float
    spans: list[PdfSpan] = field(default_factory=list)
    lines: list[PdfLine] = field(default_factory=list)
    blocks: list[PdfBlock] = field(default_factory=list)
    bracket_groups: list[BracketGroup] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_number": self.page_number,
            "width": self.width,
            "height": self.height,
            "spans": [s.to_dict() for s in self.spans],
            "lines": [ln.to_dict() for ln in self.lines],
            "blocks": [b.to_dict() for b in self.blocks],
            "bracket_groups": [
                g.to_dict() if hasattr(g, "to_dict") else g for g in self.bracket_groups
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PdfPageStructure:
        from korean_exam_braille.app.pdf.bracket_groups import BracketGroup

        return cls(
            page_number=int(data["page_number"]),
            width=float(data["width"]),
            height=float(data["height"]),
            spans=[PdfSpan.from_dict(x) for x in data.get("spans", [])],
            lines=[PdfLine.from_dict(x) for x in data.get("lines", [])],
            blocks=[PdfBlock.from_dict(x) for x in data.get("blocks", [])],
            bracket_groups=[
                BracketGroup.from_dict(x) for x in data.get("bracket_groups", [])
            ],
        )


@dataclass
class PdfDocumentStructure:
    source_path: str | None = None
    page_count: int = 0
    pages: list[PdfPageStructure] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_page(self, page_number: int) -> PdfPageStructure:
        for page in self.pages:
            if page.page_number == page_number:
                return page
        raise IndexError(f"page {page_number} not found")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "page_count": self.page_count,
            "metadata": dict(self.metadata),
            "pages": [p.to_dict() for p in self.pages],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PdfDocumentStructure:
        return cls(
            source_path=data.get("source_path"),
            page_count=int(data.get("page_count", 0)),
            metadata=dict(data.get("metadata") or {}),
            pages=[PdfPageStructure.from_dict(x) for x in data.get("pages", [])],
        )
