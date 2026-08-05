"""생성 BRF ↔ 참고 BRF 검토 — 면 창 배정."""

from korean_exam_braille.app.session.review import (
    assign_reference_windows,
    brf_text_to_display_pages,
    build_review_pages,
    char_mismatch_masks,
    find_longest_anchors,
    flatten_reference_document,
    free_intervals,
)


def test_char_mismatch_masks_marks_only_diff_with_short_min():
    a_mask, b_mask = char_mismatch_masks("abc", "axc", min_match=1, max_anchors=5)
    assert a_mask == [False, True, False]
    assert b_mask == [False, True, False]


def test_find_longest_anchors_caps_at_five():
    parts_a = [f"{'A' * 20}{i}" for i in range(6)]
    parts_b = list(parts_a)
    parts_b[3] = "Z" * 21
    a = "|".join(parts_a)
    b = "|".join(parts_b)
    anchors = find_longest_anchors(a, b, min_match=10, max_anchors=5)
    assert len(anchors) <= 5
    assert all(span.size >= 10 for span in anchors)


def test_free_intervals_skips_claimed():
    claimed = [False, False, True, True, False]
    assert free_intervals(claimed) == [(0, 2), (4, 5)]


def test_assign_windows_no_overlap_and_reports_gaps():
    # 생성 2면, 참고는 사이에 끼어든 덩어리 + 공통 블록
    block_a = "A" * 24
    block_b = "B" * 24
    noise = "N" * 20
    gen = f"{block_a}\n\x0c\n{block_b}\n"
    ref = f"{block_a}\n{noise}\n{block_b}\n"
    gen_pages = brf_text_to_display_pages(gen)
    flat = flatten_reference_document(ref)
    assignments, unassigned = assign_reference_windows(
        gen_pages,
        str(flat["unicode"]),
        str(flat["ascii"]),
        min_match=8,
    )
    assert len(assignments) == 2
    assert assignments[0]["matched"] is True
    assert assignments[1]["matched"] is True
    # 창 겹침 없음
    s0, e0 = assignments[0]["ref_start"], assignments[0]["ref_end"]
    s1, e1 = assignments[1]["ref_start"], assignments[1]["ref_end"]
    assert e0 <= s1 or e1 <= s0
    # noise 구간이 누락으로 남음
    assert unassigned
    assert any(int(g["size"]) >= 8 for g in unassigned)


def test_char_mismatch_ignores_whitespace_and_newlines():
    a = "ab cd\nef"
    b = "abcdef"
    a_mask, b_mask = char_mismatch_masks(a, b, min_match=2, max_anchors=5)
    assert a_mask == [False] * len(a)
    assert b_mask == [False] * len(b)


def test_assign_matches_despite_newline_layout():
    block = "ABCDEFGHIJKLMNOPQRST"
    gen = block[:10] + "\n" + block[10:] + "\n"
    ref = block + "\n"
    gen_pages = brf_text_to_display_pages(gen)
    flat = flatten_reference_document(ref)
    assignments, _unassigned = assign_reference_windows(
        gen_pages,
        str(flat["unicode"]),
        str(flat["ascii"]),
        min_match=8,
    )
    assert len(assignments) == 1
    assert assignments[0]["matched"] is True
    assert assignments[0]["clipped"] is False


def test_build_review_pages_is_paged():
    generated = ("a" * 20) + "\n\x0c\n" + ("b" * 20) + "\n"
    reference = ("a" * 20) + "\nxxxx\n" + ("b" * 20) + "\n"
    built = build_review_pages(generated, reference, min_match=8, max_anchors=5)
    assert "review_pages" in built
    assert len(built["review_pages"]) == 2
    assert built["assignment_summary"]["matched_pages"] >= 1
    assert "unassigned_reference" in built
    page0 = built["review_pages"][0]
    assert "unicode_lines" in page0["generated"]
    assert "mismatch" in page0["generated"]["unicode_lines"][0]
