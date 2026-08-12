"""본문 토큰 분류 — 점역 전에 종류만 나눈다."""

from korean_exam_braille.app.braille.body import (
    KIND_ARROW,
    KIND_CIRCLED_DIGIT,
    KIND_DIGIT,
    KIND_HANGUL,
    KIND_MATH,
    KIND_PUNCT,
    KIND_ROMAN,
    KIND_SPACE,
    tokenize_body,
)


def test_tokenize_mixed_exam_prompt():
    kinds = [t.kind for t in tokenize_body("3개의 FOB → ①을 고르시오.")]
    assert kinds == [
        KIND_DIGIT,
        KIND_HANGUL,
        KIND_HANGUL,
        KIND_SPACE,
        KIND_ROMAN,
        KIND_SPACE,
        KIND_ARROW,
        KIND_SPACE,
        KIND_CIRCLED_DIGIT,
        KIND_HANGUL,
        KIND_SPACE,
        KIND_HANGUL,
        KIND_HANGUL,
        KIND_HANGUL,
        KIND_HANGUL,
        KIND_PUNCT,
    ]


def test_tokenize_does_not_encode():
    tokens = tokenize_body("12가")
    assert tokens[0].text == "12"
    assert tokens[1].text == "가"
    assert all("#" not in t.text for t in tokens)


def test_hyphen_kind_depends_on_neighbors():
    assert tokenize_body("3-5")[1].kind == KIND_MATH
    assert tokenize_body("-보기-")[0].kind == KIND_PUNCT
