"""역점역: 복합 부호·온표·지문 범위."""

from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line


def test_single_quotes_around_letter_name():
    # ‘니은’ = ⠠⠦ + 니은 + ⠴⠄
    assert reverse_translate_line(",8coz0'") == "‘니은’"


def test_on_sign_vowel_inside_quotes():
    # ‘ㅣ’ = 여는따옴표 + 온표 + ㅣ + 닫는따옴표
    assert reverse_translate_line(",8=o0'") == "‘ㅣ’"
    assert reverse_translate_line(",8=[0'") == "‘ㅡ’"


def test_on_sign_without_false_ieung():
    # 온표+ㅣ 는 ‘이’가 아니라 자모 ㅣ
    assert reverse_translate_line(",8=o0'") != "‘이’"
    assert "이" not in reverse_translate_line(",8=o0'")


def test_double_corner_brackets_book_title():
    # 『훈몽자회』 — 닫는 부호가 회 받침으로 붙지 않아야 함
    assert reverse_translate_line(";8jge=.jy02") == "『훈몽자회』"


def test_passage_range_token():
    assert reverse_translate_line("82#a`9#c;0") == "[1~3]"
    assert reverse_translate_line("82#a@9#c;0") == "[1~3]"
    assert reverse_translate_line("82#a`9#c;04") == "[1~3]."


def test_unknown_not_middle_dot():
    out = reverse_translate_line("}")
    assert out.startswith("<U:")
    assert out != "·"


def test_ong_abbrev_still_works():
    # 온표 문맥이 아니면 = 은 옹
    assert reverse_translate_line("=") == "옹"


def test_ongho_not_read_as_on_sign_hieut():
    """옹호·옹호하고: =ju… 를 온표+ㅎ+오…로 읽지 않음 (⠿=`=` → 옹)."""
    from korean_exam_braille.app.braille.translator import hangul_text_to_ascii as h

    assert h("옹호하고") == "=juj`u"
    assert reverse_translate_line("=juj`u") == "옹호하고"
    assert reverse_translate_line(h("옹호하고")) == "옹호하고"
    assert reverse_translate_line(h("옹호")) == "옹호"
    src = "삶의 태도를 옹호하고 있다."
    assert reverse_translate_line(h(src)) == src
    assert (
        reverse_translate_line('l15w hriu"! =juj`u o/i 4')
        == "삶의 태도를 옹호하고 있다."
    )
