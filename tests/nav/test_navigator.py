"""계층 탐색기 단위 테스트."""

from korean_exam_braille.app.exam.models import (
    ExamDocument,
    ExamNode,
    ExamRelation,
    SourceRange,
)
from korean_exam_braille.app.nav import TreeExamNavigator


def _sample_exam() -> ExamDocument:
    choices = [
        ExamNode(
            id=f"c{i}",
            node_type="Choice",
            source_range=SourceRange(raw_text=f"① 선택{i}"),
        )
        for i in range(1, 6)
    ]
    q1 = ExamNode(
        id="q1",
        node_type="Question",
        source_range=SourceRange(raw_text="1. 물음"),
        metadata={"question_number": 1},
        children=choices,
    )
    q2 = ExamNode(
        id="q2",
        node_type="Question",
        source_range=SourceRange(raw_text="2. 물음2"),
        metadata={"question_number": 2},
        children=[
            ExamNode(
                id="c9",
                node_type="Choice",
                source_range=SourceRange(raw_text="① 가"),
            )
        ],
    )
    group = ExamNode(
        id="g1",
        node_type="PassageGroup",
        source_range=SourceRange(raw_text="[1~2]"),
        children=[
            ExamNode(
                id="p1",
                node_type="Passage",
                source_range=SourceRange(raw_text="지문"),
            ),
            q1,
            q2,
        ],
    )
    root = ExamNode(
        id="exam-root",
        node_type="ExamDocument",
        source_range=SourceRange(),
        children=[group],
    )
    return ExamDocument(
        root=root,
        relations=[
            ExamRelation("refers_to_passage", "q1", "g1"),
            ExamRelation("refers_to_passage", "q2", "g1"),
        ],
    )


def test_bind_starts_at_first_navigable():
    nav = TreeExamNavigator()
    nav.bind(_sample_exam())
    loc = nav.location()
    assert loc is not None
    assert loc.node_type == "PassageGroup"
    assert loc.node_id == "g1"


def test_enter_child_and_parent():
    nav = TreeExamNavigator()
    nav.bind(_sample_exam())
    assert nav.first_child().node_type == "Passage"
    assert nav.parent().node_id == "g1"


def test_next_question_and_origin():
    nav = TreeExamNavigator()
    nav.bind(_sample_exam())
    nav.go("q1")
    nav.mark_origin()
    nxt = nav.next_of_type("Question")
    assert nxt is not None
    assert nxt.node_id == "q2"
    back = nav.go_origin()
    assert back is not None
    assert back.node_id == "q1"


def test_siblings_among_choices():
    nav = TreeExamNavigator()
    nav.bind(_sample_exam())
    nav.go("c1")
    assert nav.next_sibling().node_id == "c2"
    assert nav.prev_sibling().node_id == "c1"
    assert nav.prev_sibling() is None


def test_breadcrumb():
    nav = TreeExamNavigator()
    nav.bind(_sample_exam())
    loc = nav.go("c1")
    assert loc is not None
    types = [c.node_type for c in loc.breadcrumb]
    assert types == ["PassageGroup", "Question"]


def test_go_by_block_id():
    exam = _sample_exam()
    # attach block ids like the builder does
    exam.root.children[0].children[1].source_range.block_ids = ["pdf-b-q1"]
    exam.root.children[0].children[1].children[0].source_range.block_ids = [
        "pdf-b-c1"
    ]
    nav = TreeExamNavigator()
    nav.bind(exam)
    loc = nav.go_by_block_id("pdf-b-c1")
    assert loc is not None
    assert loc.node_id == "c1"
    loc_q = nav.go_by_block_id("pdf-b-q1")
    assert loc_q is not None
    assert loc_q.node_id == "q1"
