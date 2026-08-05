# -*- coding: utf-8 -*-
"""과거형 어미·드문 음절(귿/옷) 역점역."""

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r


def test_past_hayeot_and_ieot():
    assert r("j:/,[bcoi") == "하였습니다"
    assert r("os/,[bcoi") == "이었습니다"
    assert r(":/,[bcoi") == "였습니다"
    assert r("j:/czin+") == "하였는데요"
    assert r(hangul_text_to_ascii("표기하였습니다")) == "표기하였습니다"
    assert r(hangul_text_to_ascii("발음하였습니다")) == "발음하였습니다"
    assert r(hangul_text_to_ascii("마찬가지였습니다")) == "마찬가지였습니다"


def test_jyeot_not_jayeot():
    """졌 = ㅈ+ㅕ+ㅆ. 자(.)+였으로 쪼개지 않음."""
    assert r(".:/") == "졌"
    assert r(hangul_text_to_ascii("졌")) == "졌"
    assert r(hangul_text_to_ascii("달라졌는지")) == "달라졌는지"
    assert "자였" not in r(hangul_text_to_ascii("달라졌는지"))
    assert r("j:/") == "하였"  # 하+였 만 예외 유지
    assert r(hangul_text_to_ascii("자음자")) == "자음자"


def test_hyeo_not_confused_with_hayeot():
    # 혀 = ㅎ+ㅕ (였 아님)
    assert r("j:") == "혀"
    assert r("j:a") == "혁"


def test_rare_syllables_geut_ot():
    assert r("`[9") == "귿"
    assert r("u'") == "옷"
    assert r(hangul_text_to_ascii("귿")) == "귿"
    assert r(hangul_text_to_ascii("옷")) == "옷"
    assert r(hangul_text_to_ascii("디귿")) == "디귿"
    assert r(hangul_text_to_ascii("시옷")) == "시옷"
    assert r(hangul_text_to_ascii("‘귿’")) == "‘귿’"
    assert r(hangul_text_to_ascii("‘옷’")) == "‘옷’"


def test_ss_final_not_ye_after_vowel():
    # 모음 뒤 / 는 종성 ㅆ (예로 재분석 금지)
    assert "예습" not in r("j:/,[bcoi")
    assert "여예" not in r(":/,[bcoi")
