# -*- coding: utf-8 -*-
"""종성 ㅍ(4) ↔ 마침표(4) 구분."""

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii as h
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r


def test_short_word_period_inserts_space():
    """두 음절 이하 어절 뒤 마침표 → 점역 시 앞에 공백."""
    assert h("다.") == "i 4"
    assert h("가.") == "$ 4"
    assert h("안녕.").endswith(" 4")
    assert " 4" in h("옆.")


def test_long_word_period_no_space():
    """세 음절 이상 어절 뒤 마침표 → 공백 없음."""
    assert h("합니다.") == "jbcoi4"
    assert " " not in h("합니다.")
    assert h("것입니다.")[-1] == "4"
    assert " 4" not in h("것입니다.")


def test_jong_pieup_no_space():
    """종성 ㅍ 단어는 공백 없이 4."""
    assert h("앞") == "<4"
    assert " " not in h("앞")
    assert h("수첩") == ",m;sb"  # no trailing bare 4 as period


def test_reverse_short_bare_4_is_jong():
    """짧은 어절 + 공백 없는 4 → 종성 ㅍ."""
    assert r("<4") == "앞"
    assert r("$4") == "갚"  # 가+ㅍ (옛 '가.' 인코딩과 구분)


def test_reverse_short_spaced_4_is_period():
    """짧은 어절 + 공백 + 4 → 마침표."""
    assert r("i 4") == "다."
    assert r("$ 4") == "가."
    assert r(h("다.")) == "다."
    assert r(h("가.")) == "가."


def test_reverse_long_bare_4_is_period():
    """긴 어절 + 공백 없는 4 → 마침표."""
    assert r(h("합니다.")) == "합니다."
    assert r("jbcoi4") == "합니다."


def test_roundtrip_ap_and_period():
    assert r(h("앞")) == "앞"
    assert r(h("아.")) == "아."
    assert r(h("옆.")) == "옆."
    assert h("앞") != h("아.")
