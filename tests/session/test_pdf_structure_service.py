"""PdfStructureService — UI 셸용 Qt-free 세션 경계."""

from pathlib import Path

import fitz
import pytest

from korean_exam_braille.app.exam.stub import StubExamStructureBuilder
from korean_exam_braille.app.nav import TreeExamNavigator
from korean_exam_braille.app.pipeline import default_stub_pipeline
from korean_exam_braille.app.session import PdfStructureService


@pytest.fixture
def tiny_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "tiny.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "16. 문항 본문")
    page.insert_text((72, 100), "① 선택지")
    doc.save(path)
    doc.close()
    return path


def test_open_and_convert_via_stub_pipeline(tiny_pdf: Path):
    service = PdfStructureService(
        exam_builder=StubExamStructureBuilder(),
        pipeline_factory=default_stub_pipeline,
    )
    doc = service.open(tiny_pdf)
    assert doc.page_count >= 1
    assert service.path == tiny_pdf

    result = service.convert()
    assert result.brf_text is not None
    assert result.exam.root.node_type == "ExamDocument"


def test_create_navigator_uses_builder(tiny_pdf: Path):
    service = PdfStructureService(exam_builder=StubExamStructureBuilder())
    service.open(tiny_pdf)
    nav, exam = service.create_navigator()
    assert isinstance(nav, TreeExamNavigator)
    assert exam.root.node_type == "ExamDocument"


def test_accept_candidates_and_merge(tiny_pdf: Path):
    service = PdfStructureService()
    service.open(tiny_pdf)
    page = service.document.pages[0]
    if len(page.blocks) < 2:
        pytest.skip("extractor produced fewer than 2 blocks")

    for block in page.blocks:
        if block.candidate_tags and not block.tags:
            break
    else:
        page.blocks[0].candidate_tags = ["Question"]
        page.blocks[0].tags = []

    applied = service.accept_candidates(page.page_number)
    assert applied >= 1
    assert page.blocks[0].tags or any(b.tags for b in page.blocks)

    a, b = page.blocks[0], page.blocks[1]
    before = len(page.blocks)
    service.merge_selected(page.page_number, a.id, b.id)
    assert len(service.get_page(page.page_number).blocks) == before - 1


def test_require_document_raises():
    service = PdfStructureService()
    with pytest.raises(ValueError, match="열려"):
        service.require_document()
