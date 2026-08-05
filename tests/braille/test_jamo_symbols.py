# -*- coding: utf-8 -*-
"""호환 자모·문장부호 정방향/역방향."""

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r


def test_compat_jamo_jongseong_on_sign():
    """단독 자음 = 온표 + 종성 점형 (참고 BRF)."""
    assert hangul_text_to_ascii("ㄱ") == "=a"
    assert hangul_text_to_ascii("ㄴ") == "=3"
    assert hangul_text_to_ascii("ㄷ") == "=9"
    assert hangul_text_to_ascii("ㄹ") == "=1"
    assert hangul_text_to_ascii("ㅁ") == "=5"
    assert hangul_text_to_ascii("ㅅ") == "='"
    assert hangul_text_to_ascii("ㅣ") == "=o"
    assert hangul_text_to_ascii("ㅡ") == "=["
    for jamo, ascii_body in [
        ("ㄱ", "=a"),
        ("ㄴ", "=3"),
        ("ㄷ", "=9"),
        ("ㄹ", "=1"),
        ("ㅁ", "=5"),
        ("ㅅ", "='"),
        ("ㅂ", "=b"),
        ("ㅇ", "=g"),
    ]:
        assert r(ascii_body) == jamo, (jamo, ascii_body, r(ascii_body))


def test_quoted_standalone_nieun_not_nh():
    """‘ㄴ’ — 닫는따옴표 0'를 ㄶ(30)으로 탐욕 결합하지 않음."""
    assert r(",8=30'") == "‘ㄴ’"
    assert r(hangul_text_to_ascii("‘ㄴ’")) == "‘ㄴ’"
    assert "ㄶ" not in r(",8=30'")


def test_list_of_jamo_in_quotes():
    assert r(hangul_text_to_ascii("‘ㄴ, ㄹ, ㅁ’")) == "‘ㄴ, ㄹ, ㅁ’"
    assert r(hangul_text_to_ascii("‘ㄱ, ㄷ, ㅅ’")) == "‘ㄱ, ㄷ, ㅅ’"


def test_choseong_on_sign_alias():
    """구 인코딩(온표+초성)도 역점역."""
    assert r("=@") == "ㄱ"
    assert r("=c") == "ㄴ"
    assert r('="') == "ㄹ"


def test_emphasis_marks_around_phrase():
    body = hangul_text_to_ascii("차자 표기")
    assert r("7" + body + "7") == "‘차자 표기’"
    assert r("7=a7") == "‘ㄱ’"


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
    """사용자가 보고한 옹<U:…> 패턴이 자모로 복원."""
    assert r("=a") == "ㄱ"
    assert r("=3") == "ㄴ"
    assert r("=9") == "ㄷ"
    assert r("=1") == "ㄹ"
    assert r("=5") == "ㅁ"
    assert r("='") == "ㅅ"
    assert "옹" not in r("=a")
    assert "옹" not in r("=3")
