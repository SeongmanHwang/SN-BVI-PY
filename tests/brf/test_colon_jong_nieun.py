# -*- coding: utf-8 -*-
"""쌍점(⠐⠂ / \"1) ↔ 종성 ㄴ(⠒ / 3) — 서로 다른 기호."""

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii as h
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r


def test_colon_is_dot5_dot2_not_nieun_cell():
    """쌍점 = 5점+2점(\"1). 종성 ㄴ 셀(3)이 아님."""
    assert h(":") == '"1'
    assert h("사회:") == 'ljy"1'
    assert h("예:") == '/"1'
    assert not h("사회:").endswith("3")
    assert not h("예:").endswith("3")


def test_colon_roundtrip():
    for s in ["사회:", "예:", "선생님:", "학생:", "선생님: 발표", "사회: 발표"]:
        assert r(h(s)) == s


def test_jong_nieun_not_colon():
    """종성 ㄴ(3)은 쌍점으로 풀리지 않음."""
    assert h("한") == "j3"
    assert r("j3") == "한"
    assert r(h("대한")) == "대한"
    assert r(h("사회잔")) == "사회잔"
    assert r("ljy3") == "사횐"  # 회+ㄴ — 쌍점 아님
    assert ":" not in r("ljy3")


def test_legacy_double_dot2_colon():
    """일부 BRF의 ⠂⠂(11) 쌍점 관례도 인정."""
    assert r("11") == ":"
    assert r('ljy"1') == "사회:"
