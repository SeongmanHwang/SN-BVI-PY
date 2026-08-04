"""Prototype 3 종단 파이프라인 테스트."""

from pathlib import Path

import fitz
import pytest

from korean_exam_braille.app.pipeline import default_pipeline


@pytest.fixture
def passage_group_pdf(tmp_path: Path) -> Path:
    fontfile = Path(r"C:\Windows\Fonts\malgun.ttf")
    if not fontfile.exists():
        pytest.skip("malgun.ttf not found")
    path = tmp_path / "passage_group.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_font(fontname="f0", fontfile=str(fontfile))
    y = 72
    lines = [
        "[16~17] 다음 글을 읽고 물음에 답하시오.",
        "사람은 언어로 생각한다.",
        "16. 윗글의 중심 화제로 알맞은 것은?",
        "① 음악",
        "② 언어",
        "③ 역사",
        "④ 미술",
        "⑤ 체육",
        "17. 밑줄 친 말의 의미로 알맞은 것은?",
        "① 가",
        "② 나",
        "③ 다",
        "④ 라",
        "⑤ 마",
    ]
    for text in lines:
        page.insert_text((72, y), text, fontsize=11, fontname="f0")
        y += 22
    doc.save(path)
    doc.close()
    return path


def test_default_pipeline_builds_non_stub_tree(passage_group_pdf: Path):
    result = default_pipeline().run(passage_group_pdf, page_numbers=[1])
    assert "RuleExamStructureBuilder" in result.metadata["stages"]
    assert "TableBrailleTranslator" in result.metadata["stages"]
    assert "RuleBrailleLayoutEngine" in result.metadata["stages"]

    groups = [c for c in result.exam.root.children if c.node_type == "PassageGroup"]
    assert groups, "expected at least one PassageGroup"
    questions = [
        c for g in groups for c in g.children if c.node_type == "Question"
    ]
    assert len(questions) >= 1

    # BRF에 숫자 점자 흔적 (#) 또는 원문 점역 결과
    assert result.brf_text
    assert result.sequences
    assert result.braille_document.pages
    # 문항 번호 점역: # + digit cells
    assert "#" in result.brf_text or any(
        "#" in (s.metadata.get("ascii") or "") for s in result.sequences
    )


def test_relations_present(passage_group_pdf: Path):
    result = default_pipeline().run(passage_group_pdf)
    assert result.exam.relations
    assert all(r.relation_type == "refers_to_passage" for r in result.exam.relations)
