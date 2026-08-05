"""Exam → DTBook 2005-3 구조 XML."""

from korean_exam_braille.app.daisy import ExamDtbookExporter, PreviewDtbookExporter
from korean_exam_braille.app.exam.models import ExamDocument, ExamNode, SourceRange


def _sample_exam() -> ExamDocument:
    return ExamDocument(
        root=ExamNode(
            id="root",
            node_type="ExamDocument",
            source_range=SourceRange(),
            children=[
                ExamNode(
                    id="pg1",
                    node_type="PassageGroup",
                    source_range=SourceRange(raw_text="[16~17]"),
                    metadata={"start_question": 16, "end_question": 17},
                    children=[
                        ExamNode(
                            id="pass1",
                            node_type="Passage",
                            source_range=SourceRange(raw_text="지문 본문입니다."),
                        ),
                        ExamNode(
                            id="q16",
                            node_type="Question",
                            source_range=SourceRange(raw_text="16. 물음"),
                            metadata={"question_number": 16},
                            children=[
                                ExamNode(
                                    id="c1",
                                    node_type="Choice",
                                    source_range=SourceRange(raw_text="① 갑"),
                                ),
                                ExamNode(
                                    id="c2",
                                    node_type="Choice",
                                    source_range=SourceRange(raw_text="② 을"),
                                ),
                            ],
                        ),
                    ],
                )
            ],
        )
    )


def test_exam_dtbook_structure():
    xml = ExamDtbookExporter().export(_sample_exam(), title="모의고사")
    assert xml.startswith("<?xml")
    assert "dtbook 2005-3" in xml
    assert 'version="2005-3"' in xml
    assert "dtbook-2005-3-structure" in xml
    assert "preview-not-final-schema" not in xml
    assert "지문 [16~17]" in xml or "PassageGroup" in xml
    assert "문항 16" in xml
    assert 'type="pl"' in xml
    assert "① 갑" in xml
    assert "<list" in xml


def test_preview_alias_same_class():
    assert issubclass(PreviewDtbookExporter, ExamDtbookExporter)
    xml = PreviewDtbookExporter().export(_sample_exam(), title="t")
    assert "dtbook-2005-3-structure" in xml
