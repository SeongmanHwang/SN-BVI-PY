"""줄·면 편집·직렬화 포트."""

from __future__ import annotations

from typing import Protocol

from korean_exam_braille.app.braille.models import BrailleSequence
from korean_exam_braille.app.layout.models import BrailleDocument, LayoutProfile


class BrailleLayoutEngine(Protocol):
    """점자 토큰열 → 줄·면 배치."""

    def layout(
        self,
        sequences: list[BrailleSequence],
        *,
        profile: LayoutProfile | None = None,
    ) -> BrailleDocument: ...


class BrfSerializer(Protocol):
    """BrailleDocument → BRF 텍스트."""

    def serialize(self, document: BrailleDocument) -> str: ...
