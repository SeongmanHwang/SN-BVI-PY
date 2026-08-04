# -*- coding: utf-8 -*-
"""안내문 허용 시험 내용 비교 테스트."""

from korean_exam_braille.app.brf.exam_diff import (
    compare_exam_content,
    document_to_line_views,
    segment_lines,
)
from korean_exam_braille.app.brf.parser import parse_brf_text


def _brf(pages: list[str]) -> str:
    return "\x0c".join(pages)


def test_guidance_in_reference_is_expected():
    gen = _brf(
        [
            "\n".join(
                [
                    "  82#a`9#c;0 i[5",
                    "passage body here",
                    "  #a4 question one",
                    "  #1 choice",
                ]
            )
        ]
    )
    # 참고본만 갖는 머리말(묵자 안내) — 시험 앵커 없음
    ref = _brf(
        [
            "\n".join(
                [
                    "  \uc548\ub0b4 \uc0ac\ud56d \uc810\uc790 \ubb38\uc81c",
                    "  \uc720\uc758 \uc0ac\ud56d \uc2dc\uac01 \uc7a5\uc560",
                    "  82#a`9#c;0 i[5",
                    "passage body here",
                    "  #a4 question one",
                    "  #1 choice",
                ]
            )
        ]
    )
    report = compare_exam_content(gen, ref)
    assert report.aligned_ok >= 1
    assert report.expected_diffs
    assert not report.content_mismatches


def test_content_mismatch_detected():
    gen = _brf(["  #a4 alpha question\n  #1 a"])
    ref = _brf(["  #a4 beta totally different\n  #1 a"])
    report = compare_exam_content(gen, ref, match_threshold=0.9)
    assert report.content_mismatches
    assert report.content_mismatches[0].key == "question:1"


def test_missing_question_in_generated():
    gen = _brf(["  #a4 only one\n"])
    ref = _brf(["  #a4 only one\n  #b4 second question\n"])
    report = compare_exam_content(gen, ref)
    keys = [d.key for d in report.missing_in_generated]
    assert "question:2" in keys


def test_segment_passage_and_question_keys():
    doc = parse_brf_text(
        "  82#a`9#c;0 next\nbody\n  #b4 q2 text\n"
    )
    segs = segment_lines(document_to_line_views(doc))
    keys = [s.key for s in segs]
    assert "passage:1-3" in keys
    assert "question:2" in keys
