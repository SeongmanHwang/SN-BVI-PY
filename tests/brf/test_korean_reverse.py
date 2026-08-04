"""한국 점자 역점역 테스트."""

from korean_exam_braille.app.brf.ascii_braille import normalize_brf_ascii
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line


def test_backtick_is_choseong_gieul():
    assert normalize_brf_ascii("`u") == "@u"
    assert reverse_translate_line("`u") == "고"


def test_exam_title_fragments():
    assert reverse_translate_line("#bjbf") == "2026"
    assert reverse_translate_line("jac*iu") == "학년도"
    assert reverse_translate_line("#fp1") == "6월" or reverse_translate_line("#f") == "6"
    assert reverse_translate_line("p1") == "월"
    assert reverse_translate_line("`mas") == "국어"
    assert reverse_translate_line("]:a") == "영역"
    assert reverse_translate_line(".n") == "제"


def test_exam_header_line():
    assert reverse_translate_line("#bjbf jac*iu #fp1 `u#b") == "2026 학년도 6월 고2"
    assert reverse_translate_line("            `mas ]:a").strip() == "국어 영역"
    assert reverse_translate_line("            .n#a`+,o").strip() == "제1교시"


def test_word_abbrev_and_geot():
    assert reverse_translate_line("au") == "그리고"
    assert reverse_translate_line("_s") == "것"


def test_period_not_final_pieup():
    # 답하시오.
    assert reverse_translate_line("ibj,ou4") == "답하시오."


def test_separator_preserved():
    line = "=gggggggggggggggggggggggggggggg="
    assert reverse_translate_line(line) == line


def test_numbers_and_latin():
    assert reverse_translate_line("#aj") == "10"
    assert reverse_translate_line("0abc") == "abc"
    assert reverse_translate_line(";,a") == "A"
