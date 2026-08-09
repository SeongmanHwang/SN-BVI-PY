"""종성 ㅇ(7) ↔ 드러냄+온표 자모(7=…7) 충돌."""

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii as h
from korean_exam_braille.app.brf.ascii_braille import unicode_to_ascii
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r


def test_circled_option_markers_after_ga_not_gang():
    """가 + ㉢ 점열 `$7=97` 이 강으로 먹히지 않는다."""
    ink = "㉠묘텅㉡백파가㉢언덕"
    ascii_text = h(ink)
    assert "77=37" in ascii_text  # 텅 ㅇ + 드러냄
    assert "$7=97" in ascii_text  # 가 다음 드러냄(종성 없음)
    assert r(ascii_text) == "‘ㄱ’묘텅‘ㄴ’백파가‘ㄷ’언덕"


def test_collapsed_ieung_emph_recovers_place_options():
    """압축·전위된 점열에서도 선택지 따옴표를 복원한다."""
    # 정방향보다 7 위치가 어긋난 참고 BRF 형태
    given = "7=a7e+hs7=37^rad$77=97)i?"
    assert r(given) == "‘ㄱ’묘텅‘ㄴ’백파가‘ㄷ’언덕"
    uni = "⠶⠿⠁⠶⠑⠬⠓⠎⠶⠿⠒⠶⠘⠗⠁⠙⠫⠶⠶⠿⠔⠶⠾⠊⠹"
    assert unicode_to_ascii(uni) == given
    assert r(unicode_to_ascii(uni)) == "‘ㄱ’묘텅‘ㄴ’백파가‘ㄷ’언덕"


def test_da_circled_giyeok_not_dang():
    """다㉠ → 당이 아니라 다‘ㄱ’."""
    assert r(h("다㉠")) == "다‘ㄱ’"
    assert r(h("묘㉠")) == "묘‘ㄱ’"


def test_proper_double_seven_mieum_option():
    """정상 이중 7(텅 ㅇ + 드러냄)은 그대로."""
    assert "e+hs77=37" in h("묘텅㉡")
    assert r(h("묘텅㉡")) == "묘텅‘ㄴ’"
