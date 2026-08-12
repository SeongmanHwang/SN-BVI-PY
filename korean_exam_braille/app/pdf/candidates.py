"""PDF 블록 텍스트에서 문항·선택지 등 구조 후보를 탐지한다."""

from __future__ import annotations

import re

from korean_exam_braille.app.common.patterns import (
    PASSAGE_RANGE,
    question_number_from_text,
)

_CHOICE = re.compile(
    r"(?:^|\n)\s*(?:"
    r"[①②③④⑤]"
    r"|[1-5]\s*[\)］\]]"
    r"|[ㄱㄴㄷㄹㅁ]\s*[\.．]"
    r"|[1-5]\s*번\s*선택"  # fixture fallback
    r")"
)

_EXAMPLE = re.compile(
    r"〈\s*보\s*기\s*\d*\s*〉|<\s*보\s*기\s*\d*\s*>|【\s*보\s*기\s*\d*\s*】"
)
_END = re.compile(r"시험이\s*끝났|문제지.*거두|수고하셨")


def detect_block_candidates(
    text: str,
    *,
    band: str | None = None,
) -> list[str]:
    tags: list[str] = []
    if not text or not text.strip():
        return tags

    if band == "header":
        tags.append("Header")
        return tags
    if band == "footer":
        tags.append("Footer")
        return tags

    if PASSAGE_RANGE.search(text):
        tags.append("PassageGroup")

    # 순서도 선형 묵자. 본문 `1.` 문항 후보보다 먼저 본다.
    if text.lstrip().startswith("[그림: 순서도]"):
        tags.append("FlowchartAsset")

    # 번호 모양은 Question *후보*일 뿐. 확정은 Exam 빌더가
    # PassageGroup [start~end] 범위·번호 진행으로 한다.
    if (
        "PassageGroup" not in tags
        and "FlowchartAsset" not in tags
        and question_number_from_text(text) is not None
    ):
        tags.append("Question")

    if _CHOICE.search(text):
        tags.append("Choice")

    if _EXAMPLE.search(text):
        tags.append("ExampleBox")

    # Footnote 미사용: `*` 줄은 본문(Passage 등)으로 부착
    if _END.search(text):
        tags.append("EndNotice")

    return list(dict.fromkeys(tags))
