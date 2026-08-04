"""점자 줄·면 편집 출력 모델."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LayoutProfile:
    cells_per_line: int = 32
    lines_per_page: int = 26
    top_margin: int = 1
    bottom_margin: int = 1
    paragraph_indent: int = 2
    choice_indent: int = 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "cells_per_line": self.cells_per_line,
            "lines_per_page": self.lines_per_page,
            "top_margin": self.top_margin,
            "bottom_margin": self.bottom_margin,
            "paragraph_indent": self.paragraph_indent,
            "choice_indent": self.choice_indent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LayoutProfile:
        return cls(
            cells_per_line=int(data.get("cells_per_line", 32)),
            lines_per_page=int(data.get("lines_per_page", 26)),
            top_margin=int(data.get("top_margin", 1)),
            bottom_margin=int(data.get("bottom_margin", 1)),
            paragraph_indent=int(data.get("paragraph_indent", 2)),
            choice_indent=int(data.get("choice_indent", 2)),
        )


@dataclass
class BrailleLine:
    cells: list[int] = field(default_factory=list)
    source_node_ids: list[str] = field(default_factory=list)
    ascii_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cells": list(self.cells),
            "source_node_ids": list(self.source_node_ids),
            "ascii_text": self.ascii_text,
        }


@dataclass
class BraillePage:
    page_index: int
    lines: list[BrailleLine] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_index": self.page_index,
            "lines": [ln.to_dict() for ln in self.lines],
            "metadata": dict(self.metadata),
        }


@dataclass
class BrailleDocument:
    pages: list[BraillePage] = field(default_factory=list)
    profile: LayoutProfile = field(default_factory=LayoutProfile)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pages": [p.to_dict() for p in self.pages],
            "profile": self.profile.to_dict(),
            "metadata": dict(self.metadata),
        }
