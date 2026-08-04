"""PDF 블록 텍스트에서 문항·선택지 등 구조 후보를 탐지한다."""

from __future__ import annotations

import re

_QUESTION = re.compile(
    r"(?:^|\n)\s*(?:"
    r"(\d{1,2})\s*[\.．。]"  # 16. / 16．
    r"|(\d{1,2})\s+"  # 16 발문
    r")"
)

_PASSAGE_RANGE = re.compile(r"\[\s*(\d{1,2})\s*[~\-–—]\s*(\d{1,2})\s*\]")

_CHOICE = re.compile(
    r"(?:^|\n)\s*(?:"
    r"[①②③④⑤]"
    r"|[1-5]\s*[\)］\]]"
    r"|[ㄱㄴㄷㄹㅁ]\s*[\.．]"
    r"|[1-5]\s*번\s*선택"  # fixture fallback
    r")"
)

_EXAMPLE = re.compile(r"〈\s*보\s*기\s*〉|<\s*보\s*기\s*>|【\s*보\s*기\s*】")
_FOOTNOTE = re.compile(r"(?:^|\n)\s*\*")
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

    if _PASSAGE_RANGE.search(text):
        tags.append("PassageGroup")

    m = _QUESTION.search(text)
    if m and "PassageGroup" not in tags:
        for g in m.groups():
            if g and g.isdigit() and 1 <= int(g) <= 45:
                tags.append("Question")
                break

    if _CHOICE.search(text):
        tags.append("Choice")

    if _EXAMPLE.search(text):
        tags.append("ExampleBox")

    if _FOOTNOTE.search(text):
        tags.append("Footnote")

    if _END.search(text):
        tags.append("EndNotice")

    return list(dict.fromkeys(tags))
