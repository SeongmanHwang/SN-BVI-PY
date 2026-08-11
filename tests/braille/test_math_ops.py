# -*- coding: utf-8 -*-
"""수표(#) 접두 수식 기호 정·역점역."""

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii as h
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r


def test_math_ops_with_number_sign():
    assert h("+") == "#5"
    assert h("−") == "#9"
    assert h("×") == "#*"
    assert h("÷") == "#//"
    assert h("=") == "#33"
    assert h("₩") == "#0@w"
    assert h("$") == "#0@s"
    for ink, ascii_body in [
        ("+", "#5"),
        ("−", "#9"),
        ("×", "#*"),
        ("÷", "#//"),
        ("=", "#33"),
        ("<", "#99"),
        (">", "#55"),
        ("₩", "#0@w"),
        ("$", "#0@s"),
    ]:
        assert r(ascii_body) == ink, (ink, ascii_body, r(ascii_body))


def test_formula_roundtrip():
    assert h("2+3=5") == "#b#5#c#33#e"
    assert r("#b#5#c#33#e") == "2+3=5"
    assert r(h("2+3=5")) == "2+3=5"
    assert r(h("2×3=6")) == "2×3=6"
    assert r(h("8÷2=4")) == "8÷2=4"


def test_digit_adjacent_compare_and_ascii_minus():
    assert h("2<3") == "#b#99#c"
    assert h("5>1") == "#e#55#a"
    assert h("2-1") == "#b#9#a"
    assert r(h("2<3")) == "2<3"
    assert r(h("2-1")) == "2−1"  # 역점역은 U+2212


def test_angle_brackets_for_bogi_unchanged():
    assert r(h("<보기>")) == "<보기>"
    assert h("<보기>").startswith("78")
    assert h("<보기>").endswith("07")


def test_bare_equals_still_ong_without_number_sign():
    """수표 없는 `=` 는 여전히 옹."""
    assert r("=") == "옹"
    assert r("#33") == "="


def test_currency_roundtrip():
    assert r(h("₩100")) == "₩100"
    assert r(h("$20")) == "$20"
