"""추출 텍스트 표시용 — common 정규화 재노출."""

from __future__ import annotations

from korean_exam_braille.app.common.opaque_text import (
    OPAQUE_REPLACEMENT,
    is_opaque_char,
    replace_opaque_with_slash,
)

__all__ = [
    "OPAQUE_REPLACEMENT",
    "annotate_opaque_codepoints",
    "is_opaque_char",
    "replace_opaque_with_slash",
]


def annotate_opaque_codepoints(text: str) -> str:
    """호환용: 불투명 문자를 빗금으로 바꾼다."""
    return replace_opaque_with_slash(text)
