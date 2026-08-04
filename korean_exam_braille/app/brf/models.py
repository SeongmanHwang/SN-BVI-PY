from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from korean_exam_braille.app.common.tags import STRUCTURE_TAGS

__all__ = [
    "STRUCTURE_TAGS",
    "BrfLine",
    "BrfPage",
    "BrfDocument",
]


@dataclass
class BrfLine:
    """BRF 한 행. 원본 ASCII와 파생 표현을 함께 보관한다."""

    global_index: int
    page_index: int
    line_index: int
    raw_ascii: str
    unicode_braille: str
    reverse_text: str | None = None
    tags: list[str] = field(default_factory=list)
    notes: str | None = None
    candidate_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "global_index": self.global_index,
            "page_index": self.page_index,
            "line_index": self.line_index,
            "raw_ascii": self.raw_ascii,
            "unicode_braille": self.unicode_braille,
            "reverse_text": self.reverse_text,
            "tags": list(self.tags),
            "notes": self.notes,
            "candidate_tags": list(self.candidate_tags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BrfLine:
        return cls(
            global_index=int(data["global_index"]),
            page_index=int(data["page_index"]),
            line_index=int(data["line_index"]),
            raw_ascii=str(data["raw_ascii"]),
            unicode_braille=str(data.get("unicode_braille", "")),
            reverse_text=data.get("reverse_text"),
            tags=list(data.get("tags") or []),
            notes=data.get("notes"),
            candidate_tags=list(data.get("candidate_tags") or []),
        )


@dataclass
class BrfPage:
    """폼피드로 구분된 점자 면."""

    page_index: int
    lines: list[BrfLine] = field(default_factory=list)

    @property
    def line_count(self) -> int:
        return len(self.lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_index": self.page_index,
            "lines": [line.to_dict() for line in self.lines],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BrfPage:
        return cls(
            page_index=int(data["page_index"]),
            lines=[BrfLine.from_dict(item) for item in data.get("lines", [])],
        )


@dataclass
class BrfDocument:
    """BRF 문서 전체. 행·빈 줄·폼피드를 보존한다."""

    source_path: str | None = None
    pages: list[BrfPage] = field(default_factory=list)
    encoding: str = "utf-8"
    has_trailing_formfeed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def lines(self) -> list[BrfLine]:
        result: list[BrfLine] = []
        for page in self.pages:
            result.extend(page.lines)
        return result

    @property
    def line_count(self) -> int:
        return sum(page.line_count for page in self.pages)

    def get_line(self, global_index: int) -> BrfLine:
        for line in self.lines:
            if line.global_index == global_index:
                return line
        raise IndexError(f"line global_index={global_index} not found")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "encoding": self.encoding,
            "has_trailing_formfeed": self.has_trailing_formfeed,
            "metadata": dict(self.metadata),
            "pages": [page.to_dict() for page in self.pages],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BrfDocument:
        return cls(
            source_path=data.get("source_path"),
            encoding=str(data.get("encoding", "utf-8")),
            has_trailing_formfeed=bool(data.get("has_trailing_formfeed", False)),
            metadata=dict(data.get("metadata") or {}),
            pages=[BrfPage.from_dict(item) for item in data.get("pages", [])],
        )
