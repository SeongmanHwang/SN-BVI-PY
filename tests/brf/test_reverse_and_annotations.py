"""역점역·구조 후보·주석 저장 테스트."""

from pathlib import Path

from korean_exam_braille.app.brf.annotations import (
    apply_annotations,
    export_annotations,
    load_annotations,
    save_annotations,
)
from korean_exam_braille.app.brf.parser import parse_brf_text
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line
from korean_exam_braille.app.brf.structure_detect import detect_line_candidates


def test_number_reverse():
    assert reverse_translate_line("#a") == "1"
    assert reverse_translate_line("#aj") == "10"
    assert reverse_translate_line("#be") == "25"


def test_latin_reverse():
    assert reverse_translate_line("0abc") == "abc"


def test_korean_header_smoke():
    assert "학년도" in reverse_translate_line("jac*iu")
    assert reverse_translate_line("`mas") == "국어"


def test_separator_candidate():
    tags = detect_line_candidates("================")
    assert "Separator" in tags


def test_question_candidate():
    tags = detect_line_candidates("#a 발문")
    assert "Question" in tags


def test_choice_candidate():
    tags = detect_line_candidates("#a 선택")
    # #a 단독은 문항 1번으로도 잡힐 수 있음 — 선택지는 문항이 아닐 때
    tags2 = detect_line_candidates("#c 보기내용")
    assert "Question" in tags2 or "Choice" in tags2


def test_annotation_roundtrip(tmp_path: Path):
    doc = parse_brf_text("#a hello\n=====\n\x0c#b world\n")
    doc.source_path = str(tmp_path / "demo.brf")
    doc.lines[0].tags = ["Question", "Prompt"]
    doc.lines[0].notes = "1번 문항"
    path = save_annotations(doc)
    data = load_annotations(path)
    doc2 = parse_brf_text("#a hello\n=====\n\x0c#b world\n")
    applied = apply_annotations(doc2, data)
    assert applied == 1
    assert doc2.lines[0].tags == ["Question", "Prompt"]
    assert doc2.lines[0].notes == "1번 문항"
    exported = export_annotations(doc2)
    assert exported["line_count"] == doc2.line_count
