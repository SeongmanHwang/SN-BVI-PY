"""개발자 모드 PDF↔점자 면 연동."""

import fitz
import pytest

from korean_exam_braille.app.exam.stub import StubExamStructureBuilder
from korean_exam_braille.app.pipeline import default_stub_pipeline
from korean_exam_braille.app.session import ConversionWorkspace, PdfStructureService


@pytest.fixture
def multi_page_pdf(tmp_path):
    path = tmp_path / "multi.pdf"
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page body {i + 1} " + ("가나다라마바사아자차카타파하 " * 8))
    path.write_bytes(doc.tobytes())
    doc.close()
    return path


def test_braille_pages_linked_cover_all_indices(multi_page_pdf):
    ws = ConversionWorkspace(
        service=PdfStructureService(
            exam_builder=StubExamStructureBuilder(),
            pipeline_factory=default_stub_pipeline,
        )
    )
    ws.load_pdf(multi_page_pdf)
    ws.analyze_and_convert()
    braille_pages, pdf_to_braille = ws.braille_pages_linked_to_pdf()
    assert braille_pages
    covered = set()
    for indices in pdf_to_braille.values():
        covered.update(indices)
    assert covered == set(range(len(braille_pages)))
    for page in braille_pages:
        assert page["pdf_page_numbers"]
