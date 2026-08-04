"""표 기반 정방향 한국어 점역."""

from __future__ import annotations

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

# 묵자 → ASCII (표 반전)
_CHO_TO_ASCII: dict[str, str] = {v: k for k, v in CHOSEONG.items()}
# 된소리: ㄲ 등은 TENSED
for _cell, _jamo in TENSED_MAP.items():
    _CHO_TO_ASCII[_jamo] = TENSED_PREFIX + _cell

_JUNG_TO_ASCII: dict[str, str] = {v: k for k, v in JUNGSEONG.items()}
for _cells, _jamo in JUNGSEONG_DIGRAPHS.items():
    _JUNG_TO_ASCII[_jamo] = _cells

_JONG_TO_ASCII: dict[str, str] = {v: k for k, v in JONGSEONG.items()}
for _cells, _jamo in JONGSEONG_DIGRAPHS.items():
    _JONG_TO_ASCII[_jamo] = _cells

# 가류 약자: (초성, 중성=ㅏ) → 셀. 전용 셀 우선 ($=가, l=사)
_CV_ABBREV_BY_CHO: dict[str, str] = {}
for _cell, (_cho, _jung) in ABBREV_CV.items():
    if _jung != "ㅏ":
        continue
    # 전용 셀 우선
    if _cho not in _CV_ABBREV_BY_CHO or _cell in {"$", "l"}:
        if _cell == ",":
            continue  # 사·초성 ㅅ과 충돌 — l 사용
        _CV_ABBREV_BY_CHO[_cho] = _cell

_VC_ABBREV: dict[tuple[str, str], str] = {
    (jung, jong): cell for cell, (jung, jong) in ABBREV_VC.items()
}

_DIGIT_TO_ASCII: dict[str, str] = {v: k for k, v in NUMBER_MAP.items()}

_PUNCT_TO_ASCII: dict[str, str] = {
    ".": "4",
    "!": "6",
    "?": "8",
    ",": "1",  # ⠂ 간이
    ":": "3",
    ";": "23",  # fallback multi — handled specially if needed
    "-": "-",
    "(": "7",
    ")": "7",
    '"': "8",
    "'": "'",
    "…": "444",
    "·": "1",
    "～": "-",
    "~": "-",
    "/": "/",
    "=": "=",
}

# 원문자 선택지 → 숫자 점역
_CIRCLED = {
    "①": "1",
    "②": "2",
    "③": "3",
    "④": "4",
    "⑤": "5",
}

_WORD_ABBREV_REV: list[tuple[str, str]] = sorted(
    ((hangul, cells) for cells, hangul in WORD_ABBREV.items()),
    key=lambda x: -len(x[0]),
)

_CHO_LIST = list(CHO_INDEX.keys())
_JUNG_LIST = list(JUNG_INDEX.keys())
_JONG_LIST = list(JONG_INDEX.keys())


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
                # 미지원 문자는 공백 셀
                cells.append(0)
    return cells


def _encode_syllable(cho: str, jung: str, jong: str) -> str:
    # 것
    if cho == "ㄱ" and jung == "ㅓ" and jong == "ㅅ":
        return ABBREV_GEOT

    # ㅇ + VC 약자
    if cho == "ㅇ" and (jung, jong) in _VC_ABBREV:
        return _VC_ABBREV[(jung, jong)]

    # 가류 약자 (ㅏ + 임의 종성)
    if jung == "ㅏ" and cho in _CV_ABBREV_BY_CHO:
        base = _CV_ABBREV_BY_CHO[cho]
        if jong:
            jong_ascii = _JONG_TO_ASCII.get(jong)
            if jong_ascii:
                return base + jong_ascii
            return base
        return base

    # 일반: 초성(ㅇ 생략) + 중성 + 종성
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


def hangul_text_to_ascii(text: str) -> str:
    """묵자 문자열 → Braille ASCII (개행 보존)."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in "\n\r":
            out.append(ch)
            i += 1
            continue
        if ch == " ":
            out.append(" ")
            i += 1
            continue
        if ch == "\t":
            out.append(" ")
            i += 1
            continue

        # 단어 약어
        matched = False
        for hangul, cells in _WORD_ABBREV_REV:
            if text.startswith(hangul, i):
                out.append(cells)
                i += len(hangul)
                matched = True
                break
        if matched:
            continue

        if ch in _CIRCLED:
            digit = _CIRCLED[ch]
            out.append(NUMBER_SIGN + _DIGIT_TO_ASCII[digit])
            i += 1
            continue

        if ch.isdigit():
            digits: list[str] = []
            while i < n and text[i].isdigit():
                digits.append(_DIGIT_TO_ASCII[text[i]])
                i += 1
            out.append(NUMBER_SIGN + "".join(digits))
            continue

        if "A" <= ch <= "Z" or "a" <= ch <= "z":
            out.append(ROMAN_SIGN)
            while i < n and (("A" <= text[i] <= "Z") or ("a" <= text[i] <= "z")):
                c = text[i]
                if "A" <= c <= "Z":
                    out.append("," + c.lower())
                else:
                    out.append(c)
                i += 1
            continue

        decomp = decompose_hangul(ch)
        if decomp is not None:
            out.append(_encode_syllable(*decomp))
            i += 1
            continue

        if ch in _PUNCT_TO_ASCII:
            punct = _PUNCT_TO_ASCII[ch]
            # multi-char punct ascii
            out.append(punct)
            i += 1
            continue

        # 한글 자모·기타: 건너뛰거나 ?
        if 0x3131 <= ord(ch) <= 0x318E:
            out.append("?")
            i += 1
            continue

        # 미지원 문자 — 공백으로 대체하지 않고 생략 표시
        out.append(" ")
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
        seq = self.translate_text(text)
        seq.source_node_id = node.id
        seq.metadata["node_type"] = node.node_type
        return seq

    def translate_document(self, exam: ExamDocument) -> list[BrailleSequence]:
        sequences: list[BrailleSequence] = []

        def walk(node: ExamNode) -> None:
            if node.node_type == "ExamDocument":
                for child in node.children:
                    walk(child)
                return
            if node.source_range.raw_text:
                sequences.append(self.translate_node(node))
            for child in node.children:
                walk(child)

        walk(exam.root)
        return sequences
