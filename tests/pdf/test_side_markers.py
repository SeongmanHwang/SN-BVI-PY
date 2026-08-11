# -*- coding: utf-8 -*-
"""오른쪽 측면 마커 → 왼쪽 질문 블록 trailing_marker."""

from korean_exam_braille.app.pdf.models import PdfBlock, PdfLine
from korean_exam_braille.app.pdf.side_markers import (
    attach_trailing_side_markers,
    is_marker_only_text,
)


def _line(lid: str, text: str, bbox: tuple[float, float, float, float]) -> PdfLine:
    return PdfLine(lid, text, bbox, [], 1, 0)


def _block(
    bid: str,
    lines: list[PdfLine],
    *,
    order: int = 0,
) -> PdfBlock:
    text = "\n".join(ln.text for ln in lines)
    bbox = (
        min(ln.bbox[0] for ln in lines),
        min(ln.bbox[1] for ln in lines),
        max(ln.bbox[2] for ln in lines),
        max(ln.bbox[3] for ln in lines),
    )
    return PdfBlock(
        id=bid,
        text=text,
        bbox=bbox,
        line_ids=[ln.id for ln in lines],
        page_number=1,
        reading_order=order,
    )


def test_is_marker_only_text():
    assert is_marker_only_text("①")
    assert is_marker_only_text(" ② ")
    assert is_marker_only_text("ㄱ.")
    assert is_marker_only_text("ⓐ")
    assert not is_marker_only_text("① 선택지 가")
    assert not is_marker_only_text("가정하고 있는 인간은 어떤 존재일까?")


def test_attach_side_markers_to_two_line_questions():
    """24번형: 왼쪽 2행 질문 + 오른쪽 ①~③ → 각 질문 끝에 마커."""
    q1a = _line("q1a", "경제 활동을 설명하기 위해 전통적인 경제학이", (50, 100, 320, 114))
    q1b = _line("q1b", "가정하고 있는 인간은 어떤 존재일까?", (50, 116, 300, 130))
    q2a = _line("q2a", "제한된 합리성이 경험과 직감에 따른 의사 결정을", (50, 160, 320, 174))
    q2b = _line("q2b", "기피하게 만드는 이유는 무엇일까?", (50, 176, 280, 190))
    q3a = _line("q3a", "감정은 어떻게 의사 결정에 영향을", (50, 220, 280, 234))
    q3b = _line("q3b", "미치는가?", (50, 236, 140, 250))
    m1 = _line("m1", "①", (360, 108, 380, 122))
    m2 = _line("m2", "②", (360, 168, 380, 182))
    m3 = _line("m3", "③", (360, 228, 380, 242))
    lines = [q1a, q1b, q2a, q2b, q3a, q3b, m1, m2, m3]
    blocks = [
        _block("b1", [q1a, q1b], order=0),
        _block("b2", [q2a, q2b], order=1),
        _block("b3", [q3a, q3b], order=2),
        _block("bm1", [m1], order=3),
        _block("bm2", [m2], order=4),
        _block("bm3", [m3], order=5),
    ]
    out = attach_trailing_side_markers(blocks, lines)
    assert len(out) == 3
    assert out[0].text.endswith("①")
    assert "존재일까? ①" in out[0].text
    assert "무엇일까? ②" in out[1].text
    assert "미치는가? ③" in out[2].text
    assert q1b.trailing_marker == "①"
    assert q2b.trailing_marker == "②"
    assert q3b.trailing_marker == "③"
    assert all(not is_marker_only_text(b.text) or "①" in b.text for b in out)


def test_real_choice_list_not_absorbed():
    """본문이 있는 선택지 열은 측면 마커로 흡수하지 않는다."""
    stem = _line("s", "알맞은 것은?", (50, 100, 200, 114))
    c1 = _line("c1", "① 선택지 가", (50, 140, 220, 154))
    c2 = _line("c2", "② 선택지 나", (50, 160, 220, 174))
    lines = [stem, c1, c2]
    # stem is 1 line — not an owner; choices have body
    blocks = [
        _block("bs", [stem], order=0),
        _block("bc1", [c1], order=1),
        _block("bc2", [c2], order=2),
    ]
    out = attach_trailing_side_markers(blocks, lines)
    assert len(out) == 3
    assert out[1].text == "① 선택지 가"
    assert c1.trailing_marker is None


def test_tall_passage_not_owner():
    """행이 너무 많은 블록은 소유자가 되지 않는다."""
    passage_lines = [
        _line(f"p{i}", f"본문 행 {i}", (50, 100 + i * 16, 300, 114 + i * 16))
        for i in range(10)
    ]
    marker = _line("m", "①", (360, 140, 380, 154))
    lines = passage_lines + [marker]
    blocks = [
        _block("bp", passage_lines, order=0),
        _block("bm", [marker], order=1),
    ]
    out = attach_trailing_side_markers(blocks, lines)
    assert len(out) == 2
    assert marker.trailing_marker is None or passage_lines[-1].trailing_marker is None
    assert "①" not in out[0].text
