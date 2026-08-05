"""대괄호·원문자·조사 복귀·강조."""

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r


def test_square_brackets_and_particles():
    assert r(hangul_text_to_ascii("[A]")) == "[A]"
    assert r(hangul_text_to_ascii("[A]의")) == "[A]의"
    assert r(hangul_text_to_ascii("[A], [B]에 대한")) == "[A], [B]에 대한"
    # 참고 BRF 관례 82…;0
    assert r("820,a;0w") == "[A]의"


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


def test_emphasis_markers_stripped():
    assert r(",-<30z-'") == "않은"


def test_passage_range_not_confused_with_bracket():
    assert hangul_text_to_ascii("[1~3]").startswith("82#")
    assert r(hangul_text_to_ascii("[1~3]")) == "[1~3]"


def test_question_with_brackets_line():
    src = "5. [A], [B]에 대한 설명으로 적절하지 않은 것은?"
    assert r(hangul_text_to_ascii(src)) == src
