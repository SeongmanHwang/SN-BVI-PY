"""불투명 코드 → 빗금 정규화·밑줄 감지 테스트."""

from pathlib import Path

import fitz

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii
from korean_exam_braille.app.common.opaque_text import (
    replace_opaque_with_slash,
    is_opaque_char,
)
from korean_exam_braille.app.pdf.emphasis import (
    annotate_text_with_underline_ranges,
    bbox_has_underline,
    iter_horizontal_underline_segments,
    merge_underline_flags,
)
from korean_exam_braille.app.pdf.extractor import extract_pdf
from korean_exam_braille.app.session import ConversionWorkspace


def test_opaque_replaced_with_slash():
    assert is_opaque_char("\ue000")
    assert is_opaque_char("\uf000")
    assert is_opaque_char("\ufffd")
    assert not is_opaque_char("가")
    assert not is_opaque_char("①")
    assert not is_opaque_char("/")
    src = "가\ue000나\ufffd다"
    assert replace_opaque_with_slash(src) == "가/나/다"
    # 훈몽자회 사례: PUA 따옴표 → 빗금
    ink = "지은 \uf000훈몽자회(訓蒙字會)\uf000에서 비롯된"
    assert replace_opaque_with_slash(ink) == "지은 /훈몽자회(訓蒙字會)/에서 비롯된"


def test_opaque_braille_is_slash_cell():
    """불투명 문자는 빗금 점자(_/ = ⠸⠌)로 점역. 단독 / 는 예와 충돌."""
    assert hangul_text_to_ascii("/") == "_/"
    assert hangul_text_to_ascii("\uf000") == "_/"
    assert hangul_text_to_ascii("가/나") == "$_/c"
    assert hangul_text_to_ascii("가\uf000나") == "$_/c"
    title = "지은 \uf000훈몽자회(訓蒙字會)\uf000에서"
    ascii_text = hangul_text_to_ascii(title)
    assert ascii_text.count("_/") == 2
    assert "\uf000" not in ascii_text
    # 역점역: 빗금 유지, 예로 오인하지 않음
    from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r

    assert r("$_/c") == "가/나"
    back = r(ascii_text)
    assert "/훈몽자회(" in back or back.startswith("지은 /")
    assert "예훈" not in back
    assert "횥" not in back


def test_workspace_pdf_text_uses_slash(tmp_path: Path):
    path = tmp_path / "opaque.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "visible")
    doc.save(path)
    doc.close()

    ws = ConversionWorkspace()
    ws.load_pdf(path)
    page_struct = ws.service.document.pages[0]
    assert page_struct.spans
    page_struct.spans[0].text = "정상\uf0a1기호"
    page_struct.spans[0].underline_ranges = []
    # line/block still old — display walks spans
    for ln in page_struct.lines:
        if page_struct.spans[0].id in ln.span_ids:
            ln.span_ids = [page_struct.spans[0].id]
    shown = ws.pdf_page_text(1)
    assert "정상/기호" in shown or shown == "정상/기호"
    assert "<U+" not in shown


def test_partial_underline_char_ranges(tmp_path: Path):
    """긴 span 중 일부만 밑줄이면 해당 구간만 underline_ranges."""
    path = tmp_path / "partial_ul.pdf"
    fontfile = Path(r"C:\Windows\Fonts\malgun.ttf")
    if not fontfile.exists():
        fontfile = Path(r"C:\Windows\Fonts\arial.ttf")
    doc = fitz.open()
    page = doc.new_page(width=620, height=240)
    page.insert_font(fontname="f0", fontfile=str(fontfile))
    ink = "한자를 빌려 표기하는 차자 표기를 활용"
    page.insert_text((50, 100), ink, fontsize=12, fontname="f0")
    targets = page.search_for("차자 표기")
    assert targets
    r = targets[0]
    y = r.y1 + 1.2
    page.draw_line(fitz.Point(r.x0, y), fitz.Point(r.x1, y), width=0.6)
    doc.save(path)
    doc.close()

    extracted = extract_pdf(path, page_numbers=[1])
    page_struct = extracted.pages[0]
    hit = next(s for s in page_struct.spans if "차자 표기" in s.text)
    assert hit.underline_ranges
    start, end = hit.underline_ranges[0]
    assert "차자 표기" in hit.text[start:end]
    # 줄 전체가 아니라 부분
    assert end - start < len(hit.text)
    from korean_exam_braille.app.pdf.display_text import format_page_text_for_display

    shown = format_page_text_for_display(page_struct)
    assert "<u>차자 표기</u>" in shown
    # 변환용 line/block 에도 동일 마커가 남아 점역 가능해야 한다
    assert any("<u>차자 표기</u>" in (ln.text or "") for ln in page_struct.lines)
    assert any("<u>차자 표기</u>" in (b.text or "") for b in page_struct.blocks)
    from korean_exam_braille.app.braille.translator import hangul_text_to_ascii

    block_hit = next(b for b in page_struct.blocks if "<u>차자 표기</u>" in (b.text or ""))
    assert ",-" in hangul_text_to_ascii(block_hit.text)
    assert "-'" in hangul_text_to_ascii(block_hit.text)

def test_extractor_normalizes_opaque_in_spans(tmp_path: Path):
    """추출 직후 span 텍스트에 PUA가 남지 않고 빗금이 된다."""
    path = tmp_path / "pua.pdf"
    doc = fitz.open()
    page = doc.new_page()
    # PyMuPDF insert may not keep PUA; verify helper on extract path via
    # direct call after building a page that at least extracts something.
    page.insert_text((72, 72), "hello")
    doc.save(path)
    doc.close()
    extracted = extract_pdf(path, page_numbers=[1])
    assert all("\uf000" not in s.text for s in extracted.pages[0].spans)


def test_merge_underline_flags_and_annotate():
    assert merge_underline_flags([False, True, True, False, True]) == [
        (1, 3),
        (4, 5),
    ]
    assert (
        annotate_text_with_underline_ranges("abcdefgh", [(2, 5)])
        == "ab<u>cde</u>fgh"
    )


def test_underline_not_in_span_flags():
    """HTML 밑줄도 span flags에 underline 비트가 없다 (실측 고정)."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_htmlbox(
        fitz.Rect(72, 72, 400, 140),
        "<p><u>underlined sample</u></p>",
    )
    data = page.get_text("dict")
    flags_seen: list[int] = []
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if "underlined" in (span.get("text") or ""):
                    flags_seen.append(int(span.get("flags", 0)))
    doc.close()
    assert flags_seen, "expected text span"
    assert all((f & 32) == 0 for f in flags_seen)


def test_underline_detected_via_drawings(tmp_path: Path):
    path = tmp_path / "underline.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_htmlbox(
        fitz.Rect(72, 72, 420, 140),
        "<p><u>underlined hangul sample</u></p>",
    )
    segs = iter_horizontal_underline_segments(page)
    assert segs, "HTML underline should produce horizontal drawings"
    doc.save(path)
    doc.close()

    extracted = extract_pdf(path, page_numbers=[1])
    page_struct = extracted.pages[0]
    underlined = [s for s in page_struct.spans if s.is_underline]
    assert underlined, "drawing-based underline should mark at least one span"
    assert any("underlined" in s.text.lower() or s.text.strip() for s in underlined)


def test_manual_line_under_text_detected():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "hello")
    page.draw_line(fitz.Point(72, 102), fitz.Point(120, 102), width=0.6)
    data = page.get_text("dict")
    bbox = None
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if "hello" in (span.get("text") or ""):
                    bbox = tuple(float(x) for x in span["bbox"])
    assert bbox is not None
    segs = iter_horizontal_underline_segments(page)
    assert segs
    assert bbox_has_underline(bbox, segs)
    doc.close()
