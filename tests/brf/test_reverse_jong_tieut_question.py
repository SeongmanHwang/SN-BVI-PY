# -*- coding: utf-8 -*-
"""종성 ㅌ(8) ↔ 물음표(8) 구분 — ㅍ/마침표와 같은 어절 길이 규칙."""

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii as h
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r


def test_monosyllable_tieut_at_eol():
    """단독 ㅌ받침 어절(밭/끝/밑)은 문장 끝에서도 종성."""
    assert r(h("밭")) == "밭"
    assert r(h("끝")) == "끝"
    assert r(h("밑")) == "밑"
    assert r("^8") == "밭"
    assert r(",`[8") == "끝"
    assert r("eo8") == "밑"


def test_short_word_question_inserts_space():
    """두 음절 이하 어절 뒤 물음표 → 점역 시 앞에 공백 (가? ≠ 같)."""
    assert h("가?") == "$ 8"
    assert h("가?") != h("같")
    assert h("끝?") == ",`[8 8"
    assert " 8" in h("까요?")
    assert " 8" in h("것은?")
    assert r(h("가?")) == "가?"
    assert r(h("같")) == "같"
    assert r(h("끝?")) == "끝?"
    assert r("$ 8") == "가?"
    assert r(",`[8 8") == "끝?"


def test_long_word_question_no_space():
    """세 음절 이상 어절 뒤 물음표 → 공백 없음."""
    assert " 8" not in h("볼까요?")
    assert h("볼까요?").endswith("8")
    assert r(h("볼까요?")) == "볼까요?"


def test_question_at_sentence_end():
    """문장 끝 물음표 왕복. ≤2는 점역이 공백을 넣음."""
    assert r(h("까요?")) == "까요?"
    assert r(h("것은?")) == "것은?"
    assert r(h("볼까요?")) == "볼까요?"
    assert r(h("알맞은 것은?")) == "알맞은 것은?"
    assert r(",`<+ 8") == "까요?"
    assert r("_sz 8") == "것은?"
    # 약자 음절(은=z) 뒤 붙임 8 은 종성 후보가 아님 → 물음표 (구관례)
    assert r("_sz8") == "것은?"


def test_byeot_not_question_mark():
    """볕 = ㅂ+ㅕ+ㅌ (^:8). 햇벼?로 읽지 않음."""
    assert h("볕") == "^:8"
    assert r(h("볕")) == "볕"
    assert r("^:8") == "볕"
    assert h("햇볕") == "jr'^:8"
    assert r(h("햇볕")) == "햇볕"
    assert r("jr'^:8") == "햇볕"
    assert r(h("햇볕 볼 일 한 번도 없었을")) == "햇볕 볼 일 한 번도 없었을"


def test_tieut_before_underline_stays_jong():
    """밑줄 직전 단독 ㅌ받침 어절은 종성."""
    assert r(h("끝<u>말</u>")) == "끝<u>말</u>"
    assert r(h("<u>끝</u>")) == "<u>끝</u>"


def test_question_before_underline():
    """밑줄 표지 앞에서도 공백 구분된 물음표·약자 뒤 8은 ?."""
    assert r(h("것은?<u>다음</u>")) == "것은?<u>다음</u>"
    assert r("_sz 8,-i<[5-'") == "것은?<u>다음</u>"
    assert r("_sz8,-i<[5-'") == "것은?<u>다음</u>"


def test_midword_tieut_unchanged():
    """어절 중간 ㅌ은 기존처럼 종성."""
    assert r(h("같은것")) == "같은것"
    assert r(h("같다")) == "같다"
    assert r(h("끝에")) == "끝에"
    assert r(h("얕은")) == "얕은"
    assert r(h("밑줄?")) == "밑줄?"


def test_tieut_then_period_roundtrip():
    """짧은 ㅌ받침 어절 + 마침표 왕복."""
    assert r(h("끝.")) == "끝."
    assert "4" in h("끝.")
    assert r(h("밭.")) == "밭."
