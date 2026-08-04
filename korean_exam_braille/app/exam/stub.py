"""Exam 계층 스텁 — Prototype 3에서 규칙 기반으로 교체."""

from __future__ import annotations

from korean_exam_braille.app.exam.models import ExamDocument, ExamNode, SourceRange
from korean_exam_braille.app.pdf.models import PdfDocumentStructure


class StubExamStructureBuilder:
    """모든 PDF 블록을 Unknown 자식으로 나열하는 자리표시 구현."""

    def build(self, pdf: PdfDocumentStructure) -> ExamDocument:
        children: list[ExamNode] = []
        unclassified: list[str] = []
        for page in pdf.pages:
            for block in page.blocks:
                unclassified.append(block.id)
                children.append(
                    ExamNode(
                        id=block.id,
                        node_type="Unknown",
                        source_range=SourceRange(
                            page_number=page.page_number,
                            block_ids=[block.id],
                            raw_text=block.text,
                        ),
                        confidence=0.0,
                        metadata={
                            "candidate_tags": list(block.candidate_tags),
                            "tags": list(block.tags),
                        },
                    )
                )
        root = ExamNode(
            id="exam-root",
            node_type="ExamDocument",
            source_range=SourceRange(raw_text=pdf.source_path),
            children=children,
            metadata={"source_path": pdf.source_path},
        )
        return ExamDocument(
            root=root,
            unclassified_ids=unclassified,
            metadata={"builder": "StubExamStructureBuilder"},
        )


class StubExamStructureValidator:
    def validate(self, exam: ExamDocument) -> list[str]:
        warnings: list[str] = []
        if exam.unclassified_ids:
            warnings.append(
                f"unclassified blocks: {len(exam.unclassified_ids)} (stub builder)"
            )
        return warnings
