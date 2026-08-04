"""BRF 행에서 구조 후보(문제 번호·선택지·구분선 등)를 탐지한다."""

from __future__ import annotations

import re

# 숫자표 # 뒤 숫자 셀이 문제 번호처럼 보이는 패턴 (예: #a , #aj , #be )
_QUESTION_ASCII = re.compile(r"^\s*(#[a-jA-J]{1,2})([-\.]|[ ]|$)")

# 선택지: 역점역 결과의 ①-⑤ / 1)~5) / ㄱ.~마. 도 함께 본다.
_CHOICE_REVERSE = re.compile(r"(?:^|\s)([①②③④⑤]|[1-5]\)|[ㄱㄴㄷㄹㅁ]\.)")

_CHOICE_ASCII_SIMPLE = re.compile(r"^\s*(#[a-eA-E])\s+")

# 긴 구분선: 동일 문자 반복, 또는 =ggg…g= 형태
_SEPARATOR = re.compile(
    r"^\s*(?:"
    r"([=\-\.\*_])\1{5,}"
    r"|=[gG]{5,}="
    r"|[gG]{8,}"
    r")\s*$"
)

_HEADER_FOOTER_HINTS = re.compile(r"(쪽|페이지|국어|문항|수능|모의)")


def _digits_from_number_cells(cells: str) -> str | None:
    mapping = {
        "a": "1",
        "b": "2",
        "c": "3",
        "d": "4",
        "e": "5",
        "f": "6",
        "g": "7",
        "h": "8",
        "i": "9",
        "j": "0",
    }
    out: list[str] = []
    for ch in cells.lower():
        if ch not in mapping:
            return None
        out.append(mapping[ch])
    return "".join(out)


def detect_line_candidates(raw_ascii: str, reverse_text: str | None = None) -> list[str]:
    tags: list[str] = []
    stripped = raw_ascii.rstrip("\n\r")

    if stripped == "":
        return []

    if _SEPARATOR.match(stripped):
        tags.append("Separator")

    q_match = _QUESTION_ASCII.match(stripped)
    if q_match:
        digits = _digits_from_number_cells(q_match.group(1)[1:])
        if digits:
            value = int(digits)
            if 1 <= value <= 45:
                tags.append("Question")
                rest = stripped[q_match.end() :].strip()
                if rest:
                    tags.append("Prompt")

    c_match = _CHOICE_ASCII_SIMPLE.match(stripped)
    if c_match and "Question" not in tags:
        tags.append("Choice")

    if reverse_text:
        if _CHOICE_REVERSE.search(reverse_text) and "Choice" not in tags:
            tags.append("Choice")
        if _HEADER_FOOTER_HINTS.search(reverse_text):
            tags.append("Header")

    seen: set[str] = set()
    ordered: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            ordered.append(tag)
    return ordered


def detect_document_candidates(lines: list[tuple[str, str | None]]) -> list[list[str]]:
    return [detect_line_candidates(raw, rev) for raw, rev in lines]
