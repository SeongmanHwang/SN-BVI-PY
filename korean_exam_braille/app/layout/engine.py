"""규칙 기반 점자 줄·면 편집."""

from __future__ import annotations

from korean_exam_braille.app.braille.models import BrailleSequence
from korean_exam_braille.app.brf.ascii_braille import ascii_char_to_dots
from korean_exam_braille.app.common.arrow_markup import ARROW_RIGHT_BRAILLE_ASCII
from korean_exam_braille.app.common.korean_tables import ROMAN_SIGN
from korean_exam_braille.app.layout.models import (
    BrailleDocument,
    BrailleLine,
    BraillePage,
    LayoutProfile,
)

_SEPARATOR = "=gggggggggggggggggggggggggggggg="  # 국내 BRF 관례 (32셀)
_NONBREAKING_ASCII = (ARROW_RIGHT_BRAILLE_ASCII,)


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


def _sequence_roman_mask(seq: BrailleSequence, ascii_text: str) -> list[bool] | None:
    raw = seq.metadata.get("roman_mask")
    if isinstance(raw, list) and len(raw) == len(ascii_text):
        return [bool(x) for x in raw]
    if seq.tokens:
        parts: list[bool] = []
        for token in seq.tokens:
            m = token.metadata.get("roman_mask")
            a = token.metadata.get("ascii")
            if isinstance(m, list) and isinstance(a, str) and len(m) == len(a):
                parts.extend(bool(x) for x in m)
            elif isinstance(a, str):
                parts.extend([False] * len(a))
            else:
                parts.extend([False] * len(token.source_text))
        if len(parts) == len(ascii_text):
            return parts
    return None


def _move_cut_before_nonbreaking(text: str, start: int, cut: int) -> int:
    """보호 점열 한가운데인 절단점을 점열 시작 앞으로 옮긴다."""
    for pattern in _NONBREAKING_ASCII:
        pos = text.find(pattern, start)
        while pos >= 0 and pos < cut:
            if pos < cut < pos + len(pattern):
                # 폭 자체가 점열보다 좁으면 한 줄 보존이 불가능하다.
                return pos if pos > start else cut
            pos = text.find(pattern, pos + 1)
    return cut


def _flatten_passage_newlines(
    text: str,
    roman_mask: list[bool] | None,
) -> tuple[str, list[bool] | None]:
    """Passage/Choice/Question soft wrap 전: 하드 개행을 공백으로 바꿔 한 흐름으로 만든다."""
    if not text or ("\n" not in text and "\r" not in text):
        return text, roman_mask
    out_chars: list[str] = []
    out_mask: list[bool] | None = [] if roman_mask is not None else None
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\r" and i + 1 < n and text[i + 1] == "\n":
            out_chars.append(" ")
            if out_mask is not None and roman_mask is not None:
                out_mask.append(False)
            i += 2
            continue
        if ch in "\r\n":
            out_chars.append(" ")
            if out_mask is not None and roman_mask is not None:
                out_mask.append(False)
            i += 1
            continue
        out_chars.append(ch)
        if out_mask is not None and roman_mask is not None:
            out_mask.append(roman_mask[i] if i < len(roman_mask) else False)
        i += 1
    flat = "".join(out_chars)
    # 연속 공백은 하나로 (마스크 False로 합침)
    collapsed: list[str] = []
    collapsed_mask: list[bool] | None = [] if out_mask is not None else None
    prev_space = False
    for j, ch in enumerate(flat):
        if ch == " ":
            if prev_space:
                continue
            prev_space = True
            collapsed.append(" ")
            if collapsed_mask is not None and out_mask is not None:
                collapsed_mask.append(False)
            continue
        prev_space = False
        collapsed.append(ch)
        if collapsed_mask is not None and out_mask is not None:
            collapsed_mask.append(out_mask[j])
    return "".join(collapsed), collapsed_mask


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
    roman_mask: list[bool] | None = None,
) -> list[str]:
    """ASCII 셀 단위 줄바꿈. 첫 줄만 first_indent, 이어서 cont_indent.

    ``roman_mask[i]`` 가 True 인 위치에서 새 줄이 시작되는데 로마자표(0)가
    없으면 앞에 ``0`` 을 넣는다. (영어 구간만 마스크됨 — 한글 된소리 제외)
    """
    if width < 1:
        width = 1
    first_indent = max(0, min(first_indent, width - 1))
    cont_indent = max(0, min(cont_indent, width - 1))
    if roman_mask is not None and len(roman_mask) != len(text):
        roman_mask = None

    lines: list[str] = []
    abs_pos = 0
    raw_lines = text.splitlines() or [""]
    for li, raw in enumerate(raw_lines):
        if li:
            abs_pos += 1  # newline
        if not raw:
            lines.append("")
            continue
        line_mask = (
            roman_mask[abs_pos : abs_pos + len(raw)] if roman_mask is not None else None
        )
        i = 0
        n = len(raw)
        line_no = 0
        while i < n:
            indent = first_indent if line_no == 0 else cont_indent
            pad = " " * indent
            usable = width - indent
            need_roman = bool(
                line_mask is not None
                and i < n
                and line_mask[i]
                and not raw[i:].startswith(ROMAN_SIGN)
            )
            if need_roman:
                usable = max(1, usable - len(ROMAN_SIGN))
            rest = n - i
            if rest <= usable:
                piece = raw[i:n]
                i = n
            else:
                cut = _move_cut_before_nonbreaking(raw, i, i + usable)
                chunk = raw[i:cut]
                sp = chunk.rfind(" ")
                if sp > 0:
                    piece = chunk[:sp]
                    i = i + sp + 1
                else:
                    piece = chunk
                    i = cut
            if need_roman:
                piece = ROMAN_SIGN + piece
            lines.append(pad + piece)
            line_no += 1
        abs_pos += len(raw)
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
            roman_mask = _sequence_roman_mask(seq, ascii_text)
            indent = _indent_for(node_type, prof)
            preformatted = bool(seq.metadata.get("preformatted"))
            # Passage/Choice/Question: translator가 개행을 공백으로 합치는
            # 것이 정석이지만, 시퀀스에 남은 \n 도 soft wrap 전에 한 흐름으로.
            if node_type in {"Passage", "Choice", "Question"} and not preformatted:
                ascii_text, roman_mask = _flatten_passage_newlines(
                    ascii_text, roman_mask
                )
            # 미리 패딩된 Header는 줄 단위로만 넣고 wrap하지 않음
            if preformatted:
                rows = ascii_text.split("\n") if ascii_text else [""]
            else:
                rows = _wrap_ascii(
                    ascii_text,
                    prof.cells_per_line,
                    first_indent=indent,
                    cont_indent=0,
                    roman_mask=roman_mask,
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
