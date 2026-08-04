"""점역 스텁 — 셀을 채우지 않고 원문만 보존."""

from __future__ import annotations

from korean_exam_braille.app.braille.models import BrailleSequence, BrailleToken
from korean_exam_braille.app.exam.models import ExamDocument, ExamNode


class StubBrailleTranslator:
    """Prototype 3 전 자리표시. cells는 비어 있고 source_text만 유지."""

    def translate_text(self, text: str) -> BrailleSequence:
        return BrailleSequence(
            source_node_id="",
            tokens=[
                BrailleToken(
                    source_text=text,
                    token_type="stub",
                    cells=[],
                    rule_id="stub.passthrough",
                )
            ],
            metadata={"translator": "StubBrailleTranslator"},
        )

    def translate_node(self, node: ExamNode) -> BrailleSequence:
        text = node.source_range.raw_text or ""
        seq = self.translate_text(text)
        seq.source_node_id = node.id
        seq.metadata["node_type"] = node.node_type
        return seq

    def translate_document(self, exam: ExamDocument) -> list[BrailleSequence]:
        sequences: list[BrailleSequence] = []

        def walk(node: ExamNode) -> None:
            if node.source_range.raw_text:
                sequences.append(self.translate_node(node))
            for child in node.children:
                walk(child)

        walk(exam.root)
        return sequences
