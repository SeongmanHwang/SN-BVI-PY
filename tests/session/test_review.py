"""생성 BRF ↔ 참고 BRF 검토 마스크."""

from korean_exam_braille.app.session.review import (
    build_review_pages,
    char_mismatch_masks,
)


def test_char_mismatch_masks_marks_only_diff():
    a_mask, b_mask = char_mismatch_masks("abc", "axc")
    assert a_mask == [False, True, False]
    assert b_mask == [False, True, False]


def test_build_review_pages_highlights_mismatch():
    # ASCII BRF 한 면 (form-feed로 면 구분)
    generated = "a\nb\n\x0c"
    reference = "a\nc\n\x0c"
    built = build_review_pages(generated, reference)
    pages = built["review_pages"]
    assert len(pages) == 1
    gen_uni = pages[0]["generated"]["unicode_lines"]
    ref_uni = pages[0]["reference"]["unicode_lines"]
    assert len(gen_uni) == 2
    assert gen_uni[0]["line_equal"] is True
    assert gen_uni[1]["line_equal"] is False
    assert any(gen_uni[1]["mismatch"])
    assert any(ref_uni[1]["mismatch"])
    assert built["compare"]["matched_lines"] >= 1
