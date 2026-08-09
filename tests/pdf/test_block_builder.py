"""build_blocks 들여쓰기/내어쓰기 문단 분할 테스트."""

from korean_exam_braille.app.pdf.block_builder import build_blocks
from korean_exam_braille.app.pdf.models import PdfLine


def _line(lid: str, text: str, x0: float, y0: float, *, x1: float = 280.0, h: float = 14.0) -> PdfLine:
    return PdfLine(lid, text, (x0, y0, x1, y0 + h), [], 1, 0)


def test_indent_paragraphs_split_on_first_line_return():
    """들여쓰기: 첫줄 오른쪽·본문 왼쪽 — 본문 후 다시 들여쓰면 새 문단."""
    lines = [
        _line("l0", "첫 문단 첫줄", x0=80, y0=100),
        _line("l1", "첫 문단 본문", x0=60, y0=116),
        _line("l2", "첫 문단 이어짐", x0=60, y0=132),
        _line("l3", "둘째 문단 첫줄", x0=80, y0=148),
        _line("l4", "둘째 문단 본문", x0=60, y0=164),
    ]
    blocks = build_blocks(lines, page_number=1)
    assert len(blocks) == 2
    assert blocks[0].line_ids == ["l0", "l1", "l2"]
    assert blocks[1].line_ids == ["l3", "l4"]


def test_outdent_dialogue_paragraphs_split():
    """내어쓰기(대화문): 첫줄 왼쪽·본문 오른쪽 — 본문 후 다시 내어쓰면 새 문단."""
    lines = [
        _line("l0", "“안녕,” 하고", x0=60, y0=100),
        _line("l1", "그가 말했다.", x0=80, y0=116),
        _line("l2", "이어서 덧붙였다.", x0=80, y0=132),
        _line("l3", "“다음에,” 하고", x0=60, y0=148),
        _line("l4", "그녀가 답했다.", x0=80, y0=164),
    ]
    blocks = build_blocks(lines, page_number=1)
    assert len(blocks) == 2
    assert blocks[0].line_ids == ["l0", "l1", "l2"]
    assert blocks[1].line_ids == ["l3", "l4"]


def test_first_to_body_indent_shift_stays_one_block():
    """문단 내부 첫줄→본문 여백 전환만으로는 분리되지 않는다."""
    lines = [
        _line("l0", "문단 첫줄", x0=80, y0=100),
        _line("l1", "문단 본문 계속", x0=60, y0=116),
        _line("l2", "문단 본문 더", x0=60, y0=132),
    ]
    blocks = build_blocks(lines, page_number=1)
    assert len(blocks) == 1
    assert blocks[0].line_ids == ["l0", "l1", "l2"]
