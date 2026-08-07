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


def _bracket_start_rule(
    label_ascii: str,
    *,
    width: int,
    source_node_id: str,
) -> BrailleLine:
    """``⠖⠒⠒⠒⠒⠀[A]⠀⠒…⠲`` 형식의 구간 위 표선."""
    prefix = "6" + ("3" * 4) + " "
    suffix_width = max(1, width - len(prefix) - len(label_ascii) - 2)
    ascii_text = prefix + label_ascii + " " + ("3" * suffix_width) + "4"
    return BrailleLine(
        cells=_ascii_line_to_cells(ascii_text),
        source_node_ids=[source_node_id] if source_node_id else [],
        ascii_text=ascii_text,
    )


def _bracket_end_rule(*, width: int, source_node_id: str) -> BrailleLine:
    """``⠓⠒…⠚`` 형식의 구간 아래 표선."""
    ascii_text = "h" + ("3" * max(1, width - 2)) + "j"
    return BrailleLine(
        cells=_ascii_line_to_cells(ascii_text),
        source_node_ids=[source_node_id] if source_node_id else [],
        ascii_text=ascii_text,
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

            start_rules = seq.metadata.get("bracket_start_ascii") or []
            if isinstance(start_rules, list):
                for label_ascii in start_rules:
                    if isinstance(label_ascii, str) and label_ascii:
                        lines.append(
                            _bracket_start_rule(
                                label_ascii,
                                width=prof.cells_per_line,
                                source_node_id=seq.source_node_id,
                            )
                        )

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

            end_labels = seq.metadata.get("bracket_end_labels") or []
            if isinstance(end_labels, list):
                for label in end_labels:
                    if isinstance(label, str) and label:
                        lines.append(
                            _bracket_end_rule(
                                width=prof.cells_per_line,
                                source_node_id=seq.source_node_id,
                            )
                        )

            # PassageGroup 지시문 뒤 구분선
            if node_type == "PassageGroup":
                lines.append(_sep_line())

            prev_type = node_type

        # 면 분할: 첫 면은 이미 선행 빈 줄이 있다.
        # 이어지는 면에도 시작 빈 줄을 넣되, 예전의 [:usable] 절단처럼
        # 본문 줄을 버리지 않도록 빈 줄만큼 용량을 미리 뺀다.
        usable = max(1, prof.lines_per_page)
        pages: list[BraillePage] = []
        if not lines:
            pages.append(BraillePage(page_index=0, lines=[]))
        else:
            i = 0
            while i < len(lines):
                page_lines: list[BrailleLine] = []
                slots = usable
                cont = bool(pages)
                # 이어지는 면: 앞에 빈 줄 (이미 빈 줄로 시작하면 중복하지 않음)
                if cont and (lines[i].ascii_text or "") != "":
                    if usable > 1:
                        page_lines.append(_blank())
                        slots = usable - 1
                    # usable==1 이면 빈 줄 대신 본문만 넣어 유실을 막는다.
                page_lines.extend(lines[i : i + slots])
                i += slots
                pages.append(
                    BraillePage(page_index=len(pages), lines=page_lines)
                )

        return BrailleDocument(
            pages=pages,
            profile=prof,
            metadata={"layout": "RuleBrailleLayoutEngine"},
        )
