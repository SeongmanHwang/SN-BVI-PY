"""BRF 행에서 구조 후보(문제 번호·선택지·구분선 등)를 탐지한다."""

from __future__ import annotations

import re

# 숫자표 # 뒤 숫자 셀 (예: #a, #aj, #be)
_NUMBER_CELLS = re.compile(r"#([a-jA-J]{1,2})")

# 실제 시험지: ja,r7 #d"1  (문항 N)
_QUESTION_EXAM = re.compile(
    r"(?:^|\s)(?:ja,r7\s*)?#([a-jA-J]{1,2})\"1"
)

# 단순 행 시작 문항 후보
_QUESTION_ASCII = re.compile(r"^\s*(#[a-jA-J]{1,2})([-\.]|[ ]|$)")

# 선택지: 역점역 ①-⑤ / 1)~5)
_CHOICE_REVERSE = re.compile(r"(?:^|\s)([①②③④⑤]|[1-5]\)|[ㄱㄴㄷㄹㅁ]\.)")

# 시험지 선택지 관례: 숫자표+#a~#e 뒤에 따옴/본문
_CHOICE_EXAM = re.compile(r"(?:^|\s)#([a-eA-E])\"[0-9a-zA-Z]")

_CHOICE_ASCII_SIMPLE = re.compile(r"^\s*(#[a-eA-E])\s+")

# 긴 구분선: ==== 또는 =ggg…g=
_SEPARATOR = re.compile(
    r"^\s*(?:"
    r"([=\-\.\*_])\1{5,}"
    r"|=[gG7]{5,}="
    r"|[gG7]{8,}"
    r")\s*$"
)

_HEADER_FOOTER_HINTS = re.compile(r"(쪽|페이지|국어|문항|수능|모의|영역|교시)")


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


def _question_number_ok(cells: str) -> bool:
    digits = _digits_from_number_cells(cells)
    if not digits:
        return False
    value = int(digits)
    return 1 <= value <= 45


def detect_line_candidates(raw_ascii: str, reverse_text: str | None = None) -> list[str]:
    tags: list[str] = []
    stripped = raw_ascii.rstrip("\n\r")

    if stripped == "":
        return []

    if _SEPARATOR.match(stripped):
        tags.append("Separator")

    q_exam = _QUESTION_EXAM.search(stripped)
    if q_exam and _question_number_ok(q_exam.group(1)):
        tags.append("Question")

    q_match = _QUESTION_ASCII.match(stripped)
    if q_match and _question_number_ok(q_match.group(1)[1:]):
        if "Question" not in tags:
            tags.append("Question")
        rest = stripped[q_match.end() :].strip()
        if rest:
            tags.append("Prompt")

    if _CHOICE_EXAM.search(stripped) and "Question" not in tags:
        tags.append("Choice")

    c_match = _CHOICE_ASCII_SIMPLE.match(stripped)
    if c_match and "Question" not in tags and "Choice" not in tags:
        tags.append("Choice")

    if reverse_text:
        if _CHOICE_REVERSE.search(reverse_text) and "Choice" not in tags:
            tags.append("Choice")
        if _HEADER_FOOTER_HINTS.search(reverse_text):
            tags.append("Header")
        # 묵자 역점역에 "N번" 형태
        if re.search(r"(?:^|\s)\d{1,2}\s*번", reverse_text) and "Question" not in tags:
            tags.append("Question")

    return list(dict.fromkeys(tags))


def detect_document_candidates(lines: list[tuple[str, str | None]]) -> list[list[str]]:
    return [detect_line_candidates(raw, rev) for raw, rev in lines]
