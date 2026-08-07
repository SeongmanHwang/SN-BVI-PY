"""머리말 줄 분리·패딩 테스트."""

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii
from korean_exam_braille.app.layout.header_format import (
    pad_header_ascii,
    should_skip_header_text,
    split_header_ink_lines,
)


def test_split_title_and_strip_page_number():
    lines = split_header_ink_lines(
        "2026학년도 6월 고2 전국연합학력평가 문제지 1"
    )
    assert lines == [
        ("left", "2026학년도 6월 고2"),
        ("left", "전국연합학력평가 문제지"),
    ]


def test_split_period_subject_center():
    lines = split_header_ink_lines("제1 교시국어영역")
    assert lines == [
        ("center", "제1교시"),
        ("center", "국어 영역"),
    ]


def test_skip_page_and_separator():
    assert should_skip_header_text("116")
    assert should_skip_header_text("━" * 20)


def test_pad_matches_reference_widths():
    title = hangul_text_to_ascii("2026학년도 6월 고2")
    assert pad_header_ascii("left", title) == "  " + title.strip()
    period = hangul_text_to_ascii("제1교시")
    centered = pad_header_ascii("center", period)
    lead = (32 - len(period.strip())) // 2
    assert centered == (" " * lead) + period.strip()
    assert centered.strip() == period.strip()
