"""RuleExamStructureBuilder 테스트."""

from korean_exam_braille.app.exam.builder import RuleExamStructureBuilder
from korean_exam_braille.app.exam.validator import RuleExamStructureValidator
from korean_exam_braille.app.pdf.models import (
    PdfBlock,
    PdfDocumentStructure,
    PdfPageStructure,
)


def _block(
    bid: str,
    text: str,
    *,
    order: int,
    tags: list[str] | None = None,
    page: int = 1,
) -> PdfBlock:
    return PdfBlock(
        id=bid,
        text=text,
        bbox=(0, float(order * 20), 200, float(order * 20 + 15)),
        line_ids=[],
        page_number=page,
        reading_order=order,
        candidate_tags=list(tags or []),
    )


def _doc(blocks: list[PdfBlock]) -> PdfDocumentStructure:
    return PdfDocumentStructure(
        source_path="mock.pdf",
        page_count=1,
        pages=[
            PdfPageStructure(
                page_number=1,
                width=595,
                height=842,
                blocks=blocks,
            )
        ],
    )


def test_builds_passage_group_with_questions_and_choices():
    blocks = [
        _block("b0", "[16~17] 다음 글을 읽고 물음에 답하시오.", order=0, tags=["PassageGroup"]),
        _block("b1", "지문 첫 문단이다.", order=1),
        _block("b2", "지문 둘째 문단이다.", order=2),
        _block("b3", "16. 윗글의 내용으로 알맞은 것은?", order=3, tags=["Question"]),
        _block("b4", "① 가", order=4, tags=["Choice"]),
        _block("b5", "② 나", order=5, tags=["Choice"]),
        _block("b6", "③ 다", order=6, tags=["Choice"]),
        _block("b7", "④ 라", order=7, tags=["Choice"]),
        _block("b8", "⑤ 마", order=8, tags=["Choice"]),
        _block("b9", "17. 밑줄 친 부분의 의미는?", order=9, tags=["Question"]),
        _block("b10", "① 가", order=10, tags=["Choice"]),
        _block("b11", "② 나", order=11, tags=["Choice"]),
        _block("b12", "③ 다", order=12, tags=["Choice"]),
        _block("b13", "④ 라", order=13, tags=["Choice"]),
        _block("b14", "⑤ 마", order=14, tags=["Choice"]),
    ]
    exam = RuleExamStructureBuilder().build(_doc(blocks))
    groups = [c for c in exam.root.children if c.node_type == "PassageGroup"]
    assert len(groups) == 1
    group = groups[0]
    passages = [c for c in group.children if c.node_type == "Passage"]
    questions = [c for c in group.children if c.node_type == "Question"]
    assert len(passages) == 2
    assert len(questions) == 2
    assert all(sum(1 for c in q.children if c.node_type == "Choice") == 5 for q in questions)
    assert len(exam.relations) == 2
    assert all(r.relation_type == "refers_to_passage" for r in exam.relations)
    assert exam.relations[0].target_id == group.id
    assert not exam.unclassified_ids


def test_validator_warns_on_choice_count():
    blocks = [
        _block("g", "[1~1] 글", order=0, tags=["PassageGroup"]),
        _block("q", "1. 물음", order=1, tags=["Question"]),
        _block("c1", "① 가", order=2, tags=["Choice"]),
        _block("c2", "② 나", order=3, tags=["Choice"]),
    ]
    exam = RuleExamStructureBuilder().build(_doc(blocks))
    warnings = RuleExamStructureValidator().validate(exam)
    assert any("expected 5 choices" in w for w in warnings)


def test_bracket_tags_become_common_exam_metadata():
    blocks = [
        _block("g", "[1~1] 글", order=0, tags=["PassageGroup"]),
        _block(
            "p1",
            "학생1 발언",
            order=1,
            tags=["bracket:[A]", "bracket-start:[A]"],
        ),
        _block(
            "p2",
            "학생2 발언",
            order=2,
            tags=["bracket:[A]", "bracket-end:[A]"],
        ),
    ]
    exam = RuleExamStructureBuilder().build(_doc(blocks))
    passages = [
        child
        for group in exam.root.children
        for child in group.children
        if child.node_type == "Passage"
    ]
    assert passages[0].metadata["bracket_labels"] == ["[A]"]
    assert passages[0].metadata["bracket_start_labels"] == ["[A]"]
    assert passages[1].metadata["bracket_labels"] == ["[A]"]
    assert "bracket_start_labels" not in passages[1].metadata
    assert passages[1].metadata["bracket_end_labels"] == ["[A]"]


def test_header_footer_excluded_from_content_root():
    """Header/Footer는 본문 root에 넣지 않고 page_artifacts로만 보존한다."""
    blocks = [
        _block("h", "국어 영역", order=0, tags=["Header"]),
        _block("g", "[1~2] 다음", order=1, tags=["PassageGroup"]),
        _block("p", "본문", order=2),
        _block("f", "1", order=3, tags=["Footer"]),
    ]
    exam = RuleExamStructureBuilder().build(_doc(blocks))
    types = [c.node_type for c in exam.root.children]
    assert types == ["PassageGroup"]
    group = exam.root.children[0]
    assert [c.node_type for c in group.children] == ["Passage"]
    artifacts = exam.metadata.get("page_artifacts") or []
    assert [a["node_type"] for a in artifacts] == ["Header", "Footer"]
    assert artifacts[0]["metadata"].get("reading_order") == 0
    assert artifacts[1]["metadata"].get("reading_order") == 3
    assert artifacts[0]["source_range"]["page_number"] == 1


def test_numbered_outline_inside_passage_is_not_question():
    """[28~30] 지문 안의 1. 2.는 문항이 아니고, 28.부터 문항이다."""
    blocks = [
        _block(
            "g",
            "[28 ~ 30] 다음은 학생들이 작성한 공동 보고서의 초고이다.",
            order=0,
            tags=["PassageGroup"],
        ),
        _block("title", "우리 학교 앞 자전거 도로 안전 실태 조사 보고서", order=1),
        _block("s1", "Ⅰ. 조사 동기 및 목적", order=2),
        _block("s2", "Ⅱ. 조사 계획", order=3),
        _block("n1", "1. 조사 방법: 설문 조사, 현장 조사", order=4, tags=["Question"]),
        _block("n2", "2. 조사 내용: 사고 현황 및 원인", order=5, tags=["Question"]),
        _block("s3", "Ⅲ. 조사 결과", order=6),
        _block("n3", "1. ○○로의 자전거 대 보행자 간 사고 현황", order=7, tags=["Question"]),
        _block("fig", "[그림]", order=8, tags=["FigureAsset"]),
        _block("n4", "2. 사고 원인 분석 및 해결 방안", order=9, tags=["Question"]),
        _block("s4", "Ⅳ. 결론", order=10),
        _block("q28", "28. ‘초고’의 글쓰기 방식으로 가장 적절한 것은?", order=11, tags=["Question"]),
        _block("c1", "① 가", order=12, tags=["Choice"]),
        _block("q29", "29. ㉠~㉢이 ‘Ⅲ. 조사 결과’에 구체화된 내용", order=13, tags=["Question"]),
        _block("c2", "① 나", order=14, tags=["Choice"]),
        _block("q30", "30. <보기>는 ‘Ⅳ. 결론’을 고쳐 쓴 것이다.", order=15, tags=["Question"]),
        _block("c3", "① 다", order=16, tags=["Choice"]),
    ]
    exam = RuleExamStructureBuilder().build(_doc(blocks))
    group = exam.root.children[0]
    assert group.node_type == "PassageGroup"
    types = [c.node_type for c in group.children]
    assert types == [
        "Passage",
        "Passage",
        "Passage",
        "Passage",
        "Passage",
        "Passage",
        "Passage",
        "FigureAsset",
        "Passage",
        "Passage",
        "Question",
        "Question",
        "Question",
    ]
    questions = [c for c in group.children if c.node_type == "Question"]
    assert [q.metadata.get("question_number") for q in questions] == [28, 29, 30]
    passages = [c for c in group.children if c.node_type == "Passage"]
    assert passages[3].source_range.raw_text.startswith("1. 조사 방법")
    assert passages[6].source_range.raw_text.startswith("1. ○○로의")
    fig = next(c for c in group.children if c.node_type == "FigureAsset")
    assert fig.id == "fig"
    assert questions[0].children[0].node_type == "Choice"


def test_orphan_question_without_passage_group_still_starts():
    """지문 그룹이 없으면 1~45 번호 문항 후보를 그대로 문항으로 둔다."""
    blocks = [
        _block("q", "16. 다음 글의 내용으로 알맞은 것은?", order=0, tags=["Question"]),
        _block("c", "① 가", order=1, tags=["Choice"]),
    ]
    exam = RuleExamStructureBuilder().build(_doc(blocks))
    assert exam.root.children[0].node_type == "Question"
    assert exam.root.children[0].metadata.get("question_number") == 16


def test_passage_continues_across_footer_header():
    """쪽 장식 뒤에도 같은 PassageGroup에 지문이 이어진다."""
    page1 = [
        _block("g", "[24~27] 다음", order=0, tags=["PassageGroup"], page=1),
        _block("p1", "지문 앞부분", order=1, page=1),
        _block("f", "8", order=2, tags=["Footer"], page=1),
    ]
    page2 = [
        _block("h", "국어 영역", order=0, tags=["Header"], page=2),
        _block("p2", "지문 이어쓰기", order=1, page=2),
        _block("q", "24. 물음", order=2, tags=["Question"], page=2),
    ]
    doc = PdfDocumentStructure(
        source_path="mock.pdf",
        page_count=2,
        pages=[
            PdfPageStructure(page_number=1, width=595, height=842, blocks=page1),
            PdfPageStructure(page_number=2, width=595, height=842, blocks=page2),
        ],
    )
    exam = RuleExamStructureBuilder().build(doc)
    assert all(c.node_type != "Header" and c.node_type != "Footer" for c in exam.root.children)
    groups = [c for c in exam.root.children if c.node_type == "PassageGroup"]
    assert len(groups) == 1
    passages = [c for c in groups[0].children if c.node_type == "Passage"]
    questions = [c for c in groups[0].children if c.node_type == "Question"]
    assert [p.source_range.raw_text for p in passages] == ["지문 앞부분", "지문 이어쓰기"]
    assert len(questions) == 1
    assert not exam.unclassified_ids
    artifacts = exam.metadata.get("page_artifacts") or []
    assert [a["node_type"] for a in artifacts] == ["Footer", "Header"]
