"""정방향 점역 테스트."""

from korean_exam_braille.app.braille.translator import (
    TableBrailleTranslator,
    hangul_text_to_ascii,
)
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line
from korean_exam_braille.app.exam.models import ExamNode, SourceRange
from korean_exam_braille.app.layout.engine import RuleBrailleLayoutEngine


def test_number_and_simple_syllables():
    ascii_text = hangul_text_to_ascii("가나다 12")
    assert "#" in ascii_text
    assert ascii_text.startswith("$")  # 가 약자
    assert "c" in ascii_text  # 나
    assert "i" in ascii_text  # 다


def test_number_run_inserts_space_before_following_letters():
    """숫자열 뒤 한글·영문 앞에는 수표 종료용 빈칸 하나."""
    assert hangul_text_to_ascii("12가") == "#ab $"
    assert hangul_text_to_ascii("제1교시") == ".n#a `+,o"
    assert hangul_text_to_ascii("2026학년도").startswith("#bjbf ")
    # 이미 공백이면 추가하지 않음
    assert hangul_text_to_ascii("12 가") == "#ab $"
    # 구두점에는 붙임
    assert hangul_text_to_ascii("3)") == "#c,0"
    # 대괄호 점수 표기는 참고 BRF처럼 공백 없이
    assert hangul_text_to_ascii("[3점]") == "82#c.s5;0"
    # 괄호 밖 단위는 빈칸
    assert hangul_text_to_ascii("3점").startswith("#c ")


def test_haknyeondo_uses_vc_abbrev():
    ascii_text = hangul_text_to_ascii("학년도")
    assert "jac*iu" in ascii_text or "jac*" in ascii_text


def test_passage_range_and_question_number():
    ascii_text = hangul_text_to_ascii("[1~3] 다음")
    assert ascii_text.startswith("82#a`9#c;0")
    q = hangul_text_to_ascii("1. 물음")
    assert q.startswith("#a4")


def test_middot_has_single_space_on_both_sides():
    """가운뎃점은 원문 공백과 무관하게 앞뒤 한 칸으로 점역한다."""
    left = hangul_text_to_ascii("국어")
    right = hangul_text_to_ascii("영어")
    expected = f"{left} 1; {right}"
    assert hangul_text_to_ascii("국어·영어") == expected
    assert hangul_text_to_ascii("국어 · 영어") == expected
    assert hangul_text_to_ascii("국어  ·  영어") == expected
    assert reverse_translate_line(expected) == "국어 · 영어"


def test_hangul_araea_and_legacy_placeholder_are_middot():
    """표 빈칸 ㆍ 와 옛 자리표시 =?(⠿⠹)는 가운뎃점으로 본다."""
    assert hangul_text_to_ascii("ㆍ") == "1;"
    assert hangul_text_to_ascii("가  ㆍ  나") == f"{hangul_text_to_ascii('가')} 1; {hangul_text_to_ascii('나')}"
    assert reverse_translate_line("=?") == "·"
    assert reverse_translate_line(" =? ") == " · "
    assert reverse_translate_line(hangul_text_to_ascii("ㆍ")) == "·"
    assert "옹" not in reverse_translate_line("=?")
    assert "억" not in reverse_translate_line("=?")


def test_bullet_operator_is_dot5_period_with_trailing_space():
    """항목 불릿 ∙ = ⠐⠲(\"4) + 뒤 공백. 역점역은 ∙ 로 복원."""
    body = hangul_text_to_ascii("독특한")
    assert hangul_text_to_ascii("∙독특한") == f'"4 {body}'
    assert hangul_text_to_ascii("∙ 독특한") == f'"4 {body}'
    assert hangul_text_to_ascii("∙") == '"4 '
    # 점역이 넣은 뒤 공백은 묵자에 남는다.
    assert reverse_translate_line(f'"4 {body}') == "∙ 독특한"
    assert reverse_translate_line('"4 ') == "∙ "


def test_figure_placeholder_fixed_braille_roundtrip():
    """[그림] ↔ ⠠⠄⠈⠪⠐⠕⠢⠀⠠⠗⠶⠐⠜⠁⠠⠄ (그림 생략) 고정 왕복."""
    from korean_exam_braille.app.brf.ascii_braille import ascii_to_unicode
    from korean_exam_braille.app.common.figure_markup import (
        FIGURE_BRAILLE_ASCII,
        FIGURE_INK,
    )

    assert hangul_text_to_ascii(FIGURE_INK) == FIGURE_BRAILLE_ASCII
    assert reverse_translate_line(FIGURE_BRAILLE_ASCII) == FIGURE_INK
    assert ascii_to_unicode(FIGURE_BRAILLE_ASCII) == "⠠⠄⠈⠪⠐⠕⠢⠀⠠⠗⠶⠐⠜⠁⠠⠄"
    # 본문 사이 행으로 끼어도 해당 행만 고정 치환
    body = hangul_text_to_ascii("본문")
    mixed = hangul_text_to_ascii(f"본문\n{FIGURE_INK}\n본문")
    assert mixed == f"{body}\n{FIGURE_BRAILLE_ASCII}\n{body}"


def test_roundtrip_smoke_simple_words():
    for src in ["가", "나", "다", "그리고", "하나"]:
        ascii_text = hangul_text_to_ascii(src)
        back = reverse_translate_line(ascii_text)
        assert src in back or back.replace(" ", "") == src.replace(" ", "")


def test_ssang_sios_avoids_ga_abbrev():
    """가류 약자 + ㅆ(`/`)은 ㅖ와 겹치므로 초성+ㅏ+ㅆ으로 점역한다."""
    cases = {
        "갔": "`</",
        "났": "c</",
        "닸": "i</",
        "맜": "e</",
        "밨": "^</",
        "샀": ",</",
        "잤": ".</",
        "캈": "f</",
        "탔": "h</",
        "팠": "d</",
        "핬": "j</",
    }
    for src, expected in cases.items():
        ascii_text = hangul_text_to_ascii(src)
        assert ascii_text == expected, (src, ascii_text, expected)
        assert reverse_translate_line(ascii_text) == src
    # 약자+/ 레거시는 ㅖ 쪽으로 읽히는 셀도 있음 — 폐 ≠ 팠
    assert hangul_text_to_ascii("폐") == "d/"
    assert reverse_translate_line("d/") == "폐"
    assert reverse_translate_line("d</") == "팠"
    assert hangul_text_to_ascii("땅을 팠다") == ",i<7! d</i"
    assert reverse_translate_line(",i<7! d</i") == "땅을 팠다"

def test_translator_fills_cells():
    tr = TableBrailleTranslator()
    seq = tr.translate_text("가나다")
    assert seq.tokens
    assert seq.tokens[0].cells
    assert seq.metadata.get("ascii")


def test_bracket_start_metadata_is_emitted_once_and_roundtrips():
    node = ExamNode(
        id="p1",
        node_type="Passage",
        source_range=SourceRange(raw_text="학생1 발언"),
        metadata={
            "bracket_labels": ["[A]"],
            "bracket_start_labels": ["[A]"],
            "bracket_end_labels": ["[A]"],
        },
    )
    seq = TableBrailleTranslator().translate_node(node)
    document = RuleBrailleLayoutEngine().layout([seq])
    rows = [
        line.ascii_text
        for page in document.pages
        for line in page.lines
        if line.ascii_text
    ]
    assert rows[0].startswith("63333 " + hangul_text_to_ascii("[A]") + " ")
    assert reverse_translate_line(rows[0]).startswith("┌──── [A]")
    assert any(reverse_translate_line(row).strip().startswith("학생1") for row in rows)
    assert rows[-1].startswith("h333333")
    assert reverse_translate_line(rows[-1]).startswith("└")


def test_circled_choice_to_marked_digit():
    ascii_text = hangul_text_to_ascii("① 선택")
    assert ascii_text.startswith("7#a7")
    assert reverse_translate_line(ascii_text).startswith("①")
    assert hangul_text_to_ascii("③").startswith("7#c7")
    assert reverse_translate_line("7#e7") == "⑤"


def test_circled_latin_a_to_e():
    """ⓐ–ⓩ → 7a7…7z7 (①의 7#a7 과 구분)."""
    assert hangul_text_to_ascii("ⓐ") == "7a7"
    assert hangul_text_to_ascii("ⓔ") == "7e7"
    assert hangul_text_to_ascii("ⓒ") == "7c7"
    assert hangul_text_to_ascii("ⓕ") == "7f7"
    assert hangul_text_to_ascii("ⓩ") == "7z7"
    assert reverse_translate_line("7a7") == "ⓐ"
    assert reverse_translate_line("7e7") == "ⓔ"
    assert reverse_translate_line("7f7") == "ⓕ"
    assert reverse_translate_line("7z7") == "ⓩ"
    src = "된 가상의 문장에서 ⓐ~ ⓔ를 분석해 볼까요?"
    assert "7a7" in hangul_text_to_ascii(src)
    assert "7e7" in hangul_text_to_ascii(src)
    back = reverse_translate_line(hangul_text_to_ascii(src))
    assert "ⓐ" in back and "ⓔ" in back
    assert hangul_text_to_ascii("ⓕ~ⓩ") == "7f7@97z7"
    assert reverse_translate_line("7f7@97z7") == "ⓕ~ⓩ"


def test_circled_hangul_and_underline_emphasis():
    """참고 BRF: ㉠<u>차자 표기</u> → 7=a7,-;<. d+`o-'"""
    assert hangul_text_to_ascii("㉠") == "7=a7"
    assert hangul_text_to_ascii("㉡") == "7=37"
    assert hangul_text_to_ascii("㉢") == "7=97"
    body = hangul_text_to_ascii("차자 표기")
    assert hangul_text_to_ascii("<u>차자 표기</u>") == ",-" + body + "-'"
    assert hangul_text_to_ascii("㉠<u>차자 표기</u>") == "7=a7,-;<. d+`o-'"


def test_circled_latin_labeled_underline_still_roundtrips():
    """인라인 ⓐ<u>…</u> 도 점역·역점역은 가능 (PDF 직렬화 기본은 2행)."""
    assert hangul_text_to_ascii("ⓐ<u>오</u>은") == "7a7,-u-'z"
    from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r

    assert r("7a7,-u-'z") == "ⓐ<u>오</u>은"
    assert "70a7" not in hangul_text_to_ascii("ⓐ<u>오</u>")


def test_hyangchal_two_line_braille():
    """향찰 기본 계약: 밑줄 행 + 원문자 행."""
    src = "[향찰 표기] <u>오</u>은\nⓐ ⓑ"
    brl = hangul_text_to_ascii(src)
    assert "\n" in brl
    assert "7a7" in brl and "7b7" in brl
    from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r

    # 행 단위 역점역
    back = "\n".join(r(line) for line in brl.split("\n"))
    assert "<u>오</u>" in back
    assert "ⓐ" in back and "ⓑ" in back


def test_box_rule_ink_to_table_rule():
    assert hangul_text_to_ascii("────────────────") == "!" + "3" * 20 + "4"
