"""Exam 계층 포트 — 구현체를 교체해도 파이프라인이 유지되도록."""

from __future__ import annotations

from typing import Protocol

from korean_exam_braille.app.exam.models import ExamDocument
from korean_exam_braille.app.pdf.models import PdfDocumentStructure


class ExamStructureBuilder(Protocol):
    """PDF 물리 구조 → 수능 국어 의미 구조."""

    def build(self, pdf: PdfDocumentStructure) -> ExamDocument: ...


class ExamStructureValidator(Protocol):
    """전역 제약(문항 수, 선택지 5개 등) 검사."""

    def validate(self, exam: ExamDocument) -> list[str]:
        """경고·오류 메시지 목록."""
        ...
