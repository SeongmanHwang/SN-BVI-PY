"""계층 탐색 위치·경로 모델 (UI·점역과 독립)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# 탐색에 노출하는 의미 노드 (리프·중간)
NAVIGABLE_TYPES: tuple[str, ...] = (
    "PassageGroup",
    "Passage",
    "Question",
    "Prompt",
    "Choice",
    "ExampleBox",
    "Footnote",
    "Instruction",
)


@dataclass(frozen=True)
class NavCrumb:
    node_id: str
    node_type: str
    label: str


@dataclass
class NavLocation:
    """현재 탐색 위치."""

    node_id: str
    node_type: str
    label: str
    depth: int
    breadcrumb: tuple[NavCrumb, ...] = ()
    parent_id: str | None = None
    child_ids: tuple[str, ...] = ()
    sibling_index: int = 0
    sibling_count: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        path = " > ".join(f"{c.node_type}" for c in self.breadcrumb)
        here = f"{self.node_type}: {self.label}"
        return f"{path} > {here}" if path else here
