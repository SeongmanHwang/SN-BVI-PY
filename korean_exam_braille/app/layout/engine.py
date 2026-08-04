"""규칙 기반 점자 줄·면 편집."""

from __future__ import annotations

from korean_exam_braille.app.braille.models import BrailleSequence
from korean_exam_braille.app.brf.ascii_braille import ascii_char_to_dots
from korean_exam_braille.app.layout.models import (
    BrailleDocument,
    BrailleLine,
    BraillePage,
    LayoutProfile,
)

_SEPARATOR = "=gggggggggggggggggggggggggggggg="  # 국내 BRF 관례 (32셀)


def _sequence_ascii(seq: BrailleSequence) -> str:
    if "ascii" in seq.metadata:
        return str(seq.metadata["ascii"])
    parts: list[str] = []
    for token in seq.tokens:
        if "ascii" in token.metadata:
            parts.append(str(token.metadata["ascii"]))
        else:
            parts.append(token.source_text)
    return "".join(parts)


def _indent_for(node_type: str | None, profile: LayoutProfile) -> int:
    if node_type == "Choice":
        return profile.choice_indent
    if node_type in {"Paragraph", "Passage", "Prompt"}:
        return profile.paragraph_indent
    return 0


def _wrap_ascii(text: str, width: int, indent: int) -> list[str]:
    """ASCII 셀 단위 줄바꿈. 공백에서 우선 분리."""
    if width < 1:
        width = 1
    indent = max(0, min(indent, width - 1))
    pad = " " * indent
    usable = width - indent
    lines: list[str] = []
    for raw in text.splitlines() or [""]:
        if not raw:
            lines.append(pad if indent else "")
            continue
        remaining = raw
        first = True
        while remaining:
            limit = usable if first else usable
            prefix = pad
            if len(remaining) <= limit:
                lines.append(prefix + remaining)
                break
            chunk = remaining[:limit]
            # 공백 기준 뒤로 당김
            sp = chunk.rfind(" ")
            if sp > 0:
                piece = chunk[:sp]
                remaining = remaining[sp + 1 :]
            else:
                piece = chunk
                remaining = remaining[limit:]
            lines.append(prefix + piece)
            first = False
    return lines


def _ascii_line_to_cells(ascii_line: str) -> list[int]:
    cells: list[int] = []
    for ch in ascii_line:
        if ch == " ":
            cells.append(0)
        else:
            try:
                cells.append(ascii_char_to_dots(ch))
            except ValueError:
                cells.append(0)
    return cells


class RuleBrailleLayoutEngine:
    """토큰 ASCII를 들여쓰기·줄바꿈·면 분할한다."""

    def layout(
        self,
        sequences: list[BrailleSequence],
        *,
        profile: LayoutProfile | None = None,
    ) -> BrailleDocument:
        prof = profile or LayoutProfile()
        lines: list[BrailleLine] = []
        prev_type: str | None = None

        for seq in sequences:
            node_type = seq.metadata.get("node_type")
            if isinstance(node_type, str):
                pass
            else:
                node_type = None

            # PassageGroup / ExampleBox 전후 구분선
            if node_type in {"PassageGroup", "ExampleBox"} and lines:
                lines.append(
                    BrailleLine(
                        cells=_ascii_line_to_cells(_SEPARATOR),
                        source_node_ids=[],
                        ascii_text=_SEPARATOR,
                    )
                )
            elif (
                prev_type in {"Passage", "PassageGroup"}
                and node_type == "Question"
                and lines
            ):
                lines.append(BrailleLine(cells=[], source_node_ids=[], ascii_text=""))

            ascii_text = _sequence_ascii(seq)
            indent = _indent_for(node_type, prof)
            for row in _wrap_ascii(ascii_text, prof.cells_per_line, indent):
                # 줄 길이 제한
                if len(row) > prof.cells_per_line:
                    row = row[: prof.cells_per_line]
                lines.append(
                    BrailleLine(
                        cells=_ascii_line_to_cells(row),
                        source_node_ids=[seq.source_node_id]
                        if seq.source_node_id
                        else [],
                        ascii_text=row,
                    )
                )
            prev_type = node_type

        usable = max(1, prof.lines_per_page - prof.top_margin - prof.bottom_margin)
        pages: list[BraillePage] = []
        if not lines:
            pages.append(BraillePage(page_index=0, lines=[]))
        else:
            for i in range(0, len(lines), usable):
                chunk = lines[i : i + usable]
                pages.append(BraillePage(page_index=len(pages), lines=chunk))

        return BrailleDocument(
            pages=pages,
            profile=prof,
            metadata={"layout": "RuleBrailleLayoutEngine"},
        )
