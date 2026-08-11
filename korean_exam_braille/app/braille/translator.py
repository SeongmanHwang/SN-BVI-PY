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
    MATH_OP_TO_ASCII,
    NUMBER_MAP,
    NUMBER_SIGN,
    ROMAN_END_SIGN,
    ROMAN_SIGN,
    HIDE_MARK_CLOSE,
    HIDE_MARK_OPEN,
    HIDE_MARK_UNIT,
    HIDE_SQUARE_UNIT,
    HIDE_TRIANGLE_UNIT,
    HIDE_X_UNIT,
    TENSED_MAP,
    TENSED_PREFIX,
    WORD_ABBREV,
)
from korean_exam_braille.app.common.patterns import PASSAGE_RANGE
from korean_exam_braille.app.exam.models import ExamDocument, ExamNode
from korean_exam_braille.app.common.arrow_markup import (
    ARROW_RIGHT_BRAILLE_ASCII,
    ARROW_RIGHT_INK,
)
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

# 종성 ㅍ/ㅌ 과 마침표/물음표는 같은 점자 셀(ASCII ``4`` / ``8``).
# 점역: 두 음절 이하 한글 어절 뒤 ``.``·``?`` 앞에 공백을 넣어 종성과 구분.
#       마침표형 줄임표 ``…``/``...``(444)는 앞에 공백 (ㅍ·444 충돌 회피).
#       가운뎃점형 ``⋯``/``···``는 6점×3(``,,,``).
# 역점역: 공백 없이 짧은 어절(≤2) 뒤 ``4`` → 종성 ㅍ,
#         긴 어절(≥3) 또는 공백 뒤 ``4`` → 마침표.
#         줄임표(444/,,,) 앞 공백은 묵자에서 제거.
#         ``8``은 어절 길이 + 흔한 ㅌ받침 화이트리스트(보조)로 구분.
_PERIOD_JONG_DISAMBIG_MAX_SYL = 2
_JONG_PUNCT_DISAMBIG_MAX_SYL = _PERIOD_JONG_DISAMBIG_MAX_SYL

# 가류 약자 셀과 초성이 같은 음절(ㅎㅅㄷㅈㅋㅍ)+ㅕ+ㅆ.
# 하+였(j:/) 등과 헷갈리지 않도록 초성·모음 사이에 붙임줄(dots 36, ASCII '-')을 둔다.
_YEOSS_COUPLING_CHO = frozenset({"ㅎ", "ㅅ", "ㄷ", "ㅈ", "ㅋ", "ㅍ"})
_COUPLING_MARK = "-"  # 붙임줄 ⠤ (3-6)
# 「예」(ㅇ+ㅖ, 무받침): 앞 음절이 받침이 없으면 `/`(종성 ㅆ과 동형)이
# 받침으로 붙어 「윴/갰…」이 되므로 붙임줄을 끼운다. 어절 선두·받침 뒤는 `/`만.

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
    "…": "444",  # 마침표형 줄임표 (2-5-6)×3
    "⋯": ",,,",  # 가운뎃점형 줄임표 (6)×3 — ··· 런과 동일
    "·": '"2',  # 가운뎃점 ⠐⠆ (5 + 2-3). 旧 1;(⠂⠰)는 종성 ㄹ+초성 ㅊ과 충돌
    "ㆍ": '"2',  # 한글 방점/표 빈칸 관례 → 가운뎃점과 동일
    "∙": '"4',  # 항목 불릿 ⠐⠲ — 점역 시 뒤에 공백 필수
    "～": "@9",
    "~": "@9",
    "―": "--",
    "—": "--",
    "–": "--",
    "/": "_/",  # 빗금 — 단독 `/`는 ㅖ·ㅆ과 충돌하므로 ⠸⠌
    # = + − × ÷ ₩ $ 는 MATH_OP_TO_ASCII (수표 # + 본문)
    "*": "99",
    "※": "99",
    "ⓒ": "7c7",
}

# 숨김/기호 표: 4-5-6 + (단위)×개수 + 1-2-3
_HIDE_CIRCLE_CHARS = frozenset("○〇◯")
_HIDE_SQUARE_CHARS = frozenset("□■")
_HIDE_TRIANGLE_CHARS = frozenset("△")
_HIDE_X_CHARS = frozenset("✕✗")


def _encode_hide_circles(count: int) -> str:
    if count < 1:
        return ""
    return HIDE_MARK_OPEN + (HIDE_MARK_UNIT * count) + HIDE_MARK_CLOSE


def _encode_hide_squares(count: int) -> str:
    if count < 1:
        return ""
    return HIDE_MARK_OPEN + (HIDE_SQUARE_UNIT * count) + HIDE_MARK_CLOSE


def _encode_hide_triangle() -> str:
    return HIDE_MARK_OPEN + HIDE_TRIANGLE_UNIT + HIDE_MARK_CLOSE


def _encode_hide_x_mark() -> str:
    return HIDE_MARK_OPEN + HIDE_X_UNIT + HIDE_MARK_CLOSE


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

# ㉠–㉭ (원문자 ㄱ–ㅎ) → 드러냄+온표+초성. 2017: ㉠ → 7=@7 (구 BRF는 7=a7).
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

# ㉮–㉻ (원문자 가·나·다·…) → 드러냄+해당 음절 점형 (㉮→7$7)
_CIRCLED_HANGUL_SYLLABLE: dict[str, str] = {
    "㉮": "가",
    "㉯": "나",
    "㉰": "다",
    "㉱": "라",
    "㉲": "마",
    "㉳": "바",
    "㉴": "사",
    "㉵": "아",
    "㉶": "자",
    "㉷": "차",
    "㉸": "카",
    "㉹": "타",
    "㉺": "파",
    "㉻": "하",
}

_EMPHASIS_OPEN = ",-"
_EMPHASIS_CLOSE = "-'"
_U_TAG = re.compile(r"<u>(.*?)</u>", re.DOTALL)
# 보기·표 박스 직렬화 표선 (묵자 ──── → 점자 표선; 역점역은 ─×16)
_RULE_LINE = re.compile(r"^[\s]*[─━\-_=]{5,}[\s]*$")
_TABLE_RULE_ASCII = "!" + ("3" * 20) + "4"
# 빈칸·생략 표시용 가운뎃점 과다 연쇄 → 정확히 4개
_LONG_MIDDOT_RUN = re.compile(r"·{4,}")

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

    # 혔/셨/뎠/졌/켰/폈: 245(등)+36+156+34 — 붙임줄로 하+였 혼동 방지
    if jung == "ㅕ" and jong == "ㅆ" and cho in _YEOSS_COUPLING_CHO:
        cho_ascii = _CHO_TO_ASCII.get(cho)
        jung_ascii = _JUNG_TO_ASCII.get(jung)
        jong_ascii = _JONG_TO_ASCII.get(jong)
        if cho_ascii and jung_ascii and jong_ascii:
            return cho_ascii + _COUPLING_MARK + jung_ascii + jong_ascii

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


def _adjacent_to_digit(text: str, i: int) -> bool:
    """수식 `<` `>` `-` 판별: 앞·뒤가 숫자이면 수표 기호로 점역."""
    if i > 0 and text[i - 1].isdigit():
        return True
    j = i + 1
    while j < len(text) and text[j] in " \t":
        j += 1
    return j < len(text) and text[j].isdigit()


def _trailing_hangul_syllables(text: str, end: int) -> int:
    """``text[:end]`` 끝에서 이어지는 한글 음절 수 (어절)."""
    n = 0
    j = end - 1
    while j >= 0 and decompose_hangul(text[j]) is not None:
        n += 1
        j -= 1
    return n


def _collapse_long_middot_runs(text: str) -> str:
    """연속 ``·`` 4개 이상을 ``····`` 로 줄인다."""
    return _LONG_MIDDOT_RUN.sub("····", text)


def hangul_text_to_ascii(text: str) -> str:
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
    ascii_text, _mask = hangul_text_to_ascii_with_roman_mask(text)
    return ascii_text


def hangul_text_to_ascii_with_roman_mask(text: str) -> tuple[str, list[bool]]:
    """점역 ASCII와, 각 ASCII 문자가 로마자(라틴) 구간인지 마스크.

    마스크는 레이아웃 줄바꿈 시 «새 줄이 영어 구간으로 시작하는데
    로마자표가 빠졌는지» 판별에 쓴다. 개행 문자는 False.
    """
    text = replace_opaque_with_slash(text)
    text = replace_hanja_with_reading(text)
    text = _collapse_long_middot_runs(text)
    text = ensure_newline_before_reference_mark(text)
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
            a, m = _encode_line_with_emphasis_masked(line)
            ascii_parts.append(a)
            mask_parts.append(m)
    joined = "".join(ascii_parts)
    mask: list[bool] = []
    for part in mask_parts:
        mask.extend(part)
    assert len(mask) == len(joined)
    return joined, mask


def _encode_line_with_emphasis(line: str) -> str:
    """밑줄 태그를 강조 점자로 바꾼 뒤 일반 점역."""
    ascii_text, _mask = _encode_line_with_emphasis_masked(line)
    return ascii_text


def _encode_line_with_emphasis_masked(line: str) -> tuple[str, list[bool]]:
    """밑줄 태그를 강조 점자로 바꾼 뒤 일반 점역 + 로마 마스크."""
    ascii_parts: list[str] = []
    mask: list[bool] = []
    cursor = 0
    for m in _U_TAG.finditer(line):
        a, mk = _encode_line_masked(line[cursor : m.start()])
        ascii_parts.append(a)
        mask.extend(mk)
        ascii_parts.append(_EMPHASIS_OPEN)
        mask.extend([False] * len(_EMPHASIS_OPEN))
        a, mk = _encode_line_masked(m.group(1))
        ascii_parts.append(a)
        mask.extend(mk)
        ascii_parts.append(_EMPHASIS_CLOSE)
        mask.extend([False] * len(_EMPHASIS_CLOSE))
        cursor = m.end()
    a, mk = _encode_line_masked(line[cursor:])
    ascii_parts.append(a)
    mask.extend(mk)
    return "".join(ascii_parts), mask


def _encode_line(line: str) -> str:
    """지문 범위·문항 번호는 점자 ASCII로 직접 넣고, 나머지 묵자만 점역."""
    ascii_text, _mask = _encode_line_masked(line)
    return ascii_text


def _encode_line_masked(line: str) -> tuple[str, list[bool]]:
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
        a, mk = _hangul_body_to_ascii_masked(line[cursor : m.start()])
        ascii_parts.append(a)
        mask.extend(mk)
        piece = _encode_passage_range(m)
        ascii_parts.append(piece)
        mask.extend([False] * len(piece))
        cursor = m.end()

    a, mk = _hangul_body_to_ascii_masked(line[cursor:])
    ascii_parts.append(a)
    mask.extend(mk)
    return "".join(ascii_parts), mask


def _hangul_body_to_ascii(text: str) -> str:
    ascii_text, _mask = _hangul_body_to_ascii_masked(text)
    return ascii_text


def _hangul_body_to_ascii_masked(text: str) -> tuple[str, list[bool]]:
    out: list[str] = []
    mask: list[bool] = []
    # 직전 한글 음절이 받침 없음 → 이어지는 「예」에 붙임줄 필요
    prev_open_syl = False

    def emit(piece: str, *, roman: bool = False) -> None:
        if not piece:
            return
        out.append(piece)
        mask.extend([roman] * len(piece))

    i = 0
    n = len(text)
    while i < n:
        ch = text[i]

        if ch in " \t":
            emit(" ")
            prev_open_syl = False
            i += 1
            continue

        matched_word = False
        for hangul, cells in _WORD_ABBREV_REV:
            if text.startswith(hangul, i):
                emit(cells)
                last = decompose_hangul(hangul[-1]) if hangul else None
                prev_open_syl = last is not None and not last[2]
                i += len(hangul)
                matched_word = True
                break
        if matched_word:
            continue

        if ch in _HIDE_CIRCLE_CHARS:
            j = i
            while j < n and text[j] in _HIDE_CIRCLE_CHARS:
                j += 1
            emit(_encode_hide_circles(j - i))
            prev_open_syl = False
            i = j
            continue

        if ch in _HIDE_SQUARE_CHARS:
            j = i
            while j < n and text[j] in _HIDE_SQUARE_CHARS:
                j += 1
            emit(_encode_hide_squares(j - i))
            prev_open_syl = False
            i = j
            continue

        if ch in _HIDE_TRIANGLE_CHARS:
            emit(_encode_hide_triangle())
            prev_open_syl = False
            i += 1
            continue

        if ch in _HIDE_X_CHARS:
            emit(_encode_hide_x_mark())
            prev_open_syl = False
            i += 1
            continue

        if ch == ARROW_RIGHT_INK:
            emit(ARROW_RIGHT_BRAILLE_ASCII)
            prev_open_syl = False
            i += 1
            continue

        if ch in _CIRCLED_DIGIT_CELL:
            emit("7#" + _CIRCLED_DIGIT_CELL[ch] + "7")
            prev_open_syl = False
            i += 1
            continue

        if ch in _CIRCLED_LATIN_CELL:
            emit("7" + _CIRCLED_LATIN_CELL[ch] + "7")
            prev_open_syl = False
            i += 1
            continue

        if ch in _CIRCLED_HANGUL_JAMO:
            jamo = _CIRCLED_HANGUL_JAMO[ch]
            body = JAMO_COMPAT_TO_ASCII.get(jamo)
            if body:
                emit("7" + body + "7")
            prev_open_syl = False
            i += 1
            continue

        if ch in _CIRCLED_HANGUL_SYLLABLE:
            syl = _CIRCLED_HANGUL_SYLLABLE[ch]
            body, _ = _hangul_body_to_ascii_masked(syl)
            if body:
                emit("7" + body + "7")
            prev_open_syl = False
            i += 1
            continue

        if ch.isdigit():
            digit_start = i
            digits: list[str] = []
            while i < n and text[i].isdigit():
                digits.append(_DIGIT_TO_ASCII[text[i]])
                i += 1
            emit(NUMBER_SIGN + "".join(digits))
            if i < n and text[i] not in " \t":
                nxt = text[i]
                after_open_bracket = digit_start > 0 and text[digit_start - 1] in "[【"
                attach_punct = (
                    nxt in _PUNCT_TO_ASCII
                    or nxt in MATH_OP_TO_ASCII
                    or (nxt in "<>-" and _adjacent_to_digit(text, i))
                )
                if not (
                    attach_punct
                    or (after_open_bracket and _is_hangul(nxt))
                ):
                    emit(" ")
            prev_open_syl = False
            continue

        if ("A" <= ch <= "Z") or ("a" <= ch <= "z"):
            # 로마자 구간 전체(표지·글자·영문 내 공백/괄호/쉼표)를 마스크 True.
            # 구간이 끝난 뒤 비로마가 이어지면 로마자종료표(4/⠲)를 붙인다.
            emit(ROMAN_SIGN, roman=True)
            while i < n:
                c = text[i]
                if ("A" <= c <= "Z") or ("a" <= c <= "z"):
                    emit("," + c.lower() if "A" <= c <= "Z" else c, roman=True)
                    i += 1
                    continue
                if c == " " and i + 1 < n and (
                    ("A" <= text[i + 1] <= "Z") or ("a" <= text[i + 1] <= "z")
                ):
                    emit(" ", roman=True)
                    i += 1
                    continue
                if c in "()" and c in _PUNCT_TO_ASCII:
                    emit(_PUNCT_TO_ASCII[c], roman=True)
                    i += 1
                    continue
                if c == ",":
                    j = i + 1
                    while j < n and text[j] in " \t":
                        j += 1
                    if j < n and (
                        ("A" <= text[j] <= "Z") or ("a" <= text[j] <= "z")
                    ):
                        emit("1", roman=True)
                        i += 1
                        continue
                    break
                break
            if i < n:
                emit(ROMAN_END_SIGN)
            prev_open_syl = False
            continue

        decomp = decompose_hangul(ch)
        if decomp is not None:
            cho, jung, jong = decomp
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
                    emit(cho_ascii + "<")
                else:
                    emit(_encode_syllable(cho, jung, jong))
            else:
                piece = _encode_syllable(*decomp)
                # 유예 → 윴 방지: 받침 없는 음절 뒤 「예」 앞에 붙임줄
                if (
                    prev_open_syl
                    and cho == "ㅇ"
                    and jung == "ㅖ"
                    and not jong
                ):
                    piece = _COUPLING_MARK + piece
                emit(piece)
            prev_open_syl = not jong
            i += 1
            continue

        if ch in MATH_OP_TO_ASCII and ch not in "<>":
            # + − × ÷ = ₩ $ — 수표(#) 접두. <> 는 숫자 인접 시에만.
            emit(MATH_OP_TO_ASCII[ch])
            prev_open_syl = False
            i += 1
            continue

        if ch in _PUNCT_TO_ASCII:
            prev_open_syl = False
            if ch in "<>":
                if _adjacent_to_digit(text, i):
                    emit(MATH_OP_TO_ASCII[ch])
                else:
                    emit(_PUNCT_TO_ASCII[ch])
                i += 1
                continue
            if ch == "-" and _adjacent_to_digit(text, i):
                emit(MATH_OP_TO_ASCII["−"])
                i += 1
                continue
            if ch == "⋯":
                emit(",,,")
                i += 1
                continue
            if ch == "·":
                run = 0
                while i + run < n and text[i + run] == "·":
                    run += 1
                if run == 3:
                    # 가운뎃점형 줄임표 (정확히 3개) → 6점×3
                    emit(",,,")
                    i += 3
                    continue
                # 1·2·4개: 각 · 를 가운뎃점으로 (4개+=빈칸 축약 후)
                for _ in range(run):
                    while out and out[-1] == " ":
                        out.pop()
                        mask.pop()
                    if out:
                        emit(" ")
                    emit('"2')
                i += run
                while i < n and text[i] in " \t":
                    i += 1
                if i < n:
                    emit(" ")
                continue
            if ch == "…" or (
                ch == "."
                and i + 2 < n
                and text[i + 1] == "."
                and text[i + 2] == "."
            ):
                # 마침표형 줄임표: … 또는 ...(+연속 .) → 2-5-6×3, 앞에 공백
                if out and out[-1] != " ":
                    emit(" ")
                emit("444")
                if ch == "…":
                    i += 1
                else:
                    i += 3
                    while i < n and text[i] == ".":
                        i += 1
                continue
            if ch == "ㆍ":
                while out and out[-1] == " ":
                    out.pop()
                    mask.pop()
                if out:
                    emit(" ")
                emit(_PUNCT_TO_ASCII[ch])
                i += 1
                while i < n and text[i] in " \t":
                    i += 1
                if i < n:
                    emit(" ")
                continue
            if ch == "∙":
                emit(_PUNCT_TO_ASCII[ch])
                i += 1
                while i < n and text[i] in " \t":
                    i += 1
                emit(" ")
                continue
            if ch in (".", "?", "!"):
                syl = _trailing_hangul_syllables(text, i)
                if (
                    1 <= syl <= _JONG_PUNCT_DISAMBIG_MAX_SYL
                    and (not out or out[-1] != " ")
                ):
                    emit(" ")
                emit(_PUNCT_TO_ASCII[ch])
                i += 1
                continue
            emit(_PUNCT_TO_ASCII[ch])
            i += 1
            continue

        if ch in JAMO_COMPAT_TO_ASCII:
            emit(JAMO_COMPAT_TO_ASCII[ch])
            prev_open_syl = False
            i += 1
            continue

        if 0x3131 <= ord(ch) <= 0x318E:
            emit("=?")
            prev_open_syl = False
            i += 1
            continue

        prev_open_syl = False
        i += 1

    return "".join(out), mask


class TableBrailleTranslator:
    """korean_tables 기반 정방향 점역."""

    def translate_text(self, text: str) -> BrailleSequence:
        ascii_text, roman_mask = hangul_text_to_ascii_with_roman_mask(text)
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
        return BrailleSequence(
            source_node_id="",
            tokens=tokens,
            metadata={
                "translator": "TableBrailleTranslator",
                "ascii": flat_ascii,
                "roman_mask": roman_mask,
            },
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
            node.node_type == "Passage"
            and genre == DEFAULT_PASSAGE_INDENT_GENRE_CONFIG.label_si
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
