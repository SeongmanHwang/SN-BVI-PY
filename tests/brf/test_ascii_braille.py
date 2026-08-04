"""ASCII ↔ 유니코드 점자 변환 테스트."""

from korean_exam_braille.app.brf.ascii_braille import (
    BRAILLE_ASCII_TABLE,
    ascii_to_unicode,
    roundtrip_ok,
    unicode_to_ascii,
)


def test_table_length():
    assert len(BRAILLE_ASCII_TABLE) == 64


def test_space_is_blank_cell():
    assert ascii_to_unicode(" ") == "\u2800"


def test_letter_a():
    assert ascii_to_unicode("a") == "⠁"
    assert ascii_to_unicode("A") == "⠁"


def test_roundtrip_basic():
    sample = " #a ,hello="
    assert roundtrip_ok(sample)
    back = unicode_to_ascii(ascii_to_unicode(sample))
    # 대문자는 소문자 셀로 정규화
    assert back == " #a ,hello="


def test_formfeed_preserved():
    text = "abc\x0cdef"
    assert ascii_to_unicode(text) == "⠁⠃⠉\x0c⠙⠑⠋"
