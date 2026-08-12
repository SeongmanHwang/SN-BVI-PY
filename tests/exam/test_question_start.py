"""문항 번호 문맥 확정 — 범위·진행."""

from korean_exam_braille.app.common.patterns import question_number_from_text
from korean_exam_braille.app.exam.question_start import is_question_start


def test_question_number_from_text():
    assert question_number_from_text("28. ‘초고’의 글쓰기 방식") == 28
    assert question_number_from_text("1. 조사 방법: 설문 조사") == 1
    assert question_number_from_text("16．발문") == 16
    assert question_number_from_text("Ⅰ. 조사 동기 및 목적") is None
    assert question_number_from_text("① 선택지") is None


def test_range_keeps_exam_items_and_rejects_outline():
    rng = (28, 30)
    assert is_question_start("1. 조사 방법", question_range=rng) is None
    assert is_question_start("2. 조사 내용", question_range=rng) is None
    assert is_question_start("1. ○○로의 사고 현황", question_range=rng) is None
    assert is_question_start("2. 사고 원인 분석", question_range=rng) is None
    assert is_question_start("17. 다른 지문 문항", question_range=rng) is None
    assert is_question_start("31. 범위 밖", question_range=rng) is None
    assert is_question_start("28. ‘초고’의 글쓰기 방식", question_range=rng) == 28
    assert is_question_start("29. ㉠~㉢이", question_range=rng) == 29
    assert is_question_start("30. <보기>는", question_range=rng) == 30


def test_sequence_requires_increasing_numbers():
    rng = (28, 30)
    assert is_question_start("29. 다음", question_range=rng, last_question=28) == 29
    assert is_question_start("30. 다음", question_range=rng, last_question=29) == 30
    assert is_question_start("28. 중복", question_range=rng, last_question=28) is None
    assert is_question_start("28. 역행", question_range=rng, last_question=29) is None


def test_no_range_still_accepts_standalone_items():
    assert is_question_start("16. 발문입니다") == 16
    assert is_question_start("1. 물음") == 1
