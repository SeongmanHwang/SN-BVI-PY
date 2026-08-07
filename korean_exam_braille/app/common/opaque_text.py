"""불투명(비표준) 유니코드 정규화 — 빗금(/)으로 통일."""

from __future__ import annotations

import unicodedata

# 한국 점자 빗금 묵자. 점역 ASCII는 `_/` (⠸⠌) — 단독 `/`는 ㅖ·ㅆ과 충돌.
OPAQUE_REPLACEMENT = "/"


def is_opaque_char(ch: str) -> bool:
    """유니코드로 문자를 확정할 수 없는 코드포인트.

    - 치환 문자 U+FFFD
    - Private Use (Co) — 예: U+F000
    - 제어 문자(Cc) — 탭/개행/CR 제외
    - 미할당(Cn)·서로게이트(Cs)
    """
    if not ch:
        return False
    if ch in "\t\n\r":
        return False
    cp = ord(ch)
    if cp == 0xFFFD:
        return True
    cat = unicodedata.category(ch)
    return cat in {"Co", "Cc", "Cn", "Cs"}


def replace_opaque_with_slash(text: str) -> str:
    """불투명 코드포인트를 빗금(/)으로 바꾼다.

    추출·표시·점역 공통. 원문 복원이 불가한 PUA 등을
    점역 가능한 빗금으로 통일한다.
    """
    if not text:
        return text
    return "".join(OPAQUE_REPLACEMENT if is_opaque_char(ch) else ch for ch in text)
