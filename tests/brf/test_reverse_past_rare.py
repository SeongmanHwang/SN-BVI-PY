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
    """졌 = ㅈ+붙임줄+ㅕ+ㅆ. 자(.)+였으로 쪼개지 않음."""
    assert hangul_text_to_ascii("졌") == ".-:/"
    assert r(".-:/") == "졌"
    assert r(".:/") == "졌"  # 레거시(붙임줄 없음)
    assert r(hangul_text_to_ascii("졌")) == "졌"
    assert r(hangul_text_to_ascii("달라졌는지")) == "달라졌는지"
    assert "자였" not in r(hangul_text_to_ascii("달라졌는지"))
    assert r("j:/") == "하였"  # 하+였 만 예외 유지
    assert r(hangul_text_to_ascii("자음자")) == "자음자"


def test_hyeoss_coupling_not_hayeot():
    """혔 = 245+36+156+34 (j-:/). 하+였(j:/)과 구분."""
    assert hangul_text_to_ascii("혔") == "j-:/"
    assert r("j-:/") == "혔"
    assert r(hangul_text_to_ascii("혔")) == "혔"
    assert r("j:/") == "하였"
    assert r(hangul_text_to_ascii("하였")) == "하였"


def test_yeoss_coupling_family():
    """셨·뎠·졌·켰·폈도 초성·ㅕ 사이에 붙임줄을 둔다."""
    for syl, ascii_expect in (
        ("셨", ",-:/"),
        ("뎠", "i-:/"),
        ("졌", ".-:/"),
        ("켰", "f-:/"),
        ("폈", "d-:/"),
        ("혔", "j-:/"),
    ):
        assert hangul_text_to_ascii(syl) == ascii_expect, syl
        assert r(ascii_expect) == syl, syl
        assert r(hangul_text_to_ascii(syl)) == syl, syl


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


def test_ye_coupling_after_open_syllable():
    """받침 없는 음절 + 예 → 붙임줄. 유예≠윴, 개예≠갰."""
    assert hangul_text_to_ascii("유예") == "%-/"
    assert hangul_text_to_ascii("개예") == "`r-/"
    assert hangul_text_to_ascii("예") == "/"
    assert hangul_text_to_ascii("예정") == "/.s7"
    assert hangul_text_to_ascii("온예") == "(/"
    assert r("%-/") == "유예"
    assert r("`r-/") == "개예"
    assert r(hangul_text_to_ascii("유예")) == "유예"
    assert r(hangul_text_to_ascii("유예기간")) == "유예기간"
    assert r(hangul_text_to_ascii("예정")) == "예정"
    assert r(hangul_text_to_ascii("온예")) == "온예"
    # 레거시(붙임줄 없음)는 종성 ㅆ으로 남음
    assert r("%/") == "윴"
