"""공통 레이아웃 프로필 테스트."""

from pathlib import Path

import fitz
import pytest

from korean_exam_braille.app.pdf.extractor import extract_pdf
from korean_exam_braille.app.pdf.layout_profile import (
    _body_gutter_from_spans,
    _is_gutter_noise_span,
    infer_layout_profile,
)
from korean_exam_braille.app.pdf.models import PdfSpan


def _span(
    idx: int,
    text: str,
    *,
    x0: float,
    x1: float,
    y0: float,
    y1: float | None = None,
) -> PdfSpan:
    return PdfSpan(
        id=f"s{idx}",
        text=text,
        bbox=(x0, y0, x1, y1 if y1 is not None else y0 + 12),
        font="Test",
        font_size=11.0,
        is_bold=False,
        page_number=1,
        extraction_index=idx,
    )


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


@pytest.fixture
def vector_header_twocol_pdf(tmp_path: Path) -> Path:
    """문자 ━ 없이 벡터 구분선 + 가운데 '국어영역'이 거터를 가로지르는 PDF."""
    fontfile = Path(r"C:\Windows\Fonts\malgun.ttf")
    if not fontfile.exists():
        pytest.skip("malgun.ttf not found")
    path = tmp_path / "vector_header_twocol.pdf"
    doc = fitz.open()
    for page_no in range(1, 4):
        page = doc.new_page(width=841, height=1190)
        page.insert_font(fontname="f0", fontfile=str(fontfile))
        page.insert_text((365, 130), "국어영역", fontsize=18, fontname="f0")
        page.insert_text((100, 125), str(page_no), fontsize=11, fontname="f0")
        page.insert_text((700, 125), "고1", fontsize=11, fontname="f0")
        # 벡터 전폭 구분선 (문자 ━ 없음)
        page.draw_line(fitz.Point(88, 159), fitz.Point(752, 159), width=0.8)
        page.insert_text((90, 200), "왼쪽 지문 한 줄입니다.", fontsize=11, fontname="f0")
        page.insert_text((90, 230), "왼쪽 두 번째 줄.", fontsize=11, fontname="f0")
        page.insert_text((90, 260), "왼쪽 세 번째 줄도 있습니다.", fontsize=11, fontname="f0")
        page.insert_text((450, 200), f"{page_no}. 물음에 답하시오.", fontsize=11, fontname="f0")
        page.insert_text((450, 230), "① 오른쪽 선택지", fontsize=11, fontname="f0")
        page.insert_text((450, 260), "② 또 다른 선택지", fontsize=11, fontname="f0")
        page.insert_text((400, 1100), str(page_no), fontsize=10, fontname="f0")
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
    assert profile.column_detection == "shared"


def test_extract_applies_same_profile(twocol_pdf: Path):
    result = extract_pdf(twocol_pdf)
    layout = result.metadata["layout_profile"]
    assert "column_cut_x" in layout
    assert result.metadata.get("column_detection") == "shared"
    # 모든 면에 Header/Footer 후보
    for page in result.pages:
        tags = {t for b in page.blocks for t in b.candidate_tags}
        assert "Header" in tags
        assert "Footer" in tags


def test_centered_title_is_gutter_noise():
    title = _span(0, "국어영역", x0=365.4, x1=479.8, y0=119.0)
    assert _is_gutter_noise_span(title, 841.0)
    wide = _span(1, "긴 시험 제목" * 4, x0=220.0, x1=621.0, y0=98.0)
    assert _is_gutter_noise_span(wide, 841.0)
    body = _span(2, "왼쪽 본문", x0=97.0, x1=400.0, y0=200.0)
    assert not _is_gutter_noise_span(body, 841.0)


def test_gutter_ignores_centered_header_title():
    """가운데 '국어영역'이 있어도 좌·우 본문으로 거터를 잡는다."""
    spans = [
        _span(0, "국어영역", x0=365.4, x1=479.8, y0=119.0, y1=147.0),
        _span(1, "왼쪽 본문 A", x0=97.0, x1=400.0, y0=200.0),
        _span(2, "왼쪽 본문 B", x0=97.0, x1=405.0, y0=220.0),
        _span(3, "왼쪽 본문 C", x0=97.0, x1=402.0, y0=240.0),
        _span(4, "오른쪽 문항", x0=439.0, x1=700.0, y0=200.0),
        _span(5, "오른쪽 선택", x0=439.0, x1=680.0, y0=220.0),
        _span(6, "오른쪽 본문", x0=450.0, x1=720.0, y0=240.0),
    ]
    gutter = _body_gutter_from_spans(
        spans,
        header_bottom=160.0,
        footer_top=1080.0,
        page_width=841.0,
    )
    assert gutter is not None
    left_max, right_min, cut = gutter
    assert left_max < right_min
    assert 380 < cut < 450


def test_vector_header_enables_body_gutter(vector_header_twocol_pdf: Path):
    doc = fitz.open(vector_header_twocol_pdf)
    try:
        profile = infer_layout_profile(doc)
    finally:
        doc.close()
    # 벡터 구분선으로 머리글 밴드가 "국어영역" 아래로 내려감
    assert profile.header_bottom_y > 140
    assert profile.header_bottom_y < 200
    # 가운데 제목을 제외하면 공통 거터 성공 가능
    assert profile.column_detection in ("shared", "page_local")
    if profile.column_detection == "shared":
        assert 300 < profile.column_cut_x < 500


def test_page_local_fallback_keeps_columns_separate(vector_header_twocol_pdf: Path):
    result = extract_pdf(vector_header_twocol_pdf)
    detection = result.metadata.get("column_detection")
    assert detection in ("shared", "page_local")
    page = result.pages[1]
    # 같은 y의 좌·우가 한 줄로 합쳐지지 않아야 함
    merged = [
        ln
        for ln in page.lines
        if ln.bbox[0] < 300 and ln.bbox[2] > 500 and (ln.bbox[2] - ln.bbox[0]) > 400
    ]
    body_merged = [
        ln
        for ln in merged
        if "왼쪽" in (ln.text or "") and ("물음" in (ln.text or "") or "선택" in (ln.text or ""))
    ]
    assert body_merged == []
    left_hits = [ln for ln in page.lines if "왼쪽" in (ln.text or "")]
    right_hits = [ln for ln in page.lines if "물음" in (ln.text or "") or "선택지" in (ln.text or "")]
    assert left_hits
    assert right_hits
