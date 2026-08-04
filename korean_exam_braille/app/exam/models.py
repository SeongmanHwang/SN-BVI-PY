"""수능 국어 의미 구조 모델 (계층 트리 + 참조 그래프)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SourceRange:
    """원본(PDF/BRF)에서의 위치."""

    page_number: int | None = None
    block_ids: list[str] = field(default_factory=list)
    start_offset: int | None = None
    end_offset: int | None = None
    raw_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_number": self.page_number,
            "block_ids": list(self.block_ids),
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "raw_text": self.raw_text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceRange:
        return cls(
            page_number=data.get("page_number"),
            block_ids=list(data.get("block_ids") or []),
            start_offset=data.get("start_offset"),
            end_offset=data.get("end_offset"),
            raw_text=data.get("raw_text"),
        )


@dataclass
class ExamRelation:
    """교차 참조 (문항→지문, 문항→보기 등)."""

    relation_type: str
    source_id: str
    target_id: str
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_type": self.relation_type,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExamRelation:
        return cls(
            relation_type=str(data["relation_type"]),
            source_id=str(data["source_id"]),
            target_id=str(data["target_id"]),
            confidence=float(data.get("confidence", 1.0)),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class ExamNode:
    """시험지 의미 노드."""

    id: str
    node_type: str
    source_range: SourceRange
    confidence: float = 1.0
    children: list[ExamNode] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "node_type": self.node_type,
            "source_range": self.source_range.to_dict(),
            "confidence": self.confidence,
            "children": [c.to_dict() for c in self.children],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExamNode:
        return cls(
            id=str(data["id"]),
            node_type=str(data["node_type"]),
            source_range=SourceRange.from_dict(data.get("source_range") or {}),
            confidence=float(data.get("confidence", 1.0)),
            children=[cls.from_dict(c) for c in data.get("children", [])],
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class ExamDocument:
    """계층 트리 + 참조 그래프."""

    root: ExamNode
    relations: list[ExamRelation] = field(default_factory=list)
    unclassified_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root.to_dict(),
            "relations": [r.to_dict() for r in self.relations],
            "unclassified_ids": list(self.unclassified_ids),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExamDocument:
        return cls(
            root=ExamNode.from_dict(data["root"]),
            relations=[ExamRelation.from_dict(r) for r in data.get("relations", [])],
            unclassified_ids=list(data.get("unclassified_ids") or []),
            metadata=dict(data.get("metadata") or {}),
        )
