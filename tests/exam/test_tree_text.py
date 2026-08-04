"""Exam 트리 텍스트 테스트."""

from korean_exam_braille.app.exam.models import ExamDocument, ExamNode, ExamRelation, SourceRange
from korean_exam_braille.app.exam.tree_text import format_exam_summary, format_exam_tree


def test_format_tree_and_summary():
    q = ExamNode(
        id="q1",
        node_type="Question",
        source_range=SourceRange(raw_text="1. 물음"),
        metadata={"question_number": 1},
        children=[
            ExamNode(
                id="c1",
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
            q,
        ],
    )
    root = ExamNode(
        id="exam-root",
        node_type="ExamDocument",
        source_range=SourceRange(),
        children=[group],
    )
    exam = ExamDocument(
        root=root,
        relations=[
            ExamRelation(
                relation_type="refers_to_passage",
                source_id="q1",
                target_id="g1",
            )
        ],
    )
    tree = format_exam_tree(exam)
    assert "PassageGroup" in tree
    assert "Question #1" in tree
    assert "refers_to_passage" in tree
    assert "PassageGroup 1" in format_exam_summary(exam)
