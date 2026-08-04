"""PDF 물리 구조 모델."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "bbox": list(self.bbox),
            "font": self.font,
            "font_size": self.font_size,
            "is_bold": self.is_bold,
            "page_number": self.page_number,
            "extraction_index": self.extraction_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PdfSpan:
        bbox = data["bbox"]
        return cls(
            id=str(data["id"]),
            text=str(data["text"]),
            bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
            font=str(data.get("font", "")),
            font_size=float(data.get("font_size", 0.0)),
            is_bold=bool(data.get("is_bold", False)),
            page_number=int(data["page_number"]),
            extraction_index=int(data.get("extraction_index", 0)),
        )


@dataclass
class PdfLine:
    id: str
    text: str
    bbox: BBox
    span_ids: list[str]
    page_number: int
    reading_order: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "bbox": list(self.bbox),
            "span_ids": list(self.span_ids),
            "page_number": self.page_number,
            "reading_order": self.reading_order,
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_number": self.page_number,
            "width": self.width,
            "height": self.height,
            "spans": [s.to_dict() for s in self.spans],
            "lines": [ln.to_dict() for ln in self.lines],
            "blocks": [b.to_dict() for b in self.blocks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PdfPageStructure:
        return cls(
            page_number=int(data["page_number"]),
            width=float(data["width"]),
            height=float(data["height"]),
            spans=[PdfSpan.from_dict(x) for x in data.get("spans", [])],
            lines=[PdfLine.from_dict(x) for x in data.get("lines", [])],
            blocks=[PdfBlock.from_dict(x) for x in data.get("blocks", [])],
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
