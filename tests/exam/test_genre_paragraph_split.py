"""장르별 Passage 문단 나눔."""

from korean_exam_braille.app.exam.genre_paragraph_split import (
    count_indented_double_quote_lines,
    line_starts_with_double_quote,
    resplit_passage_run,
)
from korean_exam_braille.app.exam.models import ExamNode, SourceRange
from korean_exam_braille.app.exam.passage_indent_config import (
    DEFAULT_PASSAGE_INDENT_GENRE_CONFIG as CFG,
)
from korean_exam_braille.app.pdf.models import PdfLine


def _line(lid: str, text: str, x0: float, page: int = 1) -> PdfLine:
    return PdfLine(
        id=lid,
        text=text,
        bbox=(x0, 0.0, x0 + 100.0, 12.0),
        span_ids=[],
        page_number=page,
    )


def test_double_quote_detection():
    assert line_starts_with_double_quote('"안녕"')
    assert line_starts_with_double_quote("“안녕”")
    assert line_starts_with_double_quote('  "들여쓴 인용"')
    assert not line_starts_with_double_quote("「홀낫표」")
    assert not line_starts_with_double_quote("인용 없음")


def test_count_indented_double_quotes():
    # base 100, indent 110 = R
    x0s = [110.0, 100.0, 110.0, 100.0]
    texts = ['"말1"', "본문", "“말2”", "본문2"]
    assert count_indented_double_quote_lines(x0s, texts) == 2


def test_nonfiction_splits_on_indent():
    lines = {
        "l0": _line("l0", "첫단락시작", 110.0),
        "l1": _line("l1", "이어짐", 100.0),
        "l2": _line("l2", "새단락", 110.0),
        "l3": _line("l3", "이어짐2", 100.0),
    }
    block_line_ids = {"b1": ["l0", "l1", "l2", "l3"]}
    passages = [
        ExamNode(
            id="p0",
            node_type="Passage",
            source_range=SourceRange(block_ids=["b1"], raw_text="x", page_number=1),
        )
    ]
    out = resplit_passage_run(
        passages,
        genre=CFG.label_nonfiction,
        lines_by_id=lines,
        block_line_ids=block_line_ids,
        config=CFG,
        id_prefix="g",
    )
    assert len(out) == 2
    assert "첫단락시작" in (out[0].source_range.raw_text or "")
    assert "새단락" in (out[1].source_range.raw_text or "")


def test_dialogue_splits_on_outdent():
    lines = {
        "l0": _line("l0", "들여쓴말", 120.0),
        "l1": _line("l1", "계속", 120.0),
        "l2": _line("l2", "내어쓴새말", 100.0),
        "l3": _line("l3", "계속2", 100.0),
    }
    block_line_ids = {"b1": ["l0", "l1", "l2", "l3"]}
    passages = [
        ExamNode(
            id="p0",
            node_type="Passage",
            source_range=SourceRange(block_ids=["b1"], raw_text="x", page_number=1),
        )
    ]
    out = resplit_passage_run(
        passages,
        genre=CFG.label_dialogue,
        lines_by_id=lines,
        block_line_ids=block_line_ids,
        config=CFG,
        id_prefix="g",
    )
    assert len(out) == 2
    assert "들여쓴말" in (out[0].source_range.raw_text or "")
    assert "내어쓴새말" in (out[1].source_range.raw_text or "")


def test_poetry_does_not_split():
    lines = {
        "l0": _line("l0", "a", 110.0),
        "l1": _line("l1", "b", 100.0),
        "l2": _line("l2", "c", 110.0),
    }
    block_line_ids = {"b1": ["l0", "l1", "l2"]}
    passages = [
        ExamNode(
            id="p0",
            node_type="Passage",
            source_range=SourceRange(block_ids=["b1"], raw_text="x", page_number=1),
        )
    ]
    out = resplit_passage_run(
        passages,
        genre=CFG.label_si,
        lines_by_id=lines,
        block_line_ids=block_line_ids,
        config=CFG,
        id_prefix="g",
    )
    assert out == passages


def test_novel_quote_keeps_following_indents():
    # R" R R L L R(본문) L → 따옴표 문단은 R×3, 이어서 L×2, 그다음 비따옴표 R+L
    lines = {
        "l0": _line("l0", "“대사1", 110.0),
        "l1": _line("l1", "대사계속", 110.0),
        "l2": _line("l2", "대사끝”", 110.0),
        "l3": _line("l3", "서술1", 100.0),
        "l4": _line("l4", "서술2", 100.0),
        "l5": _line("l5", "새문단", 110.0),
        "l6": _line("l6", "이어짐", 100.0),
    }
    block_line_ids = {"b1": ["l0", "l1", "l2", "l3", "l4", "l5", "l6"]}
    passages = [
        ExamNode(
            id="p0",
            node_type="Passage",
            source_range=SourceRange(block_ids=["b1"], raw_text="x", page_number=1),
        )
    ]
    out = resplit_passage_run(
        passages,
        genre=CFG.label_novel,
        lines_by_id=lines,
        block_line_ids=block_line_ids,
        config=CFG,
        id_prefix="g",
    )
    assert len(out) == 3
    assert "대사1" in (out[0].source_range.raw_text or "")
    assert "대사끝" in (out[0].source_range.raw_text or "")
    assert "서술1" in (out[1].source_range.raw_text or "")
    assert "새문단" in (out[2].source_range.raw_text or "")
    assert "이어짐" in (out[2].source_range.raw_text or "")
