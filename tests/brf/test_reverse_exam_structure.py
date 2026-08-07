# -*- coding: utf-8 -*-
"""시험지 구조 부호: 보기·대괄호·쌍점·범위·표선."""

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r


def test_example_box_title():
    assert r(hangul_text_to_ascii("<보기>")) == "<보기>"
    assert r("78^u@o07") == "<보기>"


def test_score_bracket():
    assert "?<U:2>" not in r(hangul_text_to_ascii("[3점]"))
    assert r(hangul_text_to_ascii("[3점]")).replace(" ", "") == "[3점]"
    assert r("82#c.s5;0") == "[3점]"


def test_speaker_colon():
    assert r(hangul_text_to_ascii("선생님: 발표")) == "선생님: 발표"
    assert r("11") == ":"
    assert ",," not in r(hangul_text_to_ascii("선생님:"))


def test_letter_range_tilde():
    assert hangul_text_to_ascii("~") == "@9"
    assert r("@9") == "~"
    # 로마자는 로마자표(0)와 함께 — 표지 없는 a/e 는 한글로 보지 않음
    assert hangul_text_to_ascii("‘a’~‘e’") == ",80a0'@9,80e0'"
    assert r(",80a0'@9,80e0'") == "‘a’~‘e’"
    assert r(hangul_text_to_ascii("‘a’~‘e’")) == "‘a’~‘e’"


def test_quoted_eun_vs_latin_z():
    """은 약자 z vs 로마자 z — 로마자표 유무로 구분."""
    assert hangul_text_to_ascii("‘은’") == ",8z0'"
    assert r(",8z0'") == "‘은’"
    assert hangul_text_to_ascii("‘z’") == ",80z0'"
    assert r(",80z0'") == "‘z’"
    src = "초성 소릿값을, ‘隱(은)’은 ‘ㄴ’의"
    assert r(hangul_text_to_ascii(src)) == "초성 소릿값을, ‘은’은 ‘ㄴ’의"


def test_table_rule_lines():
    assert r("!" + "3" * 20 + "4") == "─" * 16
    assert r("0" + "3" * 20 + "j") == "─" * 16
    assert "을" not in r("!" + "3" * 20 + "4")
    assert "하" not in r("0" + "3" * 20 + "j")


def test_inline_decorative_skip_around_example():
    body = hangul_text_to_ascii("<보기>")
    line = "g" * 8 + body + "g" * 8
    assert "<보기>" in r(line)
    assert "운" not in r(line)
