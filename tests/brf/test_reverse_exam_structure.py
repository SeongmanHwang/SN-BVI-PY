# -*- coding: utf-8 -*-
"""시험지 구조 부호: 보기·대괄호·쌍점·범위·표선·한자."""

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii
from korean_exam_braille.app.brf.reverse_translator import (
    _cleanup_hanja_placeholders,
    reverse_translate_line as r,
)


def test_example_box_title():
    assert r(hangul_text_to_ascii("<보기>")) == "<보기>"
    assert r("78^u@o07") == "<보기>"
    # 참고 BRF: 쉼표+따옴표 관례
    assert r("1,8^u@o0'1") == "<보기>"


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
    assert r(",8a0'@9,8e0'") == "‘a’~‘e’"
    assert r(hangul_text_to_ascii("‘a’~‘e’")) == "‘a’~‘e’"
    assert "<U:@>" not in r(",8a0'@9,8e0'")


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


def test_hanja_placeholder():
    assert (
        _cleanup_hanja_placeholders("옽<U:'>(나-오), 은(숨을-은)")
        == "<한자>(나-오), 은(숨을-은)"
    )
    # 정상 한글 라벨은 유지
    assert _cleanup_hanja_placeholders("음(마실-음)") == "음(마실-음)"
