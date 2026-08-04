"""ExamDocument → 탐색용 평면 인덱스 (순수 함수)."""

from __future__ import annotations

from dataclasses import dataclass, field

from korean_exam_braille.app.exam.models import ExamDocument, ExamNode
from korean_exam_braille.app.nav.models import NAVIGABLE_TYPES, NavCrumb


def node_label(node: ExamNode, *, max_len: int = 48) -> str:
    raw = (node.source_range.raw_text or "").replace("\n", " ").strip()
    qn = node.metadata.get("question_number")
    prefix = f"{qn}. " if qn is not None else ""
    body = prefix + raw
    if len(body) > max_len:
        return body[: max_len - 1] + "…"
    return body or node.id


@dataclass
class NavIndexEntry:
    node: ExamNode
    parent_id: str | None
    depth: int
    child_ids: list[str] = field(default_factory=list)
    sibling_ids: list[str] = field(default_factory=list)


@dataclass
class NavIndex:
    """id → entry. ExamDocument와 1:1로 재생성한다."""

    entries: dict[str, NavIndexEntry]
    order: list[str]
    root_id: str

    def get(self, node_id: str) -> NavIndexEntry | None:
        return self.entries.get(node_id)

    def breadcrumb(self, node_id: str) -> tuple[NavCrumb, ...]:
        """자기 자신을 제외한 조상 crumb (루트 ExamDocument 제외)."""
        ancestors: list[NavCrumb] = []
        cur = self.entries.get(node_id)
        if cur is None:
            return ()
        parent_id = cur.parent_id
        while parent_id is not None:
            parent = self.entries.get(parent_id)
            if parent is None:
                break
            if parent.node.node_type != "ExamDocument":
                ancestors.append(
                    NavCrumb(
                        node_id=parent.node.id,
                        node_type=parent.node.node_type,
                        label=node_label(parent.node),
                    )
                )
            parent_id = parent.parent_id
        ancestors.reverse()
        return tuple(ancestors)

    def find_by_block_id(self, block_id: str) -> str | None:
        """PDF 블록 id → 가장 구체적인 Exam 노드 id."""
        matches: list[NavIndexEntry] = []
        for entry in self.entries.values():
            if block_id in entry.node.source_range.block_ids:
                matches.append(entry)
        if not matches:
            return None
        navigable = set(NAVIGABLE_TYPES)
        matches.sort(
            key=lambda e: (
                e.node.node_type in navigable,
                e.depth,
            ),
            reverse=True,
        )
        return matches[0].node.id


def build_nav_index(exam: ExamDocument) -> NavIndex:
    entries: dict[str, NavIndexEntry] = {}
    order: list[str] = []
    navigable = set(NAVIGABLE_TYPES)

    def walk(node: ExamNode, parent_id: str | None, depth: int) -> None:
        entries[node.id] = NavIndexEntry(
            node=node,
            parent_id=parent_id,
            depth=depth,
            child_ids=[c.id for c in node.children],
        )
        if node.node_type in navigable:
            order.append(node.id)
        for child in node.children:
            walk(child, node.id, depth + 1)

    walk(exam.root, None, 0)

    for entry in entries.values():
        if entry.parent_id is None:
            entry.sibling_ids = [exam.root.id]
            continue
        parent = entries[entry.parent_id]
        nav_sibs = [
            cid
            for cid in parent.child_ids
            if entries[cid].node.node_type in navigable
        ]
        entry.sibling_ids = nav_sibs if nav_sibs else list(parent.child_ids)

    return NavIndex(entries=entries, order=order, root_id=exam.root.id)
