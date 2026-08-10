"""장르별 Passage 문단 나눔."""

from korean_exam_braille.app.exam.genre_paragraph_split import (
    count_indented_double_quote_lines,
    line_starts_with_double_quote,
    resplit_passage_run,
)
from korean_exam_braille.app.exam.indent_profile import (
    classify_indent_levels,
    column_relative_x0s,
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
    # R블록 1개 + 연속 L은 줄마다 문단 → 3
    assert len(out) == 3
    assert "들여쓴말" in (out[0].source_range.raw_text or "")
    assert "계속" in (out[0].source_range.raw_text or "")
    assert (out[1].source_range.raw_text or "").strip() == "내어쓴새말"
    assert (out[2].source_range.raw_text or "").strip() == "계속2"


def test_dialogue_consecutive_l_one_line_paragraphs_split():
    """한 줄짜리 L 문단이 연속이면 합치지 않는다."""
    lines = {
        "l0": _line("l0", "첫대사", 100.0),
        "l1": _line("l1", "둘째대사", 100.0),
        "l2": _line("l2", "셋째대사", 100.0),
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
        genre=CFG.label_dialogue,
        lines_by_id=lines,
        block_line_ids=block_line_ids,
        config=CFG,
        id_prefix="g",
    )
    assert len(out) == 3
    assert [ (p.source_range.raw_text or "").strip() for p in out ] == [
        "첫대사",
        "둘째대사",
        "셋째대사",
    ]


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
    assert all(p.metadata.get("indent_genre") == CFG.label_si for p in out)


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


def test_resplit_preserves_bracket_labels_on_passage():
    """문단 분할 후에도 line.bracket_label → Passage 구간 메타가 유지되어야 한다."""
    lines = {
        "p1-c0-l0": _line("p1-c0-l0", "구간시작", 110.0),
        "p1-c0-l1": _line("p1-c0-l1", "이어짐", 100.0),
        "p1-c0-l2": _line("p1-c0-l2", "새문단", 110.0),
        "p1-c0-l3": _line("p1-c0-l3", "이어짐2", 100.0),
    }
    lines["p1-c0-l0"].bracket_label = "[A]"
    lines["p1-c0-l1"].bracket_label = "[A]"
    block_line_ids = {"b1": ["p1-c0-l0", "p1-c0-l1", "p1-c0-l2", "p1-c0-l3"]}
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
        bracket_starts={"p1-c0-l0": "[A]"},
        bracket_ends={"p1-c0-l1": "[A]"},
    )
    assert len(out) == 2
    assert out[0].metadata.get("bracket_labels") == ["[A]"]
    assert out[0].metadata.get("bracket_start_labels") == ["[A]"]
    assert out[0].metadata.get("bracket_end_labels") == ["[A]"]
    assert "bracket_labels" not in out[1].metadata


def test_novel_mixed_columns_does_not_leave_giant_right_blob():
    """좌단 + 우단 본문이 한 Passage로 남을 때 우단이 전부 R로 잡혀 거대 세그먼트가 되면 안 됨."""
    lines = {}
    block_line_ids: dict[str, list[str]] = {"bL": [], "bR": []}
    # left flush paragraphs
    for i, (text, x0) in enumerate(
        [("좌시작", 106.0), ("좌이어", 96.0), ("좌이어2", 96.0)]
    ):
        lid = f"p1-c0-l{i}"
        lines[lid] = _line(lid, text, x0)
        block_line_ids["bL"].append(lid)
    # right: three paragraphs (indent + body), absolute x0 that would all be R vs left min
    right = [
        ("우1시작", 447.0),
        ("우1이어", 437.0),
        ("우1이어2", 437.0),
        ("우2시작", 447.0),
        ("우2이어", 437.0),
        ("우2이어2", 437.0),
        ("우2이어3", 437.0),
        ("우3시작", 447.0),
        ("우3이어", 437.0),
    ]
    for i, (text, x0) in enumerate(right):
        lid = f"p1-c1-l{i}"
        lines[lid] = _line(lid, text, x0)
        block_line_ids["bR"].append(lid)

    # sanity: raw absolute classification would mark all right as R
    abs_x0s = [lines[lid].bbox[0] for lid in block_line_ids["bL"] + block_line_ids["bR"]]
    abs_levels = classify_indent_levels(abs_x0s)
    assert abs_levels[3:].count("R") == len(right)

    items = [
        (lid, lines[lid].bbox[0]) for lid in block_line_ids["bL"] + block_line_ids["bR"]
    ]
    rel_levels = classify_indent_levels(column_relative_x0s(items))
    assert rel_levels[3:].count("R") == 3  # one indent start per right paragraph

    passages = [
        ExamNode(
            id="p0",
            node_type="Passage",
            source_range=SourceRange(
                block_ids=["bL", "bR"], raw_text="x", page_number=1
            ),
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
    sizes = [len(p.metadata.get("line_ids") or []) for p in out]
    assert max(sizes) <= 4
    assert any("우2시작" in (p.source_range.raw_text or "") for p in out)
    assert any("우3시작" in (p.source_range.raw_text or "") for p in out)
