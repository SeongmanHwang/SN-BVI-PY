"""정방향 점역 테스트."""

from korean_exam_braille.app.braille.translator import (
    TableBrailleTranslator,
    hangul_text_to_ascii,
)
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line


def test_number_and_simple_syllables():
    ascii_text = hangul_text_to_ascii("가나다 12")
    assert "#" in ascii_text
    assert ascii_text.startswith("$")  # 가 약자
    assert "c" in ascii_text  # 나
    assert "i" in ascii_text  # 다


def test_number_run_inserts_space_before_following_letters():
    """숫자열 뒤 한글·영문 앞에는 수표 종료용 빈칸 하나."""
    assert hangul_text_to_ascii("12가") == "#ab $"
    assert hangul_text_to_ascii("제1교시") == ".n#a `+,o"
    assert hangul_text_to_ascii("2026학년도").startswith("#bjbf ")
    # 이미 공백이면 추가하지 않음
    assert hangul_text_to_ascii("12 가") == "#ab $"
    # 구두점에는 붙임
    assert hangul_text_to_ascii("3)") == "#c,0"
    # 대괄호 점수 표기는 참고 BRF처럼 공백 없이
    assert hangul_text_to_ascii("[3점]") == "82#c.s5;0"
    # 괄호 밖 단위는 빈칸
    assert hangul_text_to_ascii("3점").startswith("#c ")


def test_haknyeondo_uses_vc_abbrev():
    ascii_text = hangul_text_to_ascii("학년도")
    assert "jac*iu" in ascii_text or "jac*" in ascii_text


def test_passage_range_and_question_number():
    ascii_text = hangul_text_to_ascii("[1~3] 다음")
    assert ascii_text.startswith("82#a`9#c;0")
    q = hangul_text_to_ascii("1. 물음")
    assert q.startswith("#a4")


def test_roundtrip_smoke_simple_words():
    for src in ["가", "나", "다", "그리고", "하나"]:
        ascii_text = hangul_text_to_ascii(src)
        back = reverse_translate_line(ascii_text)
        assert src in back or back.replace(" ", "") == src.replace(" ", "")


def test_translator_fills_cells():
    tr = TableBrailleTranslator()
    seq = tr.translate_text("가나다")
    assert seq.tokens
    assert seq.tokens[0].cells
    assert seq.metadata.get("ascii")


def test_circled_choice_to_marked_digit():
    ascii_text = hangul_text_to_ascii("① 선택")
    assert ascii_text.startswith("7#a7")
    assert reverse_translate_line(ascii_text).startswith("①")
    assert hangul_text_to_ascii("③").startswith("7#c7")
    assert reverse_translate_line("7#e7") == "⑤"


def test_circled_hangul_and_underline_emphasis():
    """참고 BRF: ㉠<u>차자 표기</u> → 7=a7,-;<. d+`o-'"""
    assert hangul_text_to_ascii("㉠") == "7=a7"
    assert hangul_text_to_ascii("㉡") == "7=37"
    assert hangul_text_to_ascii("㉢") == "7=97"
    body = hangul_text_to_ascii("차자 표기")
    assert hangul_text_to_ascii("<u>차자 표기</u>") == ",-" + body + "-'"
    assert hangul_text_to_ascii("㉠<u>차자 표기</u>") == "7=a7,-;<. d+`o-'"
