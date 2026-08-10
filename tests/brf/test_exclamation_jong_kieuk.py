# -*- coding: utf-8 -*-
"""종성 ㅋ(6) ↔ 느낌표(6) 구분 — ㅍ/마침표와 같은 어절 길이 규칙."""

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii as h
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r


def test_short_word_exclamation_inserts_space():
    """두 음절 이하 어절 뒤 느낌표 → 점역 시 앞에 공백."""
    assert h("가!") == "$ 6"
    assert h("다!") == "i 6"
    assert h("안녕!").endswith(" 6")


def test_long_word_exclamation_no_space():
    """세 음절 이상 어절 뒤 느낌표 → 공백 없음."""
    assert h("합니다!") == "jbcoi6"
    assert " " not in h("합니다!")
    assert h("것입니다!")[-1] == "6"
    assert " 6" not in h("것입니다!")


def test_jong_kieuk_no_space():
    """종성 ㅋ 음절은 공백 없이 6."""
    assert h("갘") == "$6"
    assert " " not in h("갘")
    assert h("앜") == "<6"


def test_reverse_short_bare_6_is_jong():
    """짧은 어절 + 공백 없는 6 → 종성 ㅋ."""
    assert r("$6") == "갘"
    assert r("<6") == "앜"


def test_reverse_short_spaced_6_is_exclamation():
    """짧은 어절 + 공백 + 6 → 느낌표."""
    assert r("$ 6") == "가!"
    assert r("i 6") == "다!"
    assert r(h("가!")) == "가!"
    assert r(h("다!")) == "다!"


def test_reverse_long_bare_6_is_exclamation():
    """긴 어절 + 공백 없는 6 → 느낌표."""
    assert r(h("합니다!")) == "합니다!"
    assert r("jbcoi6") == "합니다!"


def test_roundtrip_kieuk_and_exclamation():
    assert r(h("갘")) == "갘"
    assert r(h("가!")) == "가!"
    assert r(h("앜")) == "앜"
    assert r(h("아!")) == "아!"
    assert h("갘") != h("가!")
