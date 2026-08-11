"""대괄호·원문자·조사 복귀·강조."""

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r


def test_square_brackets_and_particles():
    assert r(hangul_text_to_ascii("[A]")) == "[A]"
    assert r(hangul_text_to_ascii("[A]의")) == "[A]의"
    assert r(hangul_text_to_ascii("[A], [B]에 대한")) == "[A], [B]에 대한"
    # 참고 BRF 관례 82…;0
    assert r("820,a;0w") == "[A]의"


def test_jong_digraph_18_yields_to_square_bracket_pair():
    """겹받침 18(ㄾ)이 여는 대괄호 82 를 훔치지 않는다.

    뒤에 ;0 이 있으면 1=종성 ㄹ, 82=[ 로 나눈다.
    회귀: <4o182<5co1;0 → 앞잁<U:2>암닐] (잘못)
    """
    from korean_exam_braille.app.brf.ascii_braille import unicode_to_ascii

    assert r("<4o182<5co1;0") == "앞일[암닐]"
    uni = "⠣⠲⠕⠂⠦⠆⠣⠢⠉⠕⠂⠰⠴"
    assert r(unicode_to_ascii(uni)) == "앞일[암닐]"
    # 닫는 ] 없으면 기존처럼 ㄾ 겹받침
    assert r("o18") == "잁"


def test_bracket_uri_mal_not_middot():
    """[우리말]: 종성 ㄹ(1)+;0(]) 이 음절로 복원된다.

    가운뎃점은 \"2(⠐⠆)이므로 1;0 과 충돌하지 않는다.
    """
    ascii_text = '82m"oe1;0'
    assert hangul_text_to_ascii("[우리말]") == ascii_text
    assert r(ascii_text) == "[우리말]"
    assert r(hangul_text_to_ascii("[우리말]")) == "[우리말]"
    assert r(hangul_text_to_ascii("[향찰 표기]")) == "[향찰 표기]"
    assert r("1;0") == ",]"
    assert r('"2') == "·"
    assert r("e1;0") == "말]"
    # 구관례 1; 는 더 이상 가운뎃점이 아님 (ㄹ+ㅊ 셀열)
    assert r("1;") != "·"

def test_circled_digits():
    for ink, cell in zip("①②③④⑤", "abcde"):
        assert r(f"7#{cell}7") == ink
        assert hangul_text_to_ascii(ink) == f"7#{cell}7"
    # 참고 시험지: ⠼⠂…⠼⠲ → ①…④. #5(⠼⠢)는 수식 +
    for ink, cell in zip("①②③④", "1234"):
        assert r(f"#{cell}") == ink
    assert r("#5") == "+"


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


def test_hangul_indicator_after_circled_latin():
    """2024 제39항 한글표 ,- : ⓐ + 한글표 + 아직 → ⓐ아직 (사직 아님)."""
    # 참고 BRF 관례: 7a7,-<.oa
    assert r("7a7,-<.oa") == "ⓐ아직"
    # 한글표 없이도 역점역은 가능 (정방향은 표를 안 넣음)
    assert r("7a7<.oa") == "ⓐ아직"
    # 셨(ㅅ+붙임+ㅕ+ㅆ)은 유지
    assert r(",-:/") == "셨"
    assert hangul_text_to_ascii("셨") == ",-:/"


def test_passage_range_not_confused_with_bracket():
    assert hangul_text_to_ascii("[1~3]").startswith("82#")
    assert r(hangul_text_to_ascii("[1~3]")) == "[1~3]"


def test_question_with_brackets_line():
    src = "5. [A], [B]에 대한 설명으로 적절하지 않은 것은?"
    assert r(hangul_text_to_ascii(src)) == src
