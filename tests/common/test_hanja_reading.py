"""한자 → 음독 치환."""

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line
from korean_exam_braille.app.common.hanja_reading import (
    hanja_reading,
    replace_hanja_with_reading,
)


def test_single_hanja_readings():
    """① 한자 단독 → 음독 한글."""
    assert hanja_reading("漢") == "한"
    assert hanja_reading("字") == "자"
    assert replace_hanja_with_reading("漢字") == "한자"
    assert replace_hanja_with_reading("訓蒙字會") == "훈몽자회"


def test_redundant_paren_gloss_collapsed():
    """② 한글·한자 병기 → 한자 생략."""
    assert replace_hanja_with_reading("훈몽자회(訓蒙字會)") == "훈몽자회"
    assert replace_hanja_with_reading("한자(漢字)") == "한자"
    assert replace_hanja_with_reading("學校(학교)") == "학교"
    assert replace_hanja_with_reading("學校（학교）") == "학교"


def test_no_hanja_switch_indicator():
    """공식 한자 전환 표(⠴/`0` 전치)를 붙이지 않는다."""
    ascii_text = hangul_text_to_ascii("訓蒙字會")
    assert ascii_text == hangul_text_to_ascii("훈몽자회")
    assert not ascii_text.startswith("0")


def test_mixed_sentence_keeps_hangul():
    src = "지은 『훈몽자회(訓蒙字會)』에서 비롯된 것입니다."
    assert replace_hanja_with_reading(src) == "지은 『훈몽자회』에서 비롯된 것입니다."


def test_braille_encodes_hanja_via_reading():
    ascii_text = hangul_text_to_ascii("漢字")
    assert ascii_text == hangul_text_to_ascii("한자")
    assert "한자" in reverse_translate_line(ascii_text)

    full = hangul_text_to_ascii("훈몽자회(訓蒙字會)")
    assert full == hangul_text_to_ascii("훈몽자회")
    assert reverse_translate_line(full).replace(" ", "") == "훈몽자회"
