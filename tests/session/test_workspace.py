"""ConversionWorkspace · DTBook preview."""

from pathlib import Path

import fitz
import pytest

from korean_exam_braille.app.daisy import PreviewDtbookExporter, StubDtbookExporter
from korean_exam_braille.app.exam.models import ExamDocument, ExamNode, SourceRange
from korean_exam_braille.app.exam.stub import StubExamStructureBuilder
from korean_exam_braille.app.pipeline import default_stub_pipeline
from korean_exam_braille.app.session import ConversionWorkspace, PdfStructureService


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


def test_preview_dtbook_xml():
    exam = ExamDocument(
        root=ExamNode(
            id="root",
            node_type="ExamDocument",
            source_range=SourceRange(),
            children=[
                ExamNode(
                    id="q1",
                    node_type="Question",
                    source_range=SourceRange(raw_text="16. 본문"),
                    metadata={"question_number": 16},
                    children=[
                        ExamNode(
                            id="c1",
                            node_type="Choice",
                            source_range=SourceRange(raw_text="① 보기"),
                        )
                    ],
                )
            ],
        )
    )
    xml = PreviewDtbookExporter().export(exam, title="테스트")
    assert xml.startswith("<?xml")
    assert "preview-not-final-schema" in xml
    assert "16" in xml
    assert 'class="Choice"' in xml


def test_workspace_convert_and_brf(tiny_pdf: Path):
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
    assert "dtbook" in (ws.last_dtbook_xml or "").lower() or ws.last_dtbook_xml

    with pytest.raises(NotImplementedError):
        ws.dtbook_xml(for_user_download=True)

    preview = ws.dtbook_xml(for_user_download=False)
    assert "preview-not-final-schema" in preview
