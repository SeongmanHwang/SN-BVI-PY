# -*- coding: utf-8 -*-
"""호환 자모·문장부호 정방향/역방향."""

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r


def test_compat_jamo_choseong_on_sign():
    """단독 자음 = 온표 + 초성 점형 (2017 개정)."""
    assert hangul_text_to_ascii("ㄱ") == "=@"
    assert hangul_text_to_ascii("ㄴ") == "=c"
    assert hangul_text_to_ascii("ㄷ") == "=i"
    assert hangul_text_to_ascii("ㄹ") == '="'
    assert hangul_text_to_ascii("ㅁ") == "=e"
    assert hangul_text_to_ascii("ㅅ") == "=,"
    assert hangul_text_to_ascii("ㅣ") == "=o"
    assert hangul_text_to_ascii("ㅡ") == "=["
    for jamo, ascii_body in [
        ("ㄱ", "=@"),
        ("ㄴ", "=c"),
        ("ㄷ", "=i"),
        ("ㄹ", '="'),
        ("ㅁ", "=e"),
        ("ㅅ", "=,"),
        ("ㅂ", "=^"),
        ("ㅇ", "=g"),
        ("ㅎ", "=j"),
    ]:
        assert r(ascii_body) == jamo, (jamo, ascii_body, r(ascii_body))


def test_quoted_standalone_nieun_not_nh():
    """‘ㄴ’ — 닫는따옴표 0'를 ㄶ(30)으로 탐욕 결합하지 않음."""
    assert r(",8=c0'") == "‘ㄴ’"
    assert r(",8=30'") == "‘ㄴ’"  # 구 종성 인코딩
    assert r(hangul_text_to_ascii("‘ㄴ’")) == "‘ㄴ’"
    assert "ㄶ" not in r(",8=30'")


def test_list_of_jamo_in_quotes():
    assert r(hangul_text_to_ascii("‘ㄴ, ㄹ, ㅁ’")) == "‘ㄴ, ㄹ, ㅁ’"
    assert r(hangul_text_to_ascii("‘ㄱ, ㄷ, ㅅ’")) == "‘ㄱ, ㄷ, ㅅ’"


def test_jongseong_on_sign_legacy_alias():
    """구 인코딩(온표+종성)도 역점역."""
    assert r("=a") == "ㄱ"
    assert r("=3") == "ㄴ"
    assert r("=5") == "ㅁ"
    assert r("=0") == "ㅎ"
    assert r("7=a7") == "‘ㄱ’"


def test_emphasis_marks_around_phrase():
    body = hangul_text_to_ascii("차자 표기")
    assert r("7" + body + "7") == "‘차자 표기’"
    assert r("7=@7") == "‘ㄱ’"


def test_jamo_in_quotes_like_letter_names():
    assert r(hangul_text_to_ascii("‘ㅣ’")) == "‘ㅣ’"
    assert r(hangul_text_to_ascii("‘ㄱ’")) == "‘ㄱ’"
    assert r(hangul_text_to_ascii("‘ㅡ’")) == "‘ㅡ’"


def test_common_punct_roundtrip():
    for s in ["·", "…", "—", "『』", "「」", "<>", "《》", "{}", "※", "“”"]:
        a = hangul_text_to_ascii(s)
        assert a, s
        assert r(a) == s, (s, a, r(a))


def test_no_question_mark_for_jamo():
    assert "?" not in hangul_text_to_ascii("ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ")
    assert "?" not in hangul_text_to_ascii("ㅏㅑㅓㅕㅗㅛㅜㅠㅡㅣ")


def test_vendor_error_patterns_fixed():
    """사용자가 보고한 옹<U:…> 패턴·구 종성 본문이 자모로 복원."""
    assert r("=@") == "ㄱ"
    assert r("=a") == "ㄱ"
    assert r("=c") == "ㄴ"
    assert r("=3") == "ㄴ"
    assert r("=e") == "ㅁ"
    assert r("=5") == "ㅁ"
    assert r("=,") == "ㅅ"
    assert "옹" not in r("=@")
    assert "옹" not in r("=a")
    assert "옹" not in r("=c")
