"""계층 탐색 포트 — 구현 교체 지점."""

from __future__ import annotations

from typing import Protocol

from korean_exam_braille.app.exam.models import ExamDocument
from korean_exam_braille.app.nav.models import NavLocation


class ExamNavigator(Protocol):
    """ExamDocument 위 계층 이동.

    BRF·PDF 뷰에 의존하지 않는다. 동기화는 UI 어댑터가 담당한다.
    """

    def bind(self, exam: ExamDocument) -> None:
        """문서를 붙이고 위치를 초기화한다."""
        ...

    def location(self) -> NavLocation | None: ...

    def go(self, node_id: str) -> NavLocation | None: ...

    def go_by_block_id(self, block_id: str) -> NavLocation | None:
        """PDF 블록 id로 이동 (역연동)."""
        ...

    def parent(self) -> NavLocation | None: ...

    def first_child(self) -> NavLocation | None: ...

    def next_sibling(self) -> NavLocation | None: ...

    def prev_sibling(self) -> NavLocation | None: ...

    def next_of_type(self, node_type: str) -> NavLocation | None: ...

    def prev_of_type(self, node_type: str) -> NavLocation | None: ...

    def mark_origin(self) -> None:
        """원위치 저장."""
        ...

    def go_origin(self) -> NavLocation | None:
        """저장한 원위치로 복귀."""
        ...

    def reset_to_root(self) -> NavLocation | None:
        """문서 루트(또는 첫 탐색 가능 노드)로."""
        ...
