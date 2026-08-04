"""BRF 파서 무손실 로딩 테스트."""

from pathlib import Path

from korean_exam_braille.app.brf.parser import load_brf, parse_brf_text, serialize_brf


def test_empty_lines_preserved():
    text = "a\n\nb\n"
    doc = parse_brf_text(text)
    assert doc.page_count == 1
    assert [line.raw_ascii for line in doc.pages[0].lines] == ["a", "", "b"]


def test_formfeed_pages():
    text = "page1\n\x0cpage2\n"
    doc = parse_brf_text(text)
    assert doc.page_count == 2
    assert doc.pages[0].lines[0].raw_ascii == "page1"
    assert doc.pages[1].lines[0].raw_ascii == "page2"
    assert doc.pages[0].lines[0].page_index == 0
    assert doc.pages[1].lines[0].page_index == 1


def test_global_index_continuous():
    text = "a\nb\n\x0cc\n"
    doc = parse_brf_text(text)
    indices = [line.global_index for line in doc.lines]
    assert indices == list(range(len(indices)))


def test_serialize_roundtrip_lines(tmp_path: Path):
    original = "#a hello\n\n#b world\n\x0c#c next\n=====\n"
    doc = parse_brf_text(original)
    out = serialize_brf(doc)
    doc2 = parse_brf_text(out)
    assert [line.raw_ascii for line in doc.lines] == [
        line.raw_ascii for line in doc2.lines
    ]
    assert doc.page_count == doc2.page_count


def test_load_fixture():
    fixture = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "sample.brf"
    doc = load_brf(fixture)
    assert doc.page_count >= 2
    assert doc.line_count > 0
    assert any(line.candidate_tags for line in doc.lines)
