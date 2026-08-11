# -*- coding: utf-8 -*-
"""※ 앞 줄바꿈 정규화."""

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii as h
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r
from korean_exam_braille.app.common.text_normalize import (
    ensure_newline_before_reference_mark,
)


def test_ensure_newline_before_reference_mark():
    assert (
        ensure_newline_before_reference_mark("이현, 백상루별곡 - ※ 수군")
        == "이현, 백상루별곡 -\n※ 수군"
    )
    assert ensure_newline_before_reference_mark("※ 이미 줄 시작") == "※ 이미 줄 시작"
    assert ensure_newline_before_reference_mark("가\n※ 나") == "가\n※ 나"


def test_translate_inserts_newline_before_reference_mark():
    ascii_text = h("이현, 백상루별곡 - ※ 수군")
    assert "\n99" in ascii_text
    back = "\n".join(r(line) for line in ascii_text.splitlines())
    assert "\n※" in back
    assert "별곡" in back and "수군" in back


def test_passage_flatten_keeps_newline_before_reference_mark():
    from korean_exam_braille.app.braille.translator import TableBrailleTranslator
    from korean_exam_braille.app.exam.models import ExamNode, SourceRange

    node = ExamNode(
        id="p1",
        node_type="Passage",
        source_range=SourceRange(
            page_number=1,
            raw_text="이현, 백상루별곡 - ※ 수군",
        ),
    )
    seq = TableBrailleTranslator().translate_node(node)
    ascii_text = seq.metadata.get("ascii") or ""
    assert "\n99" in ascii_text
