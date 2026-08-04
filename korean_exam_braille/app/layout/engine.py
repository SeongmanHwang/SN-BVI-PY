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
    # Header는 translator가 이미 들여쓰기·가운데 패딩함
    if node_type == "Header":
        return 0
    if node_type in {"Choice", "Question", "PassageGroup"}:
        return profile.choice_indent
    if node_type in {"Paragraph", "Passage", "Prompt", "ExampleBox"}:
        return profile.paragraph_indent
    return 0


def _wrap_ascii(
    text: str,
    width: int,
    *,
    first_indent: int,
    cont_indent: int = 0,
) -> list[str]:
    """ASCII 셀 단위 줄바꿈. 첫 줄만 first_indent, 이어서 cont_indent."""
    if width < 1:
        width = 1
    first_indent = max(0, min(first_indent, width - 1))
    cont_indent = max(0, min(cont_indent, width - 1))
    lines: list[str] = []
    for raw in text.splitlines() or [""]:
        if not raw:
            lines.append("")
            continue
        remaining = raw
        line_no = 0
        while remaining:
            indent = first_indent if line_no == 0 else cont_indent
            pad = " " * indent
            usable = width - indent
            if len(remaining) <= usable:
                lines.append(pad + remaining)
                break
            chunk = remaining[:usable]
            sp = chunk.rfind(" ")
            if sp > 0:
                piece = chunk[:sp]
                remaining = remaining[sp + 1 :]
            else:
                piece = chunk
                remaining = remaining[usable:]
            lines.append(pad + piece)
            line_no += 1
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


def _blank() -> BrailleLine:
    return BrailleLine(cells=[], source_node_ids=[], ascii_text="")


def _sep_line() -> BrailleLine:
    return BrailleLine(
        cells=_ascii_line_to_cells(_SEPARATOR),
        source_node_ids=[],
        ascii_text=_SEPARATOR,
    )


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

        # 참고 BRF: 면 시작 빈 줄
        lines.append(_blank())

        for seq in sequences:
            node_type = seq.metadata.get("node_type")
            if not isinstance(node_type, str):
                node_type = None

            # Header → Header / PassageGroup 사이 빈 줄
            if prev_type == "Header" and node_type in {"Header", "PassageGroup"}:
                lines.append(_blank())
            # 지문 뒤 문항 앞 빈 줄
            elif prev_type in {"Passage", "ExampleBox"} and node_type == "Question":
                lines.append(_blank())
            # ExampleBox 앞 구분선
            elif node_type == "ExampleBox" and lines:
                lines.append(_sep_line())

            ascii_text = _sequence_ascii(seq)
            indent = _indent_for(node_type, prof)
            preformatted = bool(seq.metadata.get("preformatted"))
            # 미리 패딩된 Header는 줄 단위로만 넣고 wrap하지 않음
            if preformatted:
                rows = ascii_text.split("\n") if ascii_text else [""]
            else:
                rows = _wrap_ascii(
                    ascii_text,
                    prof.cells_per_line,
                    first_indent=indent,
                    cont_indent=0,
                )
            for row in rows:
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

            # PassageGroup 지시문 뒤 구분선
            if node_type == "PassageGroup":
                lines.append(_sep_line())

            prev_type = node_type

        # 면 분할: top/bottom margin 빈 줄은 이미 문서 시작에 반영. usable 전체 높이.
        usable = max(1, prof.lines_per_page)
        pages: list[BraillePage] = []
        if not lines:
            pages.append(BraillePage(page_index=0, lines=[]))
        else:
            for i in range(0, len(lines), usable):
                chunk = lines[i : i + usable]
                # 이어지는 면 시작에도 빈 줄 하나 (첫 면은 이미 있음)
                if i > 0 and (not chunk or chunk[0].ascii_text != ""):
                    chunk = [_blank(), *chunk][:usable]
                pages.append(BraillePage(page_index=len(pages), lines=chunk))

        return BrailleDocument(
            pages=pages,
            profile=prof,
            metadata={"layout": "RuleBrailleLayoutEngine"},
        )
