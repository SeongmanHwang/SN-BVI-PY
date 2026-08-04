"""시험지 머리말 묵자 → 참고 BRF식 줄 구조."""

from __future__ import annotations

import re

# (정렬, 묵자 한 줄) align: left | center
HeaderLine = tuple[str, str]

_TITLE = re.compile(
    r"^(?P<title>\d{4}\s*학년도\s+\d+\s*월\s+고\s*\d)\s+"
    r"(?P<sub>전국연합학력평가\s*문제지)"
    r"(?:\s+\d+)?\s*$"
)

_PERIOD = re.compile(r"^제(?P<num>\d+)교시\s+국어\s+영역\s*$")

_SEP_ONLY = re.compile(r"^[\s━─=_\-]+$")
_PAGE_ONLY = re.compile(r"^\d{1,3}$")


def _norm_spaces(text: str) -> str:
    t = text.replace("\n", " ").replace("\r", " ")
    t = re.sub(r"\s+", " ", t).strip()
    t = t.replace("교시국어", "교시 국어")
    t = t.replace("국어영역", "국어 영역")
    t = re.sub(r"고\s+(\d)", r"고\1", t)
    t = re.sub(r"제\s*(\d+)\s*교시", r"제\1교시", t)
    return t


def should_skip_header_text(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if _PAGE_ONLY.match(t):
        return True
    if _SEP_ONLY.match(t):
        return True
    if "학년도" not in t and "교시" not in t and "국어" in t and len(t) < 24:
        if re.search(r"\d\s*고\d", t) or t.startswith("국어"):
            return True
    return False


def split_header_ink_lines(text: str) -> list[HeaderLine]:
    """Header 묵자를 left/center 줄로 나눈다. 비면 출력 생략."""
    if should_skip_header_text(text):
        return []

    t = _norm_spaces(text)
    m = _TITLE.match(t)
    if m:
        title = re.sub(r"\s+", " ", m.group("title")).strip()
        title = re.sub(r"고\s+", "고", title)
        sub = re.sub(r"\s+", " ", m.group("sub")).strip()
        return [("left", title), ("left", sub)]

    m2 = _PERIOD.match(t)
    if m2:
        return [
            ("center", f"제{m2.group('num')}교시"),
            ("center", "국어 영역"),
        ]

    t = re.sub(r"\s+\d{1,3}\s*$", "", t).strip()
    if t and not should_skip_header_text(t):
        return [("left", t)]
    return []


def pad_header_ascii(align: str, ascii_text: str, *, width: int = 32) -> str:
    body = ascii_text.strip()
    if not body:
        return ""
    if len(body) >= width:
        return body[:width]
    if align == "center":
        lead = (width - len(body)) // 2
        return (" " * lead) + body
    return "  " + body
