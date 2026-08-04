"""PDF 추출·후보 탐지 테스트."""

from pathlib import Path

import fitz
import pytest

from korean_exam_braille.app.pdf.block_builder import merge_blocks, split_block
from korean_exam_braille.app.pdf.candidates import detect_block_candidates
from korean_exam_braille.app.pdf.extractor import extract_pdf
from korean_exam_braille.app.pdf.io import load_structure, save_structure


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "sample_exam.pdf"
    fontfile = Path(r"C:\Windows\Fonts\malgun.ttf")
    if not fontfile.exists():
        fontfile = Path(r"C:\Windows\Fonts\arial.ttf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    fontname = "f0"
    page.insert_font(fontname=fontname, fontfile=str(fontfile))

    def put(y: float, text: str, size: float = 11) -> None:
        page.insert_text((72, y), text, fontsize=size, fontname=fontname)

    put(72, "국어 영역", 16)
    put(120, "16. 다음 글의 내용으로 알맞은 것은?")
    put(150, "1) 선택지 가")
    put(170, "2) 선택지 나")
    put(190, "3) 선택지 다")
    put(220, "<보기>")
    put(240, "보기의 내용이다.")
    put(280, "[17~18] 다음 글을 읽고 물음에 답하시오.")
    doc.save(path)
    doc.close()
    return path


def test_extract_spans_and_blocks(sample_pdf: Path):
    doc = extract_pdf(sample_pdf, page_numbers=[1])
    assert doc.page_count == 1
    page = doc.pages[0]
    assert page.spans
    assert page.lines
    assert page.blocks
    joined = "\n".join(b.text for b in page.blocks)
    assert "16." in joined or "16" in joined
    assert any("Question" in b.candidate_tags for b in page.blocks)
    assert any("Choice" in b.candidate_tags for b in page.blocks)
    assert any("ExampleBox" in b.candidate_tags for b in page.blocks)


def test_structure_roundtrip(sample_pdf: Path, tmp_path: Path):
    doc = extract_pdf(sample_pdf)
    out = tmp_path / "out.structure.json"
    save_structure(doc, out)
    loaded = load_structure(out)
    assert loaded.page_count == doc.page_count
    assert len(loaded.pages[0].blocks) == len(doc.pages[0].blocks)
    assert loaded.pages[0].blocks[0].text == doc.pages[0].blocks[0].text


def test_merge_and_split(sample_pdf: Path):
    doc = extract_pdf(sample_pdf, page_numbers=[1])
    page = doc.pages[0]
    if len(page.blocks) < 2:
        pytest.skip("not enough blocks")
    a, b = page.blocks[0], page.blocks[1]
    merged_list = merge_blocks(page.blocks, a.id, b.id)
    assert len(merged_list) == len(page.blocks) - 1
    merged = next(x for x in merged_list if a.id == x.id or a.text in x.text)
    if len(merged.line_ids) >= 2:
        left, right = split_block(merged, page.lines, merged.line_ids[0])
        assert left.line_ids
        assert right.line_ids


def test_detect_candidates():
    assert "Question" in detect_block_candidates("16. 발문입니다")
    assert "Choice" in detect_block_candidates("① 보기")
    assert "ExampleBox" in detect_block_candidates("〈보기〉")
    assert "PassageGroup" in detect_block_candidates("[1~3] 다음 글을 읽고")
