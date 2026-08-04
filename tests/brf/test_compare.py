"""BRF 비교 유틸 테스트."""

from korean_exam_braille.app.brf.compare import compare_brf_texts


def test_identical_texts_match():
    text = "abc\ndef\x0cghi"
    result = compare_brf_texts(text, text)
    assert result.matched_lines == 3
    assert result.cell_match_ratio == 1.0
    assert not result.diffs


def test_detects_line_difference():
    gen = "hello\nworld"
    ref = "hello\nworlx"
    result = compare_brf_texts(gen, ref)
    assert result.matched_lines == 1
    assert result.diffs
    assert result.diffs[0].line_index == 1
    assert result.cell_match_ratio < 1.0


def test_page_limit():
    gen = "a\x0cb\x0cc"
    ref = "a\x0cx\x0cy"
    result = compare_brf_texts(gen, ref, page_limit=1)
    assert result.generated_pages == 1
    assert result.matched_lines == 1
