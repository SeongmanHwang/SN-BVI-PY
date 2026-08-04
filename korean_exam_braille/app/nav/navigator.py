"""트리 기반 ExamNavigator 구현."""

from __future__ import annotations

from korean_exam_braille.app.exam.models import ExamDocument
from korean_exam_braille.app.nav.index import NavIndex, build_nav_index, node_label
from korean_exam_braille.app.nav.models import NAVIGABLE_TYPES, NavLocation


class TreeExamNavigator:
    """Exam 트리 DFS 인덱스 위 계층 이동.

    UI·BRF·PDF에 의존하지 않음. bind()로 문서만 교체하면 된다.
    """

    def __init__(self) -> None:
        self._index: NavIndex | None = None
        self._current_id: str | None = None
        self._origin_id: str | None = None

    def bind(self, exam: ExamDocument) -> None:
        self._index = build_nav_index(exam)
        self._current_id = None
        self._origin_id = None
        self.reset_to_root()

    def location(self) -> NavLocation | None:
        if not self._index or not self._current_id:
            return None
        return self._make_location(self._current_id)

    def go(self, node_id: str) -> NavLocation | None:
        if not self._index or node_id not in self._index.entries:
            return None
        self._current_id = node_id
        return self.location()

    def go_by_block_id(self, block_id: str) -> NavLocation | None:
        if not self._index:
            return None
        node_id = self._index.find_by_block_id(block_id)
        if node_id is None:
            return None
        return self.go(node_id)

    def parent(self) -> NavLocation | None:
        if not self._index or not self._current_id:
            return None
        entry = self._index.get(self._current_id)
        if entry is None or entry.parent_id is None:
            return None
        return self.go(entry.parent_id)

    def first_child(self) -> NavLocation | None:
        if not self._index or not self._current_id:
            return None
        entry = self._index.get(self._current_id)
        if entry is None or not entry.child_ids:
            return None
        # prefer navigable child
        for cid in entry.child_ids:
            child = self._index.get(cid)
            if child and child.node.node_type in NAVIGABLE_TYPES:
                return self.go(cid)
        return self.go(entry.child_ids[0])

    def next_sibling(self) -> NavLocation | None:
        return self._step_sibling(+1)

    def prev_sibling(self) -> NavLocation | None:
        return self._step_sibling(-1)

    def next_of_type(self, node_type: str) -> NavLocation | None:
        return self._step_type(node_type, +1)

    def prev_of_type(self, node_type: str) -> NavLocation | None:
        return self._step_type(node_type, -1)

    def mark_origin(self) -> None:
        self._origin_id = self._current_id

    def go_origin(self) -> NavLocation | None:
        if self._origin_id is None:
            return None
        return self.go(self._origin_id)

    def reset_to_root(self) -> NavLocation | None:
        if not self._index:
            return None
        if self._index.order:
            return self.go(self._index.order[0])
        return self.go(self._index.root_id)

    def _step_sibling(self, delta: int) -> NavLocation | None:
        if not self._index or not self._current_id:
            return None
        entry = self._index.get(self._current_id)
        if entry is None or not entry.sibling_ids:
            return None
        try:
            idx = entry.sibling_ids.index(self._current_id)
        except ValueError:
            return None
        nxt = idx + delta
        if nxt < 0 or nxt >= len(entry.sibling_ids):
            return None
        return self.go(entry.sibling_ids[nxt])

    def _step_type(self, node_type: str, delta: int) -> NavLocation | None:
        if not self._index:
            return None
        typed = [
            nid
            for nid in self._index.order
            if self._index.entries[nid].node.node_type == node_type
        ]
        if not typed:
            return None
        if self._current_id in typed:
            idx = typed.index(self._current_id)
        else:
            # 현재가 해당 타입이 아니면, 다음/이전 DFS 상의 첫 후보
            cur_order = (
                self._index.order.index(self._current_id)
                if self._current_id in self._index.order
                else -1
            )
            if delta > 0:
                for nid in typed:
                    if self._index.order.index(nid) > cur_order:
                        return self.go(nid)
                return None
            for nid in reversed(typed):
                if self._index.order.index(nid) < cur_order:
                    return self.go(nid)
            return None
        nxt = idx + delta
        if nxt < 0 or nxt >= len(typed):
            return None
        return self.go(typed[nxt])

    def _make_location(self, node_id: str) -> NavLocation | None:
        assert self._index is not None
        entry = self._index.get(node_id)
        if entry is None:
            return None
        sibs = entry.sibling_ids
        try:
            sidx = sibs.index(node_id)
        except ValueError:
            sidx = 0
        nav_children = tuple(
            cid
            for cid in entry.child_ids
            if self._index.entries[cid].node.node_type in NAVIGABLE_TYPES
        )
        return NavLocation(
            node_id=entry.node.id,
            node_type=entry.node.node_type,
            label=node_label(entry.node),
            depth=entry.depth,
            breadcrumb=self._index.breadcrumb(node_id),
            parent_id=entry.parent_id,
            child_ids=nav_children or tuple(entry.child_ids),
            sibling_index=sidx,
            sibling_count=len(sibs) or 1,
            metadata={
                "page_number": entry.node.source_range.page_number,
                "block_ids": list(entry.node.source_range.block_ids),
                "question_number": entry.node.metadata.get("question_number"),
            },
        )
