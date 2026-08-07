"""ConversionWorkspace · DTBook export."""

from pathlib import Path

import fitz
import pytest

from korean_exam_braille.app.daisy import ExamDtbookExporter, StubDtbookExporter
from korean_exam_braille.app.exam.bracket_metadata import bracket_labels
from korean_exam_braille.app.exam.stub import StubExamStructureBuilder
from korean_exam_braille.app.pipeline import default_stub_pipeline
from korean_exam_braille.app.session import (
    ConversionWorkspace,
    PdfStructureService,
)


@pytest.fixture
def tiny_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "tiny.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "16. 문항")
    doc.save(path)
    doc.close()
    return path


def test_stub_dtbook_not_available():
    assert StubDtbookExporter().available is False


def test_bracket_labels_from_pdf_candidate_tags():
    assert bracket_labels({"candidate_tags": ["bracket:[A],[B]"]}) == [
        "[A]",
        "[B]",
    ]
    assert bracket_labels({"candidate_tags": ["Question"]}) == []


def test_workspace_convert_and_dtbook_download(tiny_pdf: Path):
    ws = ConversionWorkspace(
        service=PdfStructureService(
            exam_builder=StubExamStructureBuilder(),
            pipeline_factory=default_stub_pipeline,
        )
    )
    meta = ws.load_pdf(tiny_pdf)
    assert meta["name"] == "tiny.pdf"
    assert ws.dtbook_download_available is False

    result = ws.analyze_and_convert()
    assert result.brf_text
    assert ws.has_brf
    assert ws.dtbook_download_available is True
    assert "dtbook" in (ws.last_dtbook_xml or "").lower()

    user_xml = ws.dtbook_xml(for_user_download=True)
    assert "dtbook-2005-3-structure" in user_xml
    assert ExamDtbookExporter().available is True

    preview = ws.dtbook_xml(for_user_download=False)
    assert "dtbook-2005-3-structure" in preview
