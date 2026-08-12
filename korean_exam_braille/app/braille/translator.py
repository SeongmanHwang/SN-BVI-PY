"""표 기반 정방향 한국어 점역."""

from __future__ import annotations

import logging
import re

from korean_exam_braille.app.braille.body import (
    UNKNOWN_PRINT_ASCII,
    hangul_body_to_ascii_masked,
)
from korean_exam_braille.app.braille.models import BrailleSequence, BrailleToken
from korean_exam_braille.app.brf.ascii_braille import ascii_char_to_dots
from korean_exam_braille.app.exam.bracket_metadata import bracket_labels
from korean_exam_braille.app.common.korean_tables import (
    NUMBER_MAP,
    NUMBER_SIGN,
)
from korean_exam_braille.app.common.patterns import PASSAGE_RANGE
from korean_exam_braille.app.exam.models import ExamDocument, ExamNode
from korean_exam_braille.app.common.figure_markup import FIGURE_BRAILLE_ASCII, FIGURE_INK
from korean_exam_braille.app.common.plot_summary_markup import (
    PLOT_SUMMARY_END_BRAILLE_ASCII,
    PLOT_SUMMARY_END_INK,
)
from korean_exam_braille.app.common.hanja_reading import replace_hanja_with_reading
from korean_exam_braille.app.common.opaque_text import replace_opaque_with_slash
from korean_exam_braille.app.common.text_normalize import (
    ensure_newline_before_reference_mark,
)
from korean_exam_braille.app.exam.passage_indent_config import (
    DEFAULT_PASSAGE_INDENT_GENRE_CONFIG,
)

_DIGIT_TO_ASCII: dict[str, str] = {v: k for k, v in NUMBER_MAP.items()}
_LOG = logging.getLogger(__name__)

_EMPHASIS_OPEN = ",-"
_EMPHASIS_CLOSE = "-'"
_U_TAG = re.compile(r"<u>(.*?)</u>", re.DOTALL)
_RULE_LINE = re.compile(r"^[\s]*[─━\-_=]{5,}[\s]*$")
_TABLE_RULE_ASCII = "!" + ("3" * 20) + "4"
_LONG_MIDDOT_RUN = re.compile(r"·{4,}")
_QUESTION_START = re.compile(r"^(\d{1,2})\s*[\.．。]\s*")


def _ascii_to_cells(ascii_text: str) -> list[int]:
    cells: list[int] = []
    for ch in ascii_text:
        if ch == " ":
            cells.append(0)
        else:
            try:
                cells.append(ascii_char_to_dots(ch))
            except ValueError:
                cells.append(0)
    return cells


def _num_braille(n: int | str) -> str:
    s = str(n)
    return NUMBER_SIGN + "".join(_DIGIT_TO_ASCII[d] for d in s)


def _encode_passage_range(match: re.Match[str]) -> str:
    """[1~3] → 82#a`9#c;0 (참고 BRF 관례)."""
    a, b = int(match.group(1)), int(match.group(2))
    return f"82{_num_braille(a)}`9{_num_braille(b)};0"


def _collapse_long_middot_runs(text: str) -> str:
    """연속 ``·`` 4개 이상을 ``····`` 로 줄인다."""
    return _LONG_MIDDOT_RUN.sub("····", text)


def format_unknown_print_warning(chars: list[str]) -> str:
    uniq = list(dict.fromkeys(chars))
    shown = ", ".join(f"{c}(U+{ord(c):04X})" for c in uniq)
    return f"점역: 알 수 없는 문자 {shown} → 대체 셀 {UNKNOWN_PRINT_ASCII}"


def hangul_text_to_ascii(
    text: str,
    *,
    unknown_chars: list[str] | None = None,
) -> str:
    """묵자 문자열 → Braille ASCII (개행 보존).

    PUA 등 불투명 코드포인트는 빗금(/)으로 바꾼 뒤 점역한다.
    한자는 공식 실무대로 음독 한글로 바꾸고, 한글·한자 병기는 한자를 생략한다
    (한자 전환 표는 쓰지 않음).
    ``<u>…</u>`` 밑줄 구간은 강조부호 ``,-`` … ``-'`` 로 감싼다.
    ㉠–㉭ 은 드러냄+온표+초성(``7=@7`` …), ㉮–㉻ 은 드러냄+음절(``7$7`` …)로 점역한다.
    ⓐ–ⓩ 는 드러냄+라틴(``7a7`` …)으로 점역한다 (참고 BRF ``70a7``/‘a’ 아님).
    박스 표선 행(``────`` 등)은 ``!333…4`` 표선으로 점역한다.
    그림 자리표시 ``[그림]`` 은 고정 점역(그림 생략)으로 바꾼다.
    ``[줄거리 끝]`` 행도 고정 ASCII로 점역한다.
    """
    ascii_text, _mask = hangul_text_to_ascii_with_roman_mask(
        text, unknown_chars=unknown_chars
    )
    return ascii_text


def hangul_text_to_ascii_with_roman_mask(
    text: str,
    *,
    unknown_chars: list[str] | None = None,
) -> tuple[str, list[bool]]:
    """점역 ASCII와, 각 ASCII 문자가 로마자(라틴) 구간인지 마스크.

    마스크는 레이아웃 줄바꿈 시 «새 줄이 영어 구간으로 시작하는데
    로마자표가 빠졌는지» 판별에 쓴다. 개행 문자는 False.
    """
    text = replace_opaque_with_slash(text)
    text = replace_hanja_with_reading(text)
    text = _collapse_long_middot_runs(text)
    text = ensure_newline_before_reference_mark(text)
    collected = unknown_chars if unknown_chars is not None else []
    unknown_start = len(collected)
    ascii_parts: list[str] = []
    mask_parts: list[list[bool]] = []
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for i, line in enumerate(lines):
        if i:
            ascii_parts.append("\n")
            mask_parts.append([False])
        if line.strip() == FIGURE_INK:
            ascii_parts.append(FIGURE_BRAILLE_ASCII)
            mask_parts.append([False] * len(FIGURE_BRAILLE_ASCII))
        elif line.strip() == PLOT_SUMMARY_END_INK:
            ascii_parts.append(PLOT_SUMMARY_END_BRAILLE_ASCII)
            mask_parts.append([False] * len(PLOT_SUMMARY_END_BRAILLE_ASCII))
        elif _RULE_LINE.match(line):
            ascii_parts.append(_TABLE_RULE_ASCII)
            mask_parts.append([False] * len(_TABLE_RULE_ASCII))
        else:
            a, m = _encode_line_with_emphasis_masked(line, unknown=collected)
            ascii_parts.append(a)
            mask_parts.append(m)
    joined = "".join(ascii_parts)
    mask: list[bool] = []
    for part in mask_parts:
        mask.extend(part)
    assert len(mask) == len(joined)
    newly = collected[unknown_start:]
    if newly:
        _LOG.warning(format_unknown_print_warning(newly))
    return joined, mask


def _encode_line_with_emphasis(line: str) -> str:
    """밑줄 태그를 강조 점자로 바꾼 뒤 일반 점역."""
    ascii_text, _mask = _encode_line_with_emphasis_masked(line)
    return ascii_text


def _encode_line_with_emphasis_masked(
    line: str,
    *,
    unknown: list[str] | None = None,
) -> tuple[str, list[bool]]:
    """밑줄 태그를 강조 점자로 바꾼 뒤 일반 점역 + 로마 마스크."""
    ascii_parts: list[str] = []
    mask: list[bool] = []
    cursor = 0
    for m in _U_TAG.finditer(line):
        a, mk = _encode_line_masked(
            line[cursor : m.start()], unknown=unknown
        )
        ascii_parts.append(a)
        mask.extend(mk)
        ascii_parts.append(_EMPHASIS_OPEN)
        mask.extend([False] * len(_EMPHASIS_OPEN))
        a, mk = _encode_line_masked(m.group(1), unknown=unknown)
        ascii_parts.append(a)
        mask.extend(mk)
        ascii_parts.append(_EMPHASIS_CLOSE)
        mask.extend([False] * len(_EMPHASIS_CLOSE))
        cursor = m.end()
    a, mk = _encode_line_masked(line[cursor:], unknown=unknown)
    ascii_parts.append(a)
    mask.extend(mk)
    return "".join(ascii_parts), mask


def _encode_line(line: str) -> str:
    """지문 범위·문항 번호는 점자 ASCII로 직접 넣고, 나머지 묵자만 점역."""
    ascii_text, _mask = _encode_line_masked(line)
    return ascii_text


def _encode_line_masked(
    line: str,
    *,
    unknown: list[str] | None = None,
) -> tuple[str, list[bool]]:
    """지문 범위·문항 번호 + 본문 점역과 로마 마스크."""
    ascii_parts: list[str] = []
    mask: list[bool] = []
    cursor = 0

    m_q = _QUESTION_START.match(line)
    if m_q:
        piece = _num_braille(int(m_q.group(1))) + "4 "
        ascii_parts.append(piece)
        mask.extend([False] * len(piece))
        cursor = m_q.end()

    for m in PASSAGE_RANGE.finditer(line, cursor):
        a, mk = _hangul_body_to_ascii_masked(
            line[cursor : m.start()], unknown=unknown
        )
        ascii_parts.append(a)
        mask.extend(mk)
        piece = _encode_passage_range(m)
        ascii_parts.append(piece)
        mask.extend([False] * len(piece))
        cursor = m.end()

    a, mk = _hangul_body_to_ascii_masked(line[cursor:], unknown=unknown)
    ascii_parts.append(a)
    mask.extend(mk)
    return "".join(ascii_parts), mask


def _hangul_body_to_ascii(text: str) -> str:
    ascii_text, _mask = _hangul_body_to_ascii_masked(text)
    return ascii_text


def _hangul_body_to_ascii_masked(
    text: str,
    *,
    unknown: list[str] | None = None,
) -> tuple[str, list[bool]]:
    return hangul_body_to_ascii_masked(text, unknown=unknown)


class TableBrailleTranslator:
    """korean_tables 기반 정방향 점역."""

    def translate_text(self, text: str) -> BrailleSequence:
        unknown: list[str] = []
        ascii_text, roman_mask = hangul_text_to_ascii_with_roman_mask(
            text, unknown_chars=unknown
        )
        flat_ascii = ascii_text.replace("\r\n", "\n").replace("\r", "\n")
        if "\r" in ascii_text:
            # mask는 flat 과 길이가 같도록 유지 (위 replace가 길이를 바꾸지 않음)
            pass
        cell_list: list[int] = []
        for line in flat_ascii.split("\n"):
            cell_list.extend(_ascii_to_cells(line))
        tokens = [
            BrailleToken(
                source_text=text,
                token_type="text",
                cells=cell_list,
                rule_id="table.hangul",
                metadata={"ascii": flat_ascii, "roman_mask": roman_mask},
            )
        ]
        meta: dict = {
            "translator": "TableBrailleTranslator",
            "ascii": flat_ascii,
            "roman_mask": roman_mask,
        }
        if unknown:
            meta["unknown_chars"] = unknown
        return BrailleSequence(
            source_node_id="",
            tokens=tokens,
            metadata=meta,
        )

    def translate_node(self, node: ExamNode) -> BrailleSequence:
        text = node.source_range.raw_text or ""
        if node.node_type == "Header":
            return self._translate_header(node)
        if node.node_type == "Footer" and text.strip().isdigit():
            # 쪽 번호만 있는 푸터는 본문 흐름에서 생략 (면 꼬리말은 후속)
            return BrailleSequence(
                source_node_id=node.id,
                tokens=[],
                metadata={
                    "translator": "TableBrailleTranslator",
                    "ascii": "",
                    "node_type": node.node_type,
                    "skipped": True,
                },
            )
        # Passage/Choice/Question: PDF 행 개행을 문단 줄바꿈으로 쓰지 않음 —
        # 공백으로 이어 붙여 32셀이 찰 때까지 레이아웃이 soft wrap 하게 한다.
        # 예외: 시(indent_genre)는 시행 개행을 유지한다.
        # 예외: ※ 앞 줄바꿈은 참고 표지로 유지한다.
        genre = node.metadata.get("indent_genre")
        keep_hard_newlines = (
            node.node_type == "FlowchartAsset"
            or (
                node.node_type == "Passage"
                and genre == DEFAULT_PASSAGE_INDENT_GENRE_CONFIG.label_si
            )
        )
        text = ensure_newline_before_reference_mark(text)
        if node.node_type in {"Passage", "Choice", "Question"} and not keep_hard_newlines:
            text = text.replace("\n※", "\0※")
            text = re.sub(r"[\r\n]+", " ", text)
            text = re.sub(r" {2,}", " ", text)
            text = text.replace("\0※", "\n※")
        starts = bracket_labels(node.metadata, starts_only=True)
        ends = bracket_labels(node.metadata, ends_only=True)
        seq = self.translate_text(text)
        seq.source_node_id = node.id
        seq.metadata["node_type"] = node.node_type
        if isinstance(genre, str) and genre:
            seq.metadata["indent_genre"] = genre
        if keep_hard_newlines:
            seq.metadata["keep_hard_newlines"] = True
        if starts:
            seq.metadata["bracket_start_labels"] = starts
            seq.metadata["bracket_start_ascii"] = [
                hangul_text_to_ascii(label) for label in starts
            ]
        if ends:
            seq.metadata["bracket_end_labels"] = ends
        return seq

    def _translate_header(self, node: ExamNode) -> BrailleSequence:
        from korean_exam_braille.app.layout.header_format import (
            pad_header_ascii,
            split_header_ink_lines,
        )

        text = node.source_range.raw_text or ""
        parts = split_header_ink_lines(text)
        if not parts:
            return BrailleSequence(
                source_node_id=node.id,
                tokens=[],
                metadata={
                    "translator": "TableBrailleTranslator",
                    "ascii": "",
                    "node_type": "Header",
                    "skipped": True,
                },
            )
        ascii_lines: list[str] = []
        unknown: list[str] = []
        for align, ink in parts:
            raw = hangul_text_to_ascii(ink, unknown_chars=unknown)
            ascii_lines.append(pad_header_ascii(align, raw))
        flat = "\n".join(ascii_lines)
        cell_list: list[int] = []
        for line in flat.split("\n"):
            cell_list.extend(_ascii_to_cells(line))
        meta: dict = {
            "translator": "TableBrailleTranslator",
            "ascii": flat,
            "node_type": "Header",
            "preformatted": True,
        }
        if unknown:
            meta["unknown_chars"] = unknown
        return BrailleSequence(
            source_node_id=node.id,
            tokens=[
                BrailleToken(
                    source_text=text,
                    token_type="header",
                    cells=cell_list,
                    rule_id="table.header",
                    metadata={"ascii": flat},
                )
            ],
            metadata=meta,
        )

    def translate_document(self, exam: ExamDocument) -> list[BrailleSequence]:
        sequences: list[BrailleSequence] = []

        def walk(node: ExamNode) -> None:
            if node.node_type == "ExamDocument":
                for child in node.children:
                    walk(child)
                return
            if node.source_range.raw_text:
                seq = self.translate_node(node)
                if not seq.metadata.get("skipped"):
                    sequences.append(seq)
            for child in node.children:
                walk(child)

        walk(exam.root)
        return sequences
