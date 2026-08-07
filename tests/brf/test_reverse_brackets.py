"""대괄호·원문자·조사 복귀·강조."""

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r


def test_square_brackets_and_particles():
    assert r(hangul_text_to_ascii("[A]")) == "[A]"
    assert r(hangul_text_to_ascii("[A]의")) == "[A]의"
    assert r(hangul_text_to_ascii("[A], [B]에 대한")) == "[A], [B]에 대한"
    # 참고 BRF 관례 82…;0
    assert r("820,a;0w") == "[A]의"


def test_bracket_uri_mal_not_middot():
    """[우리말]: 종성 ㄹ(1)+;0(]) 이 가운뎃점 1; 보다 우선.

    회귀: 82m\"oe1;0 → [우리마·<U:0> (잘못)
    """
    ascii_text = '82m"oe1;0'
    assert hangul_text_to_ascii("[우리말]") == ascii_text
    assert r(ascii_text) == "[우리말]"
    assert r(hangul_text_to_ascii("[우리말]")) == "[우리말]"
    assert r(hangul_text_to_ascii("[향찰 표기]")) == "[향찰 표기]"
    # 단독 1;0 도 · 로 훔치지 않음 (1 → 쉼표 잔여, ;0 → ])
    assert r("1;0") == ",]"
    # 진짜 가운뎃점은 뒤에 0이 없을 때
    assert r("1;") == "·"
    assert r("e1;0") == "말]"


def test_circled_digits():
    for ink, cell in zip("①②③④⑤", "abcde"):
        assert r(f"7#{cell}7") == ink
        assert hangul_text_to_ascii(ink) == f"7#{cell}7"
    # 참고 시험지: ⠼⠂…⠼⠢
    for ink, cell in zip("①②③④⑤", "12345"):
        assert r(f"#{cell}") == ink


def test_choice_item_mark_stripped():
    hangul = hangul_text_to_ascii("한글")
    assert r("#1_0 " + hangul) == "① 한글"
    assert r("#2_0" + hangul) == "② 한글"
    assert "_<" not in r("#3_0 " + hangul)


def test_student_in_quotes_after_bracket():
    src = "[B]의 ‘학생 2’는"
    assert r(hangul_text_to_ascii(src)) == src


def test_emphasis_markers_to_underline_tags():
    """점역 강조부호(,- … -') → 역점역 <u>…</u>."""
    assert r(",-<30z-'") == "<u>않은</u>"
    assert r(hangul_text_to_ascii("<u>차자 표기</u>")) == "<u>차자 표기</u>"
    # ㉠ → 드러냄+자모(‘ㄱ’); 밑줄 구간만 <u>로 복원
    assert "<u>차자 표기</u>" in r(hangul_text_to_ascii("㉠<u>차자 표기</u>"))


def test_passage_range_not_confused_with_bracket():
    assert hangul_text_to_ascii("[1~3]").startswith("82#")
    assert r(hangul_text_to_ascii("[1~3]")) == "[1~3]"


def test_question_with_brackets_line():
    src = "5. [A], [B]에 대한 설명으로 적절하지 않은 것은?"
    assert r(hangul_text_to_ascii(src)) == src
