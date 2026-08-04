"""표 기반 정방향 한국어 점역."""

from __future__ import annotations

import re

from korean_exam_braille.app.braille.models import BrailleSequence, BrailleToken
from korean_exam_braille.app.brf.ascii_braille import ascii_char_to_dots
from korean_exam_braille.app.brf.korean_tables import (
    ABBREV_CV,
    ABBREV_GEOT,
    ABBREV_VC,
    CHO_INDEX,
    CHOSEONG,
    JONG_INDEX,
    JONGSEONG,
    JONGSEONG_DIGRAPHS,
    JUNG_INDEX,
    JUNGSEONG,
    JUNGSEONG_DIGRAPHS,
    NUMBER_MAP,
    NUMBER_SIGN,
    ROMAN_SIGN,
    TENSED_MAP,
    TENSED_PREFIX,
    WORD_ABBREV,
)
from korean_exam_braille.app.exam.models import ExamDocument, ExamNode

# 묵자 → ASCII (표 반전). 국내 BRF는 초성 ㄱ을 ` 로 씀.
_CHO_TO_ASCII: dict[str, str] = {v: k for k, v in CHOSEONG.items()}
_CHO_TO_ASCII["ㄱ"] = "`"
for _cell, _jamo in TENSED_MAP.items():
    body = "`" if _cell == "@" else _cell
    _CHO_TO_ASCII[_jamo] = TENSED_PREFIX + body

_JUNG_TO_ASCII: dict[str, str] = {v: k for k, v in JUNGSEONG.items()}
for _cells, _jamo in JUNGSEONG_DIGRAPHS.items():
    _JUNG_TO_ASCII[_jamo] = _cells

_JONG_TO_ASCII: dict[str, str] = {v: k for k, v in JONGSEONG.items()}
for _cells, _jamo in JONGSEONG_DIGRAPHS.items():
    _JONG_TO_ASCII[_jamo] = _cells

_CV_ABBREV_BY_CHO: dict[str, str] = {}
for _cell, (_cho, _jung) in ABBREV_CV.items():
    if _jung != "ㅏ":
        continue
    if _cho not in _CV_ABBREV_BY_CHO or _cell in {"$", "l"}:
        if _cell == ",":
            continue
        _CV_ABBREV_BY_CHO[_cho] = _cell

_VC_ABBREV: dict[tuple[str, str], str] = {
    (jung, jong): cell for cell, (jung, jong) in ABBREV_VC.items()
}

_DIGIT_TO_ASCII: dict[str, str] = {v: k for k, v in NUMBER_MAP.items()}

_PUNCT_TO_ASCII: dict[str, str] = {
    ".": "4",
    "!": "6",
    "?": "8",
    ",": "1",
    ":": "3",
    "-": "-",
    "(": "8'",
    ")": ",0",
    "[": "82",
    "]": ";0",
    '"': "8",
    "'": "'",
    "‘": ",8",
    "’": "0'",
    "“": "8",
    "”": "0",
    "『": ";8",
    "』": "02",
    "「": '"8',
    "」": "01",
    "…": "444",
    "·": "1;",
    "～": "-",
    "~": "-",
    "/": "/",
    "=": "=",
    "*": "99",
    "※": "99",
    "ⓒ": "7c7",
    "〈": "7",
    "〉": "7",
    "<": "7",
    ">": "7",
}

_CIRCLED_DIGIT_CELL = {
    "①": "a",
    "②": "b",
    "③": "c",
    "④": "d",
    "⑤": "e",
}

_WORD_ABBREV_REV: list[tuple[str, str]] = sorted(
    ((hangul, cells) for cells, hangul in WORD_ABBREV.items()),
    key=lambda x: -len(x[0]),
)

_CHO_LIST = list(CHO_INDEX.keys())
_JUNG_LIST = list(JUNG_INDEX.keys())
_JONG_LIST = list(JONG_INDEX.keys())

_PASSAGE_RANGE = re.compile(r"\[\s*(\d{1,2})\s*[~\-–—]\s*(\d{1,2})\s*\]")
_QUESTION_START = re.compile(r"^(\d{1,2})\s*[\.．。]\s*")


def decompose_hangul(ch: str) -> tuple[str, str, str] | None:
    code = ord(ch) - 0xAC00
    if not 0 <= code < 11172:
        return None
    cho_i = code // (21 * 28)
    jung_i = (code % (21 * 28)) // 28
    jong_i = code % 28
    return _CHO_LIST[cho_i], _JUNG_LIST[jung_i], _JONG_LIST[jong_i]


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


def _encode_syllable(cho: str, jung: str, jong: str) -> str:
    if cho == "ㄱ" and jung == "ㅓ" and jong == "ㅅ":
        return ABBREV_GEOT

    if cho == "ㅇ" and (jung, jong) in _VC_ABBREV:
        return _VC_ABBREV[(jung, jong)]

    if cho != "ㅇ" and (jung, jong) in _VC_ABBREV:
        cho_ascii = _CHO_TO_ASCII.get(cho)
        if cho_ascii:
            return cho_ascii + _VC_ABBREV[(jung, jong)]

    if jung == "ㅏ" and cho in _CV_ABBREV_BY_CHO:
        base = _CV_ABBREV_BY_CHO[cho]
        if jong:
            jong_ascii = _JONG_TO_ASCII.get(jong)
            if jong_ascii:
                return base + jong_ascii
            return base
        return base

    parts: list[str] = []
    if cho != "ㅇ":
        cho_ascii = _CHO_TO_ASCII.get(cho)
        if cho_ascii is None:
            return "?"
        parts.append(cho_ascii)
    jung_ascii = _JUNG_TO_ASCII.get(jung)
    if jung_ascii is None:
        return "?"
    parts.append(jung_ascii)
    if jong:
        jong_ascii = _JONG_TO_ASCII.get(jong)
        if jong_ascii is None:
            return "?"
        parts.append(jong_ascii)
    return "".join(parts)


def _is_hangul(ch: str) -> bool:
    return decompose_hangul(ch) is not None


def hangul_text_to_ascii(text: str) -> str:
    """묵자 문자열 → Braille ASCII (개행 보존)."""
    chunks: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        chunks.append(_encode_line(line))
    return "\n".join(chunks)


def _encode_line(line: str) -> str:
    """지문 범위·문항 번호는 점자 ASCII로 직접 넣고, 나머지 묵자만 점역."""
    parts: list[str] = []
    cursor = 0

    m_q = _QUESTION_START.match(line)
    if m_q:
        parts.append(_num_braille(int(m_q.group(1))) + "4 ")
        cursor = m_q.end()

    for m in _PASSAGE_RANGE.finditer(line, cursor):
        parts.append(_hangul_body_to_ascii(line[cursor : m.start()]))
        parts.append(_encode_passage_range(m))
        cursor = m.end()

    parts.append(_hangul_body_to_ascii(line[cursor:]))
    return "".join(parts)


def _hangul_body_to_ascii(text: str) -> str:
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]

        if ch in " \t":
            out.append(" ")
            i += 1
            continue

        matched_word = False
        for hangul, cells in _WORD_ABBREV_REV:
            if text.startswith(hangul, i):
                out.append(cells)
                i += len(hangul)
                matched_word = True
                break
        if matched_word:
            continue

        if ch in _CIRCLED_DIGIT_CELL:
            # 원문자 번호: 7#a7 … (일반 수표 #a 와 구분)
            out.append("7#" + _CIRCLED_DIGIT_CELL[ch] + "7")
            i += 1
            continue

        if ch.isdigit():
            digits: list[str] = []
            while i < n and text[i].isdigit():
                digits.append(_DIGIT_TO_ASCII[text[i]])
                i += 1
            out.append(NUMBER_SIGN + "".join(digits))
            # 숫자 뒤 자음 초성 한글만 띄움. 제N교시은 예외(참고: .n#a`+,o)
            if i < n and _is_hangul(text[i]):
                decomp = decompose_hangul(text[i])
                if decomp and decomp[0] != "ㅇ" and not text.startswith(
                    "교시", i
                ):
                    out.append(" ")
            continue

        if ("A" <= ch <= "Z") or ("a" <= ch <= "z"):
            out.append(ROMAN_SIGN)
            while i < n:
                c = text[i]
                if ("A" <= c <= "Z") or ("a" <= c <= "z"):
                    out.append("," + c.lower() if "A" <= c <= "Z" else c)
                    i += 1
                    continue
                if c == " " and i + 1 < n and (
                    ("A" <= text[i + 1] <= "Z") or ("a" <= text[i + 1] <= "z")
                ):
                    out.append(" ")
                    i += 1
                    continue
                if c in "()" and c in _PUNCT_TO_ASCII:
                    out.append(_PUNCT_TO_ASCII[c])
                    i += 1
                    continue
                if c == "," and i + 1 < n and (
                    ("A" <= text[i + 1] <= "Z") or ("a" <= text[i + 1] <= "z")
                ):
                    out.append(_PUNCT_TO_ASCII[","])
                    i += 1
                    continue
                break
            continue

        decomp = decompose_hangul(ch)
        if decomp is not None:
            out.append(_encode_syllable(*decomp))
            i += 1
            continue

        if ch in _PUNCT_TO_ASCII:
            out.append(_PUNCT_TO_ASCII[ch])
            i += 1
            continue

        if 0x3131 <= ord(ch) <= 0x318E:
            out.append("?")
            i += 1
            continue

        i += 1

    return "".join(out)


class TableBrailleTranslator:
    """korean_tables 기반 정방향 점역."""

    def translate_text(self, text: str) -> BrailleSequence:
        ascii_text = hangul_text_to_ascii(text)
        flat_ascii = ascii_text.replace("\r\n", "\n").replace("\r", "\n")
        cell_list: list[int] = []
        for line in flat_ascii.split("\n"):
            cell_list.extend(_ascii_to_cells(line))
        tokens = [
            BrailleToken(
                source_text=text,
                token_type="text",
                cells=cell_list,
                rule_id="table.hangul",
                metadata={"ascii": flat_ascii},
            )
        ]
        return BrailleSequence(
            source_node_id="",
            tokens=tokens,
            metadata={"translator": "TableBrailleTranslator", "ascii": flat_ascii},
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
        seq = self.translate_text(text)
        seq.source_node_id = node.id
        seq.metadata["node_type"] = node.node_type
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
        for align, ink in parts:
            raw = hangul_text_to_ascii(ink)
            ascii_lines.append(pad_header_ascii(align, raw))
        flat = "\n".join(ascii_lines)
        cell_list: list[int] = []
        for line in flat.split("\n"):
            cell_list.extend(_ascii_to_cells(line))
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
            metadata={
                "translator": "TableBrailleTranslator",
                "ascii": flat,
                "node_type": "Header",
                "preformatted": True,
            },
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
