"""종성 유지·쉼표·된소리·숫자 범위 회귀."""

from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r


def test_jongseong_kept_before_vowel():
    # 대상에서 — 종성 ㅇ(7)이 다음 에(n) 때문에 빠지지 않음
    assert r("irl7n,s") == "대상에서"
    assert r("l7ir^7o") == "상대방이"
    assert r("jbw") == "합의"
    assert r("jbwn") == "합의에"
    assert r(",[7cao") == "승낙이"


def test_ttense_ddaraseo():
    assert r(',i<"<,s') == "따라서"
    assert r(',i<"<' ) == "따라"
    assert r(',i<"[e*') == "따르면"
    # 암시 ㅏ: 된소리+ㄷ 만으로 따
    assert r(",i") == "따"


def test_comma_from_quote_cell():
    # ㄹ과 동일 셀인 “ — 음절이 아니면 쉼표
    assert r('oe:" ') == "이며, "
    assert r('`mas"') == "국어,"


def test_inline_number_range():
    assert r("#aj@9#ae") == "10~15"
    assert r("#aa@9#ae") == "11~15"
