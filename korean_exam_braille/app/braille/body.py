"""본문 점역 파이프라인: 분류 → 종류별 점역 → 경계.

점역 ASCII는 ``encode_body`` 에서만 만든다. ``tokenize_body`` 는
「이 구간은 숫자/한글/로마/…다」만 판정한다.

새 기호는 보통 (1) 렉서에 종류 추가 (2) 해당 점역기 추가.
경계 규칙(숫자 뒤 공백, 예 붙임줄, 로마 종료표)은 encode 쪽이 맡는다.
"""

from __future__ import annotations

from dataclasses import dataclass

from korean_exam_braille.app.common.arrow_markup import (
    ARROW_RIGHT_BRAILLE_ASCII,
    ARROW_RIGHT_INK,
)
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

UNKNOWN_PRINT_ASCII = "=?"
_COUPLING_MARK = "-"
_YEOSS_COUPLING_CHO = frozenset({"ㅎ", "ㅅ", "ㄷ", "ㅈ", "ㅋ", "ㅍ"})
_JONG_PUNCT_DISAMBIG_MAX_SYL = 2

KIND_SPACE = "space"
KIND_ABBREV = "abbrev"
KIND_HIDE_CIRCLE = "hide_circle"
KIND_HIDE_SQUARE = "hide_square"
KIND_HIDE_TRIANGLE = "hide_triangle"
KIND_HIDE_X = "hide_x"
KIND_ARROW = "arrow"
KIND_CIRCLED_DIGIT = "circled_digit"
KIND_CIRCLED_LATIN = "circled_latin"
KIND_CIRCLED_JAMO = "circled_jamo"
KIND_CIRCLED_SYLLABLE = "circled_syllable"
KIND_DIGIT = "digit"
KIND_ROMAN = "roman"
KIND_HANGUL = "hangul"
KIND_MATH = "math"
KIND_PUNCT = "punct"
KIND_JAMO = "jamo"
KIND_JAMO_UNKNOWN = "jamo_unknown"
KIND_NEWLINE = "newline"
KIND_UNKNOWN = "unknown"


@dataclass(frozen=True)
class BodyToken:
    """묵자 구간. ``text`` 는 의미 있는 글자, ``end`` 는 소비 끝(후행 공백 포함)."""

    kind: str
    start: int
    end: int
    text: str


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
    ",": '"',
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
    "⋯": ",,,",
    "·": '"2',
    "ㆍ": '"2',
    "∙": '"4',
    "～": "@9",
    "~": "@9",
    "―": "--",
    "—": "--",
    "–": "--",
    "/": "_/",
    "*": "99",
    "※": "99",
    "ⓒ": "7c7",
}

_HIDE_CIRCLE_CHARS = frozenset("○〇◯")
_HIDE_SQUARE_CHARS = frozenset("□■")
_HIDE_TRIANGLE_CHARS = frozenset("△")
_HIDE_X_CHARS = frozenset("✕✗")

_CIRCLED_DIGIT_CELL = {
    "①": "a",
    "②": "b",
    "③": "c",
    "④": "d",
    "⑤": "e",
}
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


def _is_hangul(ch: str) -> bool:
    return decompose_hangul(ch) is not None


def _is_ascii_digit(ch: str) -> bool:
    return "0" <= ch <= "9"


def _is_latin(ch: str) -> bool:
    return ("A" <= ch <= "Z") or ("a" <= ch <= "z")


def _adjacent_to_digit(text: str, i: int) -> bool:
    if i > 0 and _is_ascii_digit(text[i - 1]):
        return True
    j = i + 1
    while j < len(text) and text[j] in " \t":
        j += 1
    return j < len(text) and _is_ascii_digit(text[j])


def _trailing_hangul_syllables(text: str, end: int) -> int:
    n = 0
    j = end - 1
    while j >= 0 and decompose_hangul(text[j]) is not None:
        n += 1
        j -= 1
    return n


def _encode_syllable(cho: str, jung: str, jong: str) -> str:
    if cho == "ㄱ" and jung == "ㅓ" and jong == "ㅅ":
        return ABBREV_GEOT
    if cho == "ㅇ" and (jung, jong) in _VC_ABBREV:
        return _VC_ABBREV[(jung, jong)]
    if cho != "ㅇ" and (jung, jong) in _VC_ABBREV:
        cho_ascii = _CHO_TO_ASCII.get(cho)
        if cho_ascii:
            return cho_ascii + _VC_ABBREV[(jung, jong)]
    if jung == "ㅕ" and jong == "ㅆ" and cho in _YEOSS_COUPLING_CHO:
        cho_ascii = _CHO_TO_ASCII.get(cho)
        jung_ascii = _JUNG_TO_ASCII.get(jung)
        jong_ascii = _JONG_TO_ASCII.get(jong)
        if cho_ascii and jung_ascii and jong_ascii:
            return cho_ascii + _COUPLING_MARK + jung_ascii + jong_ascii
    if jung == "ㅏ" and cho in _CV_ABBREV_BY_CHO:
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


def _skip_spaces(text: str, i: int) -> int:
    n = len(text)
    while i < n and text[i] in " \t":
        i += 1
    return i


def _token(kind: str, text: str, start: int, end: int) -> BodyToken:
    return BodyToken(kind=kind, start=start, end=end, text=text)


# --- 1. 분류 (점역 없음) -------------------------------------------------


def tokenize_body(text: str) -> list[BodyToken]:
    """묵자를 종류별 구간으로만 나눈다. ASCII 점자는 만들지 않는다."""
    out: list[BodyToken] = []
    i = 0
    n = len(text)
    while i < n:
        tok = _next_token(text, i)
        out.append(tok)
        i = tok.end
    return out


def _next_token(text: str, i: int) -> BodyToken:
    ch = text[i]
    n = len(text)

    if ch in " \t":
        return _token(KIND_SPACE, ch, i, i + 1)

    for hangul, _cells in _WORD_ABBREV_REV:
        if text.startswith(hangul, i):
            return _token(KIND_ABBREV, hangul, i, i + len(hangul))

    if ch in _HIDE_CIRCLE_CHARS:
        j = i
        while j < n and text[j] in _HIDE_CIRCLE_CHARS:
            j += 1
        return _token(KIND_HIDE_CIRCLE, text[i:j], i, j)

    if ch in _HIDE_SQUARE_CHARS:
        j = i
        while j < n and text[j] in _HIDE_SQUARE_CHARS:
            j += 1
        return _token(KIND_HIDE_SQUARE, text[i:j], i, j)

    if ch in _HIDE_TRIANGLE_CHARS:
        return _token(KIND_HIDE_TRIANGLE, ch, i, i + 1)

    if ch in _HIDE_X_CHARS:
        return _token(KIND_HIDE_X, ch, i, i + 1)

    if ch == ARROW_RIGHT_INK:
        return _token(KIND_ARROW, ch, i, i + 1)

    if ch in _CIRCLED_DIGIT_CELL:
        return _token(KIND_CIRCLED_DIGIT, ch, i, i + 1)

    if ch in _CIRCLED_LATIN_CELL:
        return _token(KIND_CIRCLED_LATIN, ch, i, i + 1)

    if ch in _CIRCLED_HANGUL_JAMO:
        return _token(KIND_CIRCLED_JAMO, ch, i, i + 1)

    if ch in _CIRCLED_HANGUL_SYLLABLE:
        return _token(KIND_CIRCLED_SYLLABLE, ch, i, i + 1)

    if _is_ascii_digit(ch):
        j = i
        while j < n and _is_ascii_digit(text[j]):
            j += 1
        return _token(KIND_DIGIT, text[i:j], i, j)

    if _is_latin(ch):
        return _scan_roman(text, i)

    if decompose_hangul(ch) is not None:
        return _token(KIND_HANGUL, ch, i, i + 1)

    if ch in MATH_OP_TO_ASCII and ch not in "<>":
        return _token(KIND_MATH, ch, i, i + 1)

    if ch in "<>" and _adjacent_to_digit(text, i):
        return _token(KIND_MATH, ch, i, i + 1)

    if ch == "-" and _adjacent_to_digit(text, i):
        return _token(KIND_MATH, ch, i, i + 1)

    if ch in _PUNCT_TO_ASCII:
        return _scan_punct(text, i)

    if ch in JAMO_COMPAT_TO_ASCII:
        return _token(KIND_JAMO, ch, i, i + 1)

    if 0x3131 <= ord(ch) <= 0x318E:
        return _token(KIND_JAMO_UNKNOWN, ch, i, i + 1)

    if ch in "\n\r":
        return _token(KIND_NEWLINE, ch, i, i + 1)

    if ch.isspace():
        return _token(KIND_SPACE, ch, i, i + 1)

    return _token(KIND_UNKNOWN, ch, i, i + 1)


def _scan_roman(text: str, i: int) -> BodyToken:
    start = i
    n = len(text)
    while i < n:
        c = text[i]
        if _is_latin(c):
            i += 1
            continue
        if c == " " and i + 1 < n and _is_latin(text[i + 1]):
            i += 1
            continue
        if c in "()" and c in _PUNCT_TO_ASCII:
            i += 1
            continue
        if c == ",":
            j = i + 1
            while j < n and text[j] in " \t":
                j += 1
            if j < n and _is_latin(text[j]):
                i += 1
                continue
            break
        break
    return _token(KIND_ROMAN, text[start:i], start, i)


def _scan_punct(text: str, i: int) -> BodyToken:
    ch = text[i]
    n = len(text)
    if ch == "·":
        j = i
        while j < n and text[j] == "·":
            j += 1
        run = text[i:j]
        j = _skip_spaces(text, j)
        return _token(KIND_PUNCT, run, i, j)
    if ch == "…" or (
        ch == "." and i + 2 < n and text[i + 1] == "." and text[i + 2] == "."
    ):
        if ch == "…":
            return _token(KIND_PUNCT, "…", i, i + 1)
        j = i + 3
        while j < n and text[j] == ".":
            j += 1
        return _token(KIND_PUNCT, text[i:j], i, j)
    if ch in "ㆍ∙":
        j = _skip_spaces(text, i + 1)
        return _token(KIND_PUNCT, ch, i, j)
    return _token(KIND_PUNCT, ch, i, i + 1)


# --- 2. 종류별 점역 -------------------------------------------------------


class _Emitter:
    def __init__(self) -> None:
        self.out: list[str] = []
        self.mask: list[bool] = []
        self.prev_open_syl = False

    def emit(self, piece: str, *, roman: bool = False) -> None:
        if not piece:
            return
        self.out.append(piece)
        self.mask.extend([roman] * len(piece))

    def pop_trailing_spaces(self) -> None:
        while self.out and self.out[-1] == " ":
            self.out.pop()
            self.mask.pop()

    def last_is_space(self) -> bool:
        return bool(self.out) and self.out[-1] == " "


def hangul_body_to_ascii_masked(
    text: str,
    *,
    unknown: list[str] | None = None,
) -> tuple[str, list[bool]]:
    tokens = tokenize_body(text)
    return encode_body(text, tokens, unknown=unknown)


def encode_body(
    text: str,
    tokens: list[BodyToken],
    *,
    unknown: list[str] | None = None,
) -> tuple[str, list[bool]]:
    em = _Emitter()
    for tok in tokens:
        _encode_token(em, tok, text, unknown)
    return "".join(em.out), em.mask


def _encode_token(
    em: _Emitter,
    tok: BodyToken,
    text: str,
    unknown: list[str] | None,
) -> None:
    fn = _ENCODERS[tok.kind]
    fn(em, tok, text, unknown)


def _enc_space(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    em.emit(" ")
    em.prev_open_syl = False


def _enc_abbrev(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    cells = WORD_ABBREV_LOOKUP[tok.text]
    em.emit(cells)
    last = decompose_hangul(tok.text[-1]) if tok.text else None
    em.prev_open_syl = last is not None and not last[2]


WORD_ABBREV_LOOKUP = dict(_WORD_ABBREV_REV)


def _enc_hide_circle(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    count = len(tok.text)
    if count >= 1:
        em.emit(HIDE_MARK_OPEN + (HIDE_MARK_UNIT * count) + HIDE_MARK_CLOSE)
    em.prev_open_syl = False


def _enc_hide_square(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    count = len(tok.text)
    if count >= 1:
        em.emit(HIDE_MARK_OPEN + (HIDE_SQUARE_UNIT * count) + HIDE_MARK_CLOSE)
    em.prev_open_syl = False


def _enc_hide_triangle(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    em.emit(HIDE_MARK_OPEN + HIDE_TRIANGLE_UNIT + HIDE_MARK_CLOSE)
    em.prev_open_syl = False


def _enc_hide_x(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    em.emit(HIDE_MARK_OPEN + HIDE_X_UNIT + HIDE_MARK_CLOSE)
    em.prev_open_syl = False


def _enc_arrow(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    em.emit(ARROW_RIGHT_BRAILLE_ASCII)
    em.prev_open_syl = False


def _enc_circled_digit(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    em.emit("7#" + _CIRCLED_DIGIT_CELL[tok.text] + "7")
    em.prev_open_syl = False


def _enc_circled_latin(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    em.emit("7" + _CIRCLED_LATIN_CELL[tok.text] + "7")
    em.prev_open_syl = False


def _enc_circled_jamo(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    jamo = _CIRCLED_HANGUL_JAMO[tok.text]
    body = JAMO_COMPAT_TO_ASCII.get(jamo)
    if body:
        em.emit("7" + body + "7")
    else:
        em.emit(UNKNOWN_PRINT_ASCII)
        if unknown is not None:
            unknown.append(tok.text)
    em.prev_open_syl = False


def _enc_circled_syllable(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    syl = _CIRCLED_HANGUL_SYLLABLE[tok.text]
    body, _ = hangul_body_to_ascii_masked(syl, unknown=unknown)
    if body:
        em.emit("7" + body + "7")
    else:
        em.emit(UNKNOWN_PRINT_ASCII)
        if unknown is not None:
            unknown.append(tok.text)
    em.prev_open_syl = False


def _enc_digit(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    digits = "".join(_DIGIT_TO_ASCII[d] for d in tok.text)
    em.emit(NUMBER_SIGN + digits)
    i = tok.end
    n = len(text)
    if i < n and text[i] not in " \t":
        nxt = text[i]
        after_open_bracket = tok.start > 0 and text[tok.start - 1] in "[【"
        attach_punct = (
            nxt in _PUNCT_TO_ASCII
            or nxt in MATH_OP_TO_ASCII
            or (nxt in "<>-" and _adjacent_to_digit(text, i))
        )
        if not (
            attach_punct
            or (after_open_bracket and _is_hangul(nxt))
        ):
            em.emit(" ")
    em.prev_open_syl = False


def _enc_roman(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    em.emit(ROMAN_SIGN, roman=True)
    k = 0
    span = tok.text
    m = len(span)
    while k < m:
        c = span[k]
        if _is_latin(c):
            em.emit("," + c.lower() if "A" <= c <= "Z" else c, roman=True)
            k += 1
            continue
        if c == " ":
            em.emit(" ", roman=True)
            k += 1
            continue
        if c in "()":
            em.emit(_PUNCT_TO_ASCII[c], roman=True)
            k += 1
            continue
        if c == ",":
            em.emit("1", roman=True)
            k += 1
            continue
        break
    if tok.end < len(text):
        em.emit(ROMAN_END_SIGN)
    em.prev_open_syl = False


def _enc_hangul(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    decomp = decompose_hangul(tok.text)
    if decomp is None:
        em.emit(UNKNOWN_PRINT_ASCII)
        em.prev_open_syl = False
        return
    cho, jung, jong = decomp
    next_de = decompose_hangul(text[tok.end]) if tok.end < len(text) else None
    if (
        jung == "ㅏ"
        and not jong
        and cho in _CV_ABBREV_BY_CHO
        and next_de is not None
        and next_de[0] == "ㅇ"
    ):
        cho_ascii = _CHO_TO_ASCII.get(cho)
        if cho_ascii is not None:
            em.emit(cho_ascii + "<")
        else:
            em.emit(_encode_syllable(cho, jung, jong))
    else:
        piece = _encode_syllable(*decomp)
        if (
            em.prev_open_syl
            and cho == "ㅇ"
            and jung == "ㅖ"
            and not jong
        ):
            piece = _COUPLING_MARK + piece
        em.emit(piece)
    em.prev_open_syl = not jong


def _enc_math(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    key = "−" if tok.text == "-" else tok.text
    em.emit(MATH_OP_TO_ASCII[key])
    em.prev_open_syl = False


def _enc_punct(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    ch = tok.text[0]
    em.prev_open_syl = False
    if ch == "⋯" or (ch == "·" and len(tok.text) == 3):
        em.emit(",,,")
        return
    if ch == "·":
        for _ in tok.text:
            em.pop_trailing_spaces()
            if em.out:
                em.emit(" ")
            em.emit('"2')
        if tok.end < len(text):
            em.emit(" ")
        return
    if ch == "…" or tok.text.startswith("..."):
        if em.out and not em.last_is_space():
            em.emit(" ")
        em.emit("444")
        return
    if ch == "ㆍ":
        em.pop_trailing_spaces()
        if em.out:
            em.emit(" ")
        em.emit(_PUNCT_TO_ASCII[ch])
        if tok.end < len(text):
            em.emit(" ")
        return
    if ch == "∙":
        em.emit(_PUNCT_TO_ASCII[ch])
        em.emit(" ")
        return
    if ch in (".", "?", "!"):
        syl = _trailing_hangul_syllables(text, tok.start)
        if 1 <= syl <= _JONG_PUNCT_DISAMBIG_MAX_SYL and not em.last_is_space():
            em.emit(" ")
        em.emit(_PUNCT_TO_ASCII[ch])
        return
    em.emit(_PUNCT_TO_ASCII[ch])


def _enc_jamo(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    em.emit(JAMO_COMPAT_TO_ASCII[tok.text])
    em.prev_open_syl = False


def _enc_jamo_unknown(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    em.emit(UNKNOWN_PRINT_ASCII)
    em.prev_open_syl = False


def _enc_newline(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    em.emit(tok.text)
    em.prev_open_syl = False


def _enc_unknown(em: _Emitter, tok: BodyToken, text: str, unknown: list[str] | None) -> None:
    em.emit(UNKNOWN_PRINT_ASCII)
    if unknown is not None:
        unknown.append(tok.text)
    em.prev_open_syl = False


_ENCODERS = {
    KIND_SPACE: _enc_space,
    KIND_ABBREV: _enc_abbrev,
    KIND_HIDE_CIRCLE: _enc_hide_circle,
    KIND_HIDE_SQUARE: _enc_hide_square,
    KIND_HIDE_TRIANGLE: _enc_hide_triangle,
    KIND_HIDE_X: _enc_hide_x,
    KIND_ARROW: _enc_arrow,
    KIND_CIRCLED_DIGIT: _enc_circled_digit,
    KIND_CIRCLED_LATIN: _enc_circled_latin,
    KIND_CIRCLED_JAMO: _enc_circled_jamo,
    KIND_CIRCLED_SYLLABLE: _enc_circled_syllable,
    KIND_DIGIT: _enc_digit,
    KIND_ROMAN: _enc_roman,
    KIND_HANGUL: _enc_hangul,
    KIND_MATH: _enc_math,
    KIND_PUNCT: _enc_punct,
    KIND_JAMO: _enc_jamo,
    KIND_JAMO_UNKNOWN: _enc_jamo_unknown,
    KIND_NEWLINE: _enc_newline,
    KIND_UNKNOWN: _enc_unknown,
}
