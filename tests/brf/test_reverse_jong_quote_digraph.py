# -*- coding: utf-8 -*-
"""겹받침(ㄶ 등) + 닫는 따옴표 — 00/0' 가로채기 방지."""

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii as h
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r


def test_manheun_with_closing_single_quote_inside_word():
    """많’은: e300'z → ㄶ 겹받침 + 닫는 작은따옴표 (만”+고아 ' 아님)."""
    src = "많’은"
    assert h(src) == "e300'z"
    assert r(h(src)) == src
    assert r("e300'z") == "많’은"


def test_guest_many_market_sample():
    """①‘손님이 많’은 시장 — 사용자 제보 셀열."""
    src = "①‘손님이 많’은 시장"
    assert r(h(src)) == src
    assert r("7#a7,8,(co5o e300'z ,o.7") == src


def test_man_with_closing_double_quote_still_works():
    """만”=e300 은 겹받침을 취하지 않고 ㄴ+닫는 큰따옴표."""
    assert h("만”") == "e300"
    assert r(h("만”")) == "만”"
    assert r("e300") == "만”"


def test_manheun_with_closing_double_quote():
    """많”=e3000 → ㄶ + 00."""
    assert h("많”") == "e3000"
    assert r(h("많”")) == "많”"


def test_man_with_closing_single_quote():
    """만’=e30' → ㄴ + 0' (ㄶ로 묶지 않음)."""
    assert h("만’") == "e30'"
    assert r(h("만’")) == "만’"


def test_other_jieutnieun_digraph_before_quote():
    """않’ / 않’은 등 같은 받침 패턴."""
    assert r(h("않’")) == "않’"
    assert r(h("않’은")) == "않’은"
    assert r(h("<u>않은</u>")) == "<u>않은</u>"
