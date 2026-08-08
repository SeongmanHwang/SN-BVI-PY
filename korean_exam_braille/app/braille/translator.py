"""표 기반 정방향 한국어 점역."""

from __future__ import annotations

import re

from korean_exam_braille.app.braille.models import BrailleSequence, BrailleToken
from korean_exam_braille.app.brf.ascii_braille import ascii_char_to_dots
from korean_exam_braille.app.exam.bracket_metadata import bracket_labels
from korean_exam_braille.app.common.korean_tables import (
    ABBREV_CV,
    ABBREV_GEOT,
    ABBREV_VC,
    CHO_INDEX,
    CHOSEONG,
    JAMO_COMPAT_TO_ASCII,
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
from korean_exam_braille.app.common.patterns import PASSAGE_RANGE
from korean_exam_braille.app.exam.models import ExamDocument, ExamNode
from korean_exam_braille.app.common.figure_markup import FIGURE_BRAILLE_ASCII, FIGURE_INK
from korean_exam_braille.app.common.hanja_reading import replace_hanja_with_reading
from korean_exam_braille.app.common.opaque_text import replace_opaque_with_slash

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

# 종성 ㅍ과 마침표는 같은 점자 셀(ASCII ``4``).
# 점역 규칙: 두 음절 이하 한글 어절 뒤 마침표 앞에 공백을 넣어 종성 ㅍ과 구분한다.
# 역점역 규칙: 공백 없이 짧은 어절(≤2음절) 뒤의 ``4`` → 종성 ㅍ,
#               긴 어절(≥3) 뒤이거나 공백 뒤의 ``4`` → 마침표.
_PERIOD_JONG_DISAMBIG_MAX_SYL = 2

_PUNCT_TO_ASCII: dict[str, str] = {
    ".": "4",
    "!": "6",
    "?": "8",
    # 한국 점자 쉼표 = 5점(⠐, ASCII ") — 초성 ㄹ과 동일 셀, 문맥으로 구분.
    # 종성 ㄹ(2점, ASCII 1)과 섞이면 '가,' → '갈'이 된다.
    ",": '"',
    # 쌍점 = 5점+2점(⠐⠂), ASCII "1. 종성 ㄴ(⠒/3)과 다르다.
    ":": '"1',
    "-": "-",
    "(": "8'",
    ")": ",0",
    "[": "82",
    "]": ";0",
    "{": "81",
    "}": '"0',
    '"': "88",
    "'": "'",
    "‘": ",8",
    "’": "0'",
    "“": "88",
    "”": "00",
    "『": ";8",
    "』": "02",
    "「": '"8',
    "」": "01",
    "《": ";88",
    "》": "002",
    "【": "82",
    "】": ";0",
    "〈": "78",
    "〉": "07",
    "<": "78",
    ">": "07",
    "…": "444",
    "·": "1;",
    "ㆍ": "1;",  # 한글 방점/표 빈칸 관례 → 가운뎃점과 동일
    "∙": '"4',  # 항목 불릿 ⠐⠲ — 점역 시 뒤에 공백 필수
    "～": "@9",
    "~": "@9",
    "―": "--",
    "—": "--",
    "–": "--",
    "/": "_/",  # 빗금 — 단독 `/`는 ㅖ·ㅆ과 충돌하므로 ⠸⠌
    "=": "=",
    "*": "99",
    "※": "99",
    "ⓒ": "7c7",
}

_CIRCLED_DIGIT_CELL = {
    "①": "a",
    "②": "b",
    "③": "c",
    "④": "d",
    "⑤": "e",
}

# ⓐ–ⓩ (원문자 라틴) → 드러냄+글자. ①용 7#a7·ⓒ 관례 7c7 과 동일 계열.
_CIRCLED_LATIN_CELL = {
    "ⓐ": "a",
    "ⓑ": "b",
    "ⓒ": "c",
    "ⓓ": "d",
    "ⓔ": "e",
    "ⓕ": "f",
    "ⓖ": "g",
    "ⓗ": "h",
    "ⓘ": "i",
    "ⓙ": "j",
    "ⓚ": "k",
    "ⓛ": "l",
    "ⓜ": "m",
    "ⓝ": "n",
    "ⓞ": "o",
    "ⓟ": "p",
    "ⓠ": "q",
    "ⓡ": "r",
    "ⓢ": "s",
    "ⓣ": "t",
    "ⓤ": "u",
    "ⓥ": "v",
    "ⓦ": "w",
    "ⓧ": "x",
    "ⓨ": "y",
    "ⓩ": "z",
}

# ㉠–㉭ (원문자 ㄱ–ㅎ) → 드러냄+온표자모. 참고 BRF: ㉠차자 → 7=a7,-…-'
_CIRCLED_HANGUL_JAMO: dict[str, str] = {
    "㉠": "ㄱ",
    "㉡": "ㄴ",
    "㉢": "ㄷ",
    "㉣": "ㄹ",
    "㉤": "ㅁ",
    "㉥": "ㅂ",
    "㉦": "ㅅ",
    "㉧": "ㅇ",
    "㉨": "ㅈ",
    "㉩": "ㅊ",
    "㉪": "ㅋ",
    "㉫": "ㅌ",
    "㉬": "ㅍ",
    "㉭": "ㅎ",
}

_EMPHASIS_OPEN = ",-"
_EMPHASIS_CLOSE = "-'"
_U_TAG = re.compile(r"<u>(.*?)</u>", re.DOTALL)
# 보기·표 박스 직렬화 표선 (묵자 ──── → 점자 표선; 역점역은 ─×16)
_RULE_LINE = re.compile(r"^[\s]*[─━\-_=]{5,}[\s]*$")
_TABLE_RULE_ASCII = "!" + ("3" * 20) + "4"

_WORD_ABBREV_REV: list[tuple[str, str]] = sorted(
    ((hangul, cells) for cells, hangul in WORD_ABBREV.items()),
    key=lambda x: -len(x[0]),
)

_CHO_LIST = list(CHO_INDEX.keys())
_JUNG_LIST = list(JUNG_INDEX.keys())
_JONG_LIST = list(JONG_INDEX.keys())

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
        # 종성 ㅆ(`/`)은 중성 ㅖ와 같은 셀이라 가류 약자+/ 가
        # 녜·뎨·폐…와 겹친다. 규정상 ㅏ를 생략하지 않고 초성+ㅏ+ㅆ로 적는다.
        # 예: 팠 → d</  (d/ 이면 폐), 갔 → `</  ($/ 도 가능하나 통일).
        if jong != "ㅆ":
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


def _trailing_hangul_syllables(text: str, end: int) -> int:
    """``text[:end]`` 끝에서 이어지는 한글 음절 수 (어절)."""
    n = 0
    j = end - 1
    while j >= 0 and decompose_hangul(text[j]) is not None:
        n += 1
        j -= 1
    return n


def hangul_text_to_ascii(text: str) -> str:
    """묵자 문자열 → Braille ASCII (개행 보존).

    PUA 등 불투명 코드포인트는 빗금(/)으로 바꾼 뒤 점역한다.
    한자는 공식 실무대로 음독 한글로 바꾸고, 한글·한자 병기는 한자를 생략한다
    (한자 전환 표는 쓰지 않음).
    ``<u>…</u>`` 밑줄 구간은 강조부호 ``,-`` … ``-'`` 로 감싼다.
    ㉠–㉭ 은 드러냄+자모(``7=a7`` …)로 점역한다.
    ⓐ–ⓩ 는 드러냄+라틴(``7a7`` …)으로 점역한다 (참고 BRF ``70a7``/‘a’ 아님).
    박스 표선 행(``────`` 등)은 ``!333…4`` 표선으로 점역한다.
    그림 자리표시 ``[그림]`` 은 고정 점역(그림 생략)으로 바꾼다.
    """
    text = replace_opaque_with_slash(text)
    text = replace_hanja_with_reading(text)
    chunks: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.strip() == FIGURE_INK:
            chunks.append(FIGURE_BRAILLE_ASCII)
        elif _RULE_LINE.match(line):
            chunks.append(_TABLE_RULE_ASCII)
        else:
            chunks.append(_encode_line_with_emphasis(line))
    return "\n".join(chunks)


def _encode_line_with_emphasis(line: str) -> str:
    """밑줄 태그를 강조 점자로 바꾼 뒤 일반 점역."""
    parts: list[str] = []
    cursor = 0
    for m in _U_TAG.finditer(line):
        parts.append(_encode_line(line[cursor : m.start()]))
        inner = m.group(1)
        parts.append(_EMPHASIS_OPEN + _encode_line(inner) + _EMPHASIS_CLOSE)
        cursor = m.end()
    parts.append(_encode_line(line[cursor:]))
    return "".join(parts)


def _encode_line(line: str) -> str:
    """지문 범위·문항 번호는 점자 ASCII로 직접 넣고, 나머지 묵자만 점역."""
    parts: list[str] = []
    cursor = 0

    m_q = _QUESTION_START.match(line)
    if m_q:
        parts.append(_num_braille(int(m_q.group(1))) + "4 ")
        cursor = m_q.end()

    for m in PASSAGE_RANGE.finditer(line, cursor):
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

        if ch in _CIRCLED_LATIN_CELL:
            # ⓐ–ⓔ: 드러냄+라틴 글자 (7a7 …). ①의 7#a7·로마자표 0a 와 구분.
            out.append("7" + _CIRCLED_LATIN_CELL[ch] + "7")
            i += 1
            continue

        if ch in _CIRCLED_HANGUL_JAMO:
            # ㉠–㉭: 드러냄+온표 자모 (참고 BRF 7=a7 …). ①용 7#a7 과 구분.
            jamo = _CIRCLED_HANGUL_JAMO[ch]
            body = JAMO_COMPAT_TO_ASCII.get(jamo)
            if body:
                out.append("7" + body + "7")
            i += 1
            continue

        if ch.isdigit():
            digit_start = i
            digits: list[str] = []
            while i < n and text[i].isdigit():
                digits.append(_DIGIT_TO_ASCII[text[i]])
                i += 1
            out.append(NUMBER_SIGN + "".join(digits))
            # 수표 구간 종료: 뒤에 글자가 이어지면 빈칸 하나.
            # 이미 공백·구두점이면 생략. [3점] 등 대괄호 안 점수 표기는
            # 참고 BRF(82#c.s5;0)처럼 숫자·단위를 붙인다.
            if i < n and text[i] not in " \t":
                nxt = text[i]
                after_open_bracket = digit_start > 0 and text[digit_start - 1] in "[【"
                attach_punct = nxt in _PUNCT_TO_ASCII
                if not (
                    attach_punct
                    or (after_open_bracket and _is_hangul(nxt))
                ):
                    out.append(" ")
            continue

        if ("A" <= ch <= "Z") or ("a" <= ch <= "z"):
            # 로마자(라틴)는 항상 로마자표(⠴/0)를 앞에 붙인다.
            # 한글 약자(은=z 등)와 셀이 겹쳐도 표지로 구분한다.
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
                    # 영문 구간 쉼표는 2점(ASCII 1). 한글 쉼표(")와 구분.
                    out.append("1")
                    i += 1
                    continue
                break
            continue

        decomp = decompose_hangul(ch)
        if decomp is not None:
            cho, jung, jong = decomp
            # 가류 약자 직후가 ㅇ-시작 음절(음, 였, 을…)이면 ㅏ를 명시해
            # 자음→즘, 하였 모호성을 줄인다: 자음=.<[5, 하였=j<:/
            next_de = decompose_hangul(text[i + 1]) if i + 1 < n else None
            if (
                jung == "ㅏ"
                and not jong
                and cho in _CV_ABBREV_BY_CHO
                and next_de is not None
                and next_de[0] == "ㅇ"
            ):
                cho_ascii = _CHO_TO_ASCII.get(cho)
                if cho_ascii is not None:
                    out.append(cho_ascii + "<")
                else:
                    out.append(_encode_syllable(cho, jung, jong))
            else:
                out.append(_encode_syllable(*decomp))
            i += 1
            continue

        if ch in _PUNCT_TO_ASCII:
            # 가운뎃점(·/ㆍ)은 묵자 원문의 공백 유무와 관계없이 양옆을 한 칸 띄운다.
            # 줄 처음·끝에서는 불필요한 선행·후행 공백을 만들지 않는다.
            if ch in {"·", "ㆍ"}:
                while out and out[-1] == " ":
                    out.pop()
                if out:
                    out.append(" ")
                out.append(_PUNCT_TO_ASCII[ch])
                i += 1
                while i < n and text[i] in " \t":
                    i += 1
                if i < n:
                    out.append(" ")
                continue
            # 항목 불릿(∙) = ⠐⠲("4). 뒤 공백을 항상 둔다.
            if ch == "∙":
                out.append(_PUNCT_TO_ASCII[ch])
                i += 1
                while i < n and text[i] in " \t":
                    i += 1
                out.append(" ")
                continue
            # 마침표(4) ↔ 종성 ㅍ(4): 두 음절 이하 어절 뒤면 앞에 공백.
            if ch == ".":
                syl = _trailing_hangul_syllables(text, i)
                if (
                    1 <= syl <= _PERIOD_JONG_DISAMBIG_MAX_SYL
                    and (not out or out[-1] != " ")
                ):
                    out.append(" ")
            out.append(_PUNCT_TO_ASCII[ch])
            i += 1
            continue

        # 호환 자모(ㄱ, ㅏ, ㅣ …) — 온표 + 자모 점형
        if ch in JAMO_COMPAT_TO_ASCII:
            out.append(JAMO_COMPAT_TO_ASCII[ch])
            i += 1
            continue

        if 0x3131 <= ord(ch) <= 0x318E:
            # 표에 없는 호환 자모는 온표만 남기지 않고 명시적으로 표시
            out.append("=?")
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
        starts = bracket_labels(node.metadata, starts_only=True)
        ends = bracket_labels(node.metadata, ends_only=True)
        seq = self.translate_text(text)
        seq.source_node_id = node.id
        seq.metadata["node_type"] = node.node_type
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
