"""종단 변환 파이프라인 — 단계별 포트를 주입받아 연결."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from korean_exam_braille.app.braille.ports import BrailleTranslator
from korean_exam_braille.app.braille.stub import StubBrailleTranslator
from korean_exam_braille.app.braille.translator import (
    TableBrailleTranslator,
    format_unknown_print_warning,
)
from korean_exam_braille.app.exam.builder import RuleExamStructureBuilder
from korean_exam_braille.app.exam.ports import ExamStructureBuilder, ExamStructureValidator
from korean_exam_braille.app.exam.stub import (
    StubExamStructureBuilder,
    StubExamStructureValidator,
)
from korean_exam_braille.app.exam.validator import RuleExamStructureValidator
from korean_exam_braille.app.layout.engine import RuleBrailleLayoutEngine
from korean_exam_braille.app.layout.models import BrailleDocument, LayoutProfile
from korean_exam_braille.app.layout.ports import BrailleLayoutEngine, BrfSerializer
from korean_exam_braille.app.layout.serializer import AsciiBrfSerializer
from korean_exam_braille.app.layout.stub import StubBrailleLayoutEngine, StubBrfSerializer
from korean_exam_braille.app.pdf.adapter import DefaultPdfStructureExtractor
from korean_exam_braille.app.pdf.ports import PdfStructureExtractor


@dataclass
class PipelineResult:
    """각 단계 산출물을 보존해 단계별 교체·비교가 가능하게 한다."""

    pdf: Any
    exam: Any
    sequences: Any
    braille_document: BrailleDocument
    brf_text: str
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversionPipeline:
    """PDF → Exam → Braille → Layout → BRF.

    단계 구현체는 생성자에서 교체한다.
    """

    pdf_extractor: PdfStructureExtractor = field(
        default_factory=DefaultPdfStructureExtractor
    )
    exam_builder: ExamStructureBuilder = field(
        default_factory=RuleExamStructureBuilder
    )
    exam_validator: ExamStructureValidator = field(
        default_factory=RuleExamStructureValidator
    )
    translator: BrailleTranslator = field(default_factory=TableBrailleTranslator)
    layout_engine: BrailleLayoutEngine = field(
        default_factory=RuleBrailleLayoutEngine
    )
    serializer: BrfSerializer = field(default_factory=AsciiBrfSerializer)
    layout_profile: LayoutProfile = field(default_factory=LayoutProfile)

    def run(
        self,
        pdf_path: str | Path,
        *,
        page_numbers: list[int] | None = None,
    ) -> PipelineResult:
        pdf = self.pdf_extractor.extract(pdf_path, page_numbers=page_numbers)
        return self.run_document(
            pdf,
            metadata={
                "pdf_path": str(pdf_path),
                "page_numbers": page_numbers,
            },
        )

    def run_document(
        self,
        pdf: Any,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> PipelineResult:
        """이미 추출·편집된 PdfDocumentStructure로 이후 단계만 실행."""
        exam = self.exam_builder.build(pdf)
        warnings = list(self.exam_validator.validate(exam))
        sequences = self.translator.translate_document(exam)
        unknown_print: list[str] = []
        for seq in sequences:
            unknown_print.extend(seq.metadata.get("unknown_chars") or [])
        if unknown_print:
            warnings.append(format_unknown_print_warning(unknown_print))
        braille_document = self.layout_engine.layout(
            sequences, profile=self.layout_profile
        )
        brf_text = self.serializer.serialize(braille_document)
        meta = {
            "stages": [
                type(self.pdf_extractor).__name__,
                type(self.exam_builder).__name__,
                type(self.translator).__name__,
                type(self.layout_engine).__name__,
                type(self.serializer).__name__,
            ],
            **(metadata or {}),
        }
        if "pdf_path" not in meta:
            meta["pdf_path"] = getattr(pdf, "source_path", None)
        return PipelineResult(
            pdf=pdf,
            exam=exam,
            sequences=sequences,
            braille_document=braille_document,
            brf_text=brf_text,
            warnings=warnings,
            metadata=meta,
        )


def default_pipeline() -> ConversionPipeline:
    """규칙 기반 Prototype 3 파이프라인."""
    return ConversionPipeline()


def default_stub_pipeline() -> ConversionPipeline:
    """모든 단계가 스텁인 파이프라인 (회귀·격리용)."""
    return ConversionPipeline(
        exam_builder=StubExamStructureBuilder(),
        exam_validator=StubExamStructureValidator(),
        translator=StubBrailleTranslator(),
        layout_engine=StubBrailleLayoutEngine(),
        serializer=StubBrfSerializer(),
    )
