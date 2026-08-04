"""계층 포트·파이프라인 골격 테스트."""

from pathlib import Path

import fitz
import pytest

from korean_exam_braille.app.braille.stub import StubBrailleTranslator
from korean_exam_braille.app.exam.stub import StubExamStructureBuilder
from korean_exam_braille.app.layout.stub import StubBrailleLayoutEngine, StubBrfSerializer
from korean_exam_braille.app.pipeline import ConversionPipeline, default_stub_pipeline
from korean_exam_braille.app.pdf.adapter import DefaultPdfStructureExtractor


@pytest.fixture
def tiny_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "tiny.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello 16. test")
    doc.save(path)
    doc.close()
    return path


def test_default_pipeline_runs(tiny_pdf: Path):
    pipeline = default_stub_pipeline()
    result = pipeline.run(tiny_pdf, page_numbers=[1])
    assert result.pdf.page_count >= 1
    assert result.exam.root.node_type == "ExamDocument"
    assert result.exam.unclassified_ids
    assert result.sequences
    assert result.braille_document.pages
    assert isinstance(result.brf_text, str)
    assert result.warnings
    assert "StubExamStructureBuilder" in result.metadata["stages"]


def test_pipeline_accepts_injected_ports(tiny_pdf: Path):
    pipeline = ConversionPipeline(
        pdf_extractor=DefaultPdfStructureExtractor(),
        exam_builder=StubExamStructureBuilder(),
        translator=StubBrailleTranslator(),
        layout_engine=StubBrailleLayoutEngine(),
        serializer=StubBrfSerializer(),
    )
    result = pipeline.run(tiny_pdf)
    assert "\x0c" in result.brf_text or result.brf_text is not None
