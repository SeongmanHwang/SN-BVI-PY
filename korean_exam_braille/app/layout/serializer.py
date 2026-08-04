"""BrailleDocument → BRF ASCII 직렬화."""

from __future__ import annotations

from korean_exam_braille.app.brf.ascii_braille import FORM_FEED, dots_to_ascii_char
from korean_exam_braille.app.layout.models import BrailleDocument, BrailleLine


def _line_to_ascii(line: BrailleLine) -> str:
    if line.ascii_text:
        return line.ascii_text
    return "".join(dots_to_ascii_char(c) if c else " " for c in line.cells)


class AsciiBrfSerializer:
    """셀/ASCII 줄을 면 단위 BRF 텍스트로 직렬화."""

    def serialize(self, document: BrailleDocument) -> str:
        page_texts: list[str] = []
        for page in document.pages:
            page_texts.append("\n".join(_line_to_ascii(ln) for ln in page.lines))
        return FORM_FEED.join(page_texts)
