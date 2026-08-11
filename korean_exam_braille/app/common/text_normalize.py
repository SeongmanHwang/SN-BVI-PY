"""점역·추출 공유 묵자 정규화."""

from __future__ import annotations

import re

# 같은 줄에 있는 ※ 앞에 줄바꿈 (이미 줄 시작이면 유지)
_NEWLINE_BEFORE_REF_MARK = re.compile(r"([^\n])[ \t]*※")


def ensure_newline_before_reference_mark(text: str) -> str:
    """``… - ※ 수군`` → ``… -\\n※ 수군``."""
    if not text or "※" not in text:
        return text
    return _NEWLINE_BEFORE_REF_MARK.sub(r"\1\n※", text)
