"""점역 계층 포트."""

from __future__ import annotations

from typing import Protocol

from korean_exam_braille.app.braille.models import BrailleSequence
from korean_exam_braille.app.exam.models import ExamDocument, ExamNode


class BrailleTranslator(Protocol):
    """묵자(또는 ExamNode) → 점자 토큰열."""

    def translate_text(self, text: str) -> BrailleSequence: ...

    def translate_node(self, node: ExamNode) -> BrailleSequence: ...

    def translate_document(self, exam: ExamDocument) -> list[BrailleSequence]: ...
