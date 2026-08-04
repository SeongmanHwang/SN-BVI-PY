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


def test_circled_choice_to_hash_digit():
    ascii_text = hangul_text_to_ascii("① 선택")
    assert ascii_text.startswith("#1")
