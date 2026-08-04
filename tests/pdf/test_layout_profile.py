"""공통 레이아웃 프로필 테스트."""

from pathlib import Path

import fitz
import pytest

from korean_exam_braille.app.pdf.extractor import extract_pdf
from korean_exam_braille.app.pdf.layout_profile import infer_layout_profile


@pytest.fixture
def twocol_pdf(tmp_path: Path) -> Path:
    """헤더·2단·푸터가 반복되는 합성 PDF."""
    fontfile = Path(r"C:\Windows\Fonts\malgun.ttf")
    if not fontfile.exists():
        pytest.skip("malgun.ttf not found")
    path = tmp_path / "twocol.pdf"
    doc = fitz.open()
    for page_no in range(1, 4):
        page = doc.new_page(width=841, height=1190)
        page.insert_font(fontname="f0", fontfile=str(fontfile))
        # header
        page.insert_text((362, 120), "국어영역", fontsize=14, fontname="f0")
        page.insert_text((100, 140), f"{page_no}          고2", fontsize=11, fontname="f0")
        page.insert_text((90, 160), "━" * 40, fontsize=10, fontname="f0")
        # left body
        page.insert_text((90, 200), f"[{page_no * 3} ~ {page_no * 3 + 2}] 다음 글을 읽고", fontsize=11, fontname="f0")
        page.insert_text((90, 230), "왼쪽 본문입니다.", fontsize=11, fontname="f0")
        # right body
        page.insert_text((450, 200), f"{page_no}. 알맞은 것은?", fontsize=11, fontname="f0")
        page.insert_text((450, 230), "① 선택지", fontsize=11, fontname="f0")
        # footer
        page.insert_text((400, 1100), str(page_no), fontsize=10, fontname="f0")
        page.insert_text((430, 1105), "16", fontsize=10, fontname="f0")
    doc.save(path)
    doc.close()
    return path


def test_infer_shared_profile(twocol_pdf: Path):
    doc = fitz.open(twocol_pdf)
    try:
        profile = infer_layout_profile(doc)
    finally:
        doc.close()
    assert profile.column_cut_x > 300
    assert profile.column_cut_x < 500
    assert profile.header_bottom_y < 250
    assert profile.footer_top_y > 1000


def test_extract_applies_same_profile(twocol_pdf: Path):
    result = extract_pdf(twocol_pdf)
    layout = result.metadata["layout_profile"]
    assert "column_cut_x" in layout
    # 모든 면에 Header/Footer 후보
    for page in result.pages:
        tags = {t for b in page.blocks for t in b.candidate_tags}
        assert "Header" in tags
        assert "Footer" in tags
