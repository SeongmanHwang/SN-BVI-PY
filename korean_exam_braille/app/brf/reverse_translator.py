"""한국 점자 규정 기반 묵자 역점역.

Inspector·내용 비교용. 단순 1셀 치환이 아니라:

1. 복합 문장부호 최장 일치
2. 수표·온표·로마자표 상태
3. 약자·약어
4. 초성·모음·종성 음절 분석 (초성 ㅇ 생략)
5. 미인식 셀은 · 가 아니라 <U:…> 로 보존
"""

from __future__ import annotations

import re

from korean_exam_braille.app.brf.ascii_braille import normalize_brf_ascii
from korean_exam_braille.app.common.arrow_markup import (
    ARROW_RIGHT_BRAILLE_ASCII,
    ARROW_RIGHT_INK,
)
from korean_exam_braille.app.common.figure_markup import (
    FIGURE_BRAILLE_ASCII,
    FIGURE_INK,
)
from korean_exam_braille.app.common.plot_summary_markup import (
    PLOT_SUMMARY_END_BRAILLE_ASCII,
    PLOT_SUMMARY_END_INK,
)
from korean_exam_braille.app.common.korean_tables import (
    ABBREV_CV,
    ABBREV_GEOT,
    ABBREV_VC,
    CHOSEONG,
    CHOSEONG_IEUNG,
    JONGSEONG,
    JONGSEONG_DIGRAPHS,
    JUNGSEONG,
    JUNGSEONG_DIGRAPHS,
    LETTER_SIGN,
    MATH_OP_BODIES,
    HIDE_MARK_CLOSE,
    HIDE_MARK_OPEN,
    HIDE_MARK_UNIT,
    HIDE_SQUARE_UNIT,
    HIDE_TRIANGLE_UNIT,
    HIDE_X_UNIT,
    ROMAN_END_SIGN,
    NUMBER_MAP,
    NUMBER_SIGN,
    ON_SIGN,
    ON_SIGN_BODIES,
    PUNCT_MULTI,
    PUNCT_SINGLE,
    ROMAN_SIGN,
    TENSED_MAP,
    TENSED_PREFIX,
    WORD_ABBREV,
    YEONG_ONSET_OVERRIDE,
    compose_hangul,
)

# 최장 일치용 정렬 — 길이 우선, 같은 길이면 대·중·소괄호 우선
_BRACKET_PUNCT_KEYS = frozenset({"82", ";0", "81", '"0', "8'", ",0", "78", "07"})
_PUNCT_MULTI_SORTED: list[tuple[str, str]] = sorted(
    PUNCT_MULTI.items(),
    key=lambda kv: (-len(kv[0]), 0 if kv[0] in _BRACKET_PUNCT_KEYS else 1),
)

# 종성으로 붙이면 안 되는 닫는 복합 부호 접두 (2칸+)
_CLOSING_MULTI_PREFIXES = frozenset(
    k
    for k, v in PUNCT_MULTI.items()
    if v in {"’", "”", "』", "」", ")", "}", "]", "〉", "》", ">"}
) | frozenset({"0'", "02", "01", "00", ",0", "07", ";0"})

_LATIN_LETTERS = frozenset("abcdefghijklmnopqrstuvwxyz")

# 직전 묵자가 로마/원문자/숫자 계열이면 뒤의 ,- 를 제39항 한글표로 본다.
_HANGUL_INDICATOR_PREV = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    "ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ"
    "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮"
    "㉠㉡㉢㉣㉤㉥㉦㉧㉨㉩㉪㉫㉬㉭"
    "㉮㉯㉰㉱㉲㉳㉴㉵㉶㉷㉸㉹㉺㉻"
)

# 원문자 가–하 (㉮–㉻). 본문이 라틴 1글자(c/i/e…)와 겹치면 라틴 원문자(ⓒ…) 우선.
_CIRCLED_HANGUL_SYL_ASCII: list[tuple[str, str]] = sorted(
    [
        ("$", "㉮"),  # 가
        ("c", "㉯"),  # 나 — ⓒ 와 충돌, 역점역은 라틴 우선
        ("i", "㉰"),  # 다 — ⓘ
        ('"<', "㉱"),  # 라
        ("e", "㉲"),  # 마 — ⓔ
        ("^", "㉳"),  # 바
        ("l", "㉴"),  # 사 — ⓛ
        ("<", "㉵"),  # 아
        (".", "㉶"),  # 자
        (";<", "㉷"),  # 차
        ("f", "㉸"),  # 카 — ⓕ
        ("h", "㉹"),  # 타 — ⓗ
        ("d", "㉺"),  # 파 — ⓓ
        ("j", "㉻"),  # 하 — ⓙ
    ],
    key=lambda kv: (-len(kv[0]), kv[0]),
)
_CIRCLED_HANGUL_SYL_SAFE = [
    (body, ink)
    for body, ink in _CIRCLED_HANGUL_SYL_ASCII
    if not (len(body) == 1 and body in _LATIN_LETTERS)
]

# 시험 지문 범위: 82#a`9#c;0 → [1~3] (normalize 후 ` → @)
_PASSAGE_RANGE_ASCII = re.compile(
    r"82#([a-jA-J]+)[@`]9#([a-jA-J]+);0(4)?"
)
# 본문 숫자 범위: #aj@9#ae → 10~15
_NUM_RANGE_ASCII = re.compile(
    r"#([a-jA-J]+)[@`]9#([a-jA-J]+)"
)


def _norm_cell(ch: str) -> str:
    if ch == "`":
        return "@"
    return ch.lower() if ch.isalpha() else ch


def _is_boundary(ch: str | None) -> bool:
    return ch is None or ch == " "


def _is_tail_boundary(chars: list[str], i: int) -> bool:
    """문장·어절 끝: EOL, 공백, 또는 밑줄 표지(,- / -').

    마침표(4)·느낌표 등은 포함하지 않는다 — 호출부에서 별도 처리.
    """
    if i >= len(chars):
        return True
    if chars[i] == " ":
        return True
    matched = _match_punct(chars, i)
    return matched is not None and matched[0] in {"<u>", "</u>"}


def _is_period_disambig_boundary(chars: list[str], after_i: int) -> bool:
    """종성 ㅍ vs 마침표 구분용 경계.

    공백·EOL·밑줄(,- / -')·닫는 따옴표/괄호 앞에서 ``4``를 마침표 후보로 본다.
    """
    if _is_tail_boundary(chars, after_i):
        return True
    return after_i < len(chars) and _starts_closing_multi(chars, after_i)


_JONG_PUNCT_DISAMBIG_MAX_SYL = 2


def _out_word_hangul_count(out: list[str] | None) -> int:
    """출력 버퍼에서 직전 공백 이후 한글 음절 수."""
    if not out:
        return 0
    n = 0
    for ch in reversed(out):
        if ch == " ":
            break
        if len(ch) == 1 and "\uac00" <= ch <= "\ud7a3":
            n += 1
            continue
        if ch in {"‘", "’", "“", "”", "「", "」", "『", "』", "〈", "〉", "《", "》"}:
            continue
        if ch:
            break
    return n


def _is_separator_line(text: str) -> bool:
    s = text.strip()
    if len(s) < 6:
        return False
    body = s.replace(" ", "")
    if len(body) < 6:
        return False
    # =ggg…g= 또는 =777…7= (참고 BRF 구분선)
    if (
        s.startswith("=")
        and s.endswith("=")
        and set(body) <= set("=gG7")
    ):
        return True
    if len(set(body)) == 1:
        return True
    if all(ch in "-=._*gG7=" for ch in body):
        return True
    # 표 가로선: 구조 셀만으로 구성되고 동일 셀이 대부분
    from collections import Counter

    structural = set("3-=gG7.*!0j4'")
    if len(body) >= 8 and set(body) <= structural:
        counts = Counter(body)
        _most, cnt = counts.most_common(1)[0]
        if cnt / len(body) >= 0.65:
            return True
    return False


def _separator_ink(text: str) -> str:
    """구분선은 묵자에서 가로줄로 정규화."""
    return "─" * 16


def _bracket_rule_ink(text: str) -> str | None:
    """라벨 포함 위 표선 / 닫는 아래 표선을 검수용 묵자로 복원."""
    s = normalize_brf_ascii(text).strip()
    top = re.fullmatch(r"6(3{4}) +(82\S+;0) +(3+)4", s)
    if top:
        label = reverse_translate_line(top.group(2))
        return (
            "┌"
            + ("─" * len(top.group(1)))
            + f" {label} "
            + ("─" * len(top.group(3)))
            + "┐"
        )
    bottom = re.fullmatch(r"h(3{6,})j", s)
    if bottom:
        return "└" + ("─" * len(bottom.group(1))) + "┘"
    return None


def _syllable(cho: str, jung: str, jong: str = "") -> str:
    return compose_hangul(cho, jung, jong) or f"<U:syl:{cho}+{jung}+{jong}>"


def _peek(chars: list[str], i: int) -> str | None:
    if i >= len(chars):
        return None
    return _norm_cell(chars[i])


def _slice_norm(chars: list[str], i: int, length: int) -> str | None:
    if i + length > len(chars):
        return None
    return "".join(_norm_cell(chars[i + k]) for k in range(length))


def _digits_braille_to_int(cells: str) -> int | None:
    mapping = dict(zip("abcdefghij", "1234567890"))
    digits = "".join(mapping.get(c.lower(), "") for c in cells)
    return int(digits) if digits.isdigit() else None


def _unknown(cell: str) -> str:
    return f"<U:{cell}>"


def _match_punct(chars: list[str], i: int) -> tuple[str, int] | None:
    """복합 문장부호 최장 일치. (묵자, 소비 칸 수).

    `82`는 지문 범위(82#…@9#…;0)일 때만 대괄호로 보지 않는다.
    `82#c…;0` ([3점] 등)은 여는 `[` 로 처리한다.

    가운뎃점은 ``"2``(⠐⠆, 5+2-3). 구관례 ``1;``(⠂⠰)는 쓰지 않음 —
    그 셀열은 종성 ㄹ+초성 ㅊ(예: 일치)이다.

    겹받침 ``18``(ㄾ) vs 여는 대괄호 ``82``: 뒤에 ``;0`` 짝이 있으면
    종성 ㄹ + ``[`` 로 나눈다 (``…182…;0``).
    """
    for key, ink in _PUNCT_MULTI_SORTED:
        got = _slice_norm(chars, i, len(key))
        if got != key:
            continue
        if key == "82":
            rest = normalize_brf_ascii("".join(chars[i:]))
            if _PASSAGE_RANGE_ASCII.match(rest):
                continue
        # ,-:/… = ㅅ+붙임줄+모음(셨…). 밑줄 시작(,-)과 충돌하므로,
        # 바로 모음이 오고 닫는 -' 짝이 없으면 음절 조립에 맡긴다.
        if key == ",-":
            after = i + len(key)
            if _take_vowel(chars, after) is not None:
                rest = "".join(chars[after:])
                if "-'" not in normalize_brf_ascii(rest):
                    continue
        return ink, len(key)
    return None


def _try_math_op(chars: list[str], i: int, out: list[str]) -> int | None:
    """수표(#) + 수식 본문 → + − × ÷ = <> ₩ $."""
    if _norm_cell(chars[i]) != NUMBER_SIGN:
        return None
    for body, ink in MATH_OP_BODIES:
        end = i + 1 + len(body)
        if end > len(chars):
            continue
        if all(_norm_cell(chars[i + 1 + k]) == body[k] for k in range(len(body))):
            out.append(ink)
            return end
    return None


def _try_circled_digit(chars: list[str], i: int, out: list[str]) -> int | None:
    """원문자 선택지 번호·원문자 라틴·원문자 한글 음절.

    - 관례 A: 7#a7 … 7#e7 → ①…⑤ (정방향 인코딩)
    - 관례 B: #1 … #4 (⠼⠂…⠼⠲) → ①…④ (`#5`는 수식 +; ⑤는 7#e7)
    - 관례 C: 7$7 … (가–하, 라틴 1글자와 안 겹치는 본문) → ㉮…㉻
    - 관례 D: 7a7 … 7z7 → ⓐ…ⓩ (수표 없는 드러냄+글자)
    """
    # A) 7#a7
    if _slice_norm(chars, i, 2) == "7#":
        if i + 3 >= len(chars):
            return None
        dig = _norm_cell(chars[i + 2])
        if dig not in "abcde":
            return None
        if _norm_cell(chars[i + 3]) != "7":
            return None
        out.append("①②③④⑤"["abcde".index(dig)])
        return i + 4

    # C) 드러냄+한글 음절+드러냄 → ㉮…㉻ (라틴 1글자 본문은 D에 양보)
    if _norm_cell(chars[i]) == "7":
        for body, ink in _CIRCLED_HANGUL_SYL_SAFE:
            nbody = len(body)
            if i + nbody + 1 >= len(chars):
                continue
            if _slice_norm(chars, i + 1, nbody) != body:
                continue
            if _norm_cell(chars[i + 1 + nbody]) != "7":
                continue
            out.append(ink)
            return i + nbody + 2

    # D) 7a7 … 7z7 → ⓐ…ⓩ (①용 7#a7 보다 뒤에 두어 # 있는 쪽을 우선)
    if _norm_cell(chars[i]) == "7" and i + 2 < len(chars):
        mid = _norm_cell(chars[i + 1])
        if mid in "abcdefghijklmnopqrstuvwxyz" and _norm_cell(chars[i + 2]) == "7":
            out.append(
                "ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ"[
                    "abcdefghijklmnopqrstuvwxyz".index(mid)
                ]
            )
            return i + 3

    # B) #1 … #4 (수표 뒤 하부 점형 → ①…④).
    # #5 는 수식 덧셈(+); ⑤는 7#e7 관례를 쓴다.
    if _norm_cell(chars[i]) == NUMBER_SIGN and i + 1 < len(chars):
        dig = _norm_cell(chars[i + 1])
        if dig in "1234":
            out.append("①②③④"["1234".index(dig)])
            return i + 2
    return None


def _try_hide_framed(
    chars: list[str],
    i: int,
    out: list[str],
    *,
    unit: str,
    ink: str,
) -> int | None:
    """숨김/기호 표: _ + unit×n + l → ink×n."""
    if _norm_cell(chars[i]) != HIDE_MARK_OPEN:
        return None
    j = i + 1
    while j < len(chars) and _norm_cell(chars[j]) == unit:
        j += 1
    n_mid = j - (i + 1)
    if n_mid < 1:
        return None
    if j >= len(chars) or _norm_cell(chars[j]) != HIDE_MARK_CLOSE:
        return None
    out.append(ink * n_mid)
    return j + 1


def _try_hide_circles(chars: list[str], i: int, out: list[str]) -> int | None:
    """동그라미 숨김표: _ + 0×n + l → ○×n (선택지 _0 보다 긴 패턴 우선)."""
    return _try_hide_framed(
        chars, i, out, unit=HIDE_MARK_UNIT, ink="○"
    )


def _try_hide_squares(chars: list[str], i: int, out: list[str]) -> int | None:
    """네모: _ + 7×n + l → □×n."""
    return _try_hide_framed(
        chars, i, out, unit=HIDE_SQUARE_UNIT, ink="□"
    )


def _try_hide_triangle(chars: list[str], i: int, out: list[str]) -> int | None:
    """세모: _ + + + l → △."""
    return _try_hide_framed(
        chars, i, out, unit=HIDE_TRIANGLE_UNIT, ink="△"
    )


def _try_hide_x_mark(chars: list[str], i: int, out: list[str]) -> int | None:
    """가위표: _ + x + l → ✕."""
    return _try_hide_framed(
        chars, i, out, unit=HIDE_X_UNIT, ink="✕"
    )


def _try_arrow_right(chars: list[str], i: int, out: list[str]) -> int | None:
    """``_/jvl1d+_/`` (/화살표/) → →."""
    arrow = ARROW_RIGHT_BRAILLE_ASCII
    if _slice_norm(chars, i, len(arrow)) != arrow:
        return None
    out.append(ARROW_RIGHT_INK)
    return i + len(arrow)


def _try_choice_item_mark(chars: list[str], i: int, out: list[str]) -> int | None:
    """선택지 항목 표지 ⠇⠴ (_0) — 묵자에서는 생략."""
    if _slice_norm(chars, i, 2) != "_0":
        return None
    end = i + 2
    if end < len(chars) and chars[end] == " ":
        end += 1
    # ①_0한글 → ① 한글
    if out and out[-1] in "①②③④⑤":
        out.append(" ")
    return end


def _hangul_particle_len(chars: list[str], i: int) -> int:
    """조사로 확정 가능한 접두 길이. 영단어(On 등)와 겹치면 0."""
    forms = ("cz", "v", "w", "n", "z", "!", "$")
    for form in forms:
        if _slice_norm(chars, i, len(form)) != form:
            continue
        after_i = i + len(form)
        if after_i < len(chars) and chars[after_i] != " ":
            an = _peek(chars, after_i)
            if an in _LATIN_LETTERS or an == ",":
                continue  # On, and, …
            if _match_punct(chars, after_i):
                return len(form)
            # 한글 음절 시작 등이면 조사로 인정
            if an is not None and an not in _LATIN_LETTERS:
                return len(form)
            continue
        return len(form)
    return 0


def _starts_closing_multi(chars: list[str], i: int) -> bool:
    for pref in _CLOSING_MULTI_PREFIXES:
        got = _slice_norm(chars, i, len(pref))
        if got == pref:
            return True
    return False


def _has_closing_square_ahead(chars: list[str], start: int) -> bool:
    """``start`` 이후에 닫는 대괄호 ``;0`` 이 있는지."""
    j = max(start, 0)
    while j + 1 < len(chars):
        if _slice_norm(chars, j, 2) == ";0":
            return True
        j += 1
    return False


def _opens_square_bracket(chars: list[str], i: int) -> bool:
    """여는 대괄호 ``82`` (지문 범위 82#…;0 제외)."""
    if _slice_norm(chars, i, 2) != "82":
        return False
    rest = normalize_brf_ascii("".join(chars[i:]))
    return not _PASSAGE_RANGE_ASCII.match(rest)


def _take_vowel(chars: list[str], i: int) -> tuple[str, int] | None:
    if i >= len(chars):
        return None
    if i + 1 < len(chars):
        dig = _norm_cell(chars[i]) + _norm_cell(chars[i + 1])
        if dig in JUNGSEONG_DIGRAPHS:
            return JUNGSEONG_DIGRAPHS[dig], i + 2
    n = _norm_cell(chars[i])
    if n in JUNGSEONG:
        return JUNGSEONG[n], i + 1
    return None


def _prev_suggests_hangul_indicator(out: list[str]) -> bool:
    """바로 앞 묵자가 로마자·원문자·숫자 등이면 한글표 문맥."""
    for ink in reversed(out):
        if not ink or ink.isspace():
            continue
        return ink[-1] in _HANGUL_INDICATOR_PREV
    return False


def _hangul_can_start_at(chars: list[str], i: int) -> bool:
    """한글표 뒤에 올 수 있는 한글 시작 여부 (모음·초성·약자·온표 등)."""
    if i >= len(chars):
        return False
    n = _norm_cell(chars[i])
    if n in JUNGSEONG or n in JUNGSEONG_DIGRAPHS:
        return True
    if i + 1 < len(chars):
        dig = n + _norm_cell(chars[i + 1])
        if dig in JUNGSEONG_DIGRAPHS:
            return True
    if n in CHOSEONG or n in ABBREV_CV or n in ABBREV_VC:
        return True
    if n == TENSED_PREFIX or n == ON_SIGN or n == CHOSEONG_IEUNG:
        return True
    return False


def _try_hangul_indicator(chars: list[str], i: int, out: list[str]) -> int | None:
    """2024 제39항 한글표 ``,-`` (⠠⠤). 로마자 등 뒤에 한글이 이어질 때 경계.

    강조 밑줄 시작(``,-`` … ``-'``)과 동일 셀열이라, 닫는 ``-'`` 짝이 없고
    직전 묵자가 로마/원문자 계열이며 뒤에 한글이 시작되면 표지만 소비한다.
    """
    if _slice_norm(chars, i, 2) != ",-":
        return None
    after = i + 2
    rest = normalize_brf_ascii("".join(chars[after:]))
    if "-'" in rest:
        return None
    if not _prev_suggests_hangul_indicator(out):
        return None
    if not _hangul_can_start_at(chars, after):
        return None
    return after


def _take_final(
    chars: list[str],
    i: int,
    *,
    skip_jong: frozenset[str] | None = None,
    out: list[str] | None = None,
    cho: str | None = None,
    jung: str | None = None,
) -> tuple[str, int, bool] | None:
    """(종성 또는 문장부호, 새 인덱스, 문장부호 여부).

    닫는 복합 부호 시작이면 종성으로 가져가지 않는다.
    skip_jong: 드러냄표(7) 등 종성으로 쓰지 않을 셀.

    종성 ㅍ과 마침표는 동일 셀(ASCII ``4``):
      - 점역: 두 음절 이하 어절 뒤 마침표 앞에 공백을 넣음
      - 역점역: 공백·EOL·밑줄·닫는부호 앞에서,
                짧은 어절(완성 중 포함 ≤2음절) 뒤 ``4`` → 종성 ㅍ,
                세 음절 이상 어절 뒤 ``4`` → 마침표

    종성 ㅌ과 물음표는 동일 셀(ASCII ``8``):
      - 점역: 두 음절 이하 어절 뒤 물음표 앞에 공백
      - 역점역: 공백·EOL·밑줄·닫는부호 앞에서,
                짧은 어절(완성 중 포함 ≤2음절) 뒤 ``8`` → 종성 ㅌ,
                세 음절 이상 어절 뒤 ``8`` → 물음표
                (``햇볕`` ``jr'^:8`` → 밭/끝과 같이 ㅌ; ``벼?`` 아님)

    종성 ㅋ과 느낌표는 동일 셀(ASCII ``6``):
      - 점역: 두 음절 이하 어절 뒤 느낌표 앞에 공백
      - 역점역: 공백·EOL·밑줄·닫는부호 앞에서,
                짧은 어절(완성 중 포함 ≤2음절) 뒤 ``6`` → 종성 ㅋ,
                세 음절 이상 어절 뒤 ``6`` → 느낌표
    """
    if i >= len(chars):
        return None
    if _starts_closing_multi(chars, i):
        return None
    # 회( → jy8' 에서 8을 종성 ㅌ으로 먹으면 안 됨. 8' = (
    if _match_punct(chars, i) is not None:
        return None

    n = _norm_cell(chars[i])
    if skip_jong and n in skip_jong:
        return None
    nxt = _peek(chars, i + 1)

    if nxt is not None and (n + nxt) in JONGSEONG_DIGRAPHS:
        # 겹받침 vs 종성+닫는부호: 둘째 칸이 닫는 복합 시작이면 보통 포기
        # (만”=e300 → 종성 ㄴ + 00).
        # 다만 겹받침을 취한 뒤에도 닫는 복합이 되면 겹받침 우선
        # (많’=e300' → 30 + 0', 00에 가로채지 않음).
        # 겹받침 18(ㄾ) vs 여는 대괄호 82: 뒤에 ;0 짝이 있으면 대괄호 우선
        closing_at_second = _starts_closing_multi(chars, i + 1)
        closing_after_digraph = _starts_closing_multi(chars, i + 2)
        square_steal = _opens_square_bracket(chars, i + 1) and _has_closing_square_ahead(
            chars, i + 3
        )
        if not square_steal and (
            not closing_at_second or closing_after_digraph
        ):
            return JONGSEONG_DIGRAPHS[n + nxt], i + 2, False

    # 마침표(4) ↔ 종성 ㅍ(4) — 어절 음절 수로 구분
    if n == "4" and _is_period_disambig_boundary(chars, i + 1):
        # +1: 지금 조립 중인 음절
        word_syl = _out_word_hangul_count(out) + 1
        if word_syl <= _JONG_PUNCT_DISAMBIG_MAX_SYL:
            return JONGSEONG["4"], i + 1, False
        return ".", i + 1, True

    # 물음표(8) ↔ 종성 ㅌ(8) — 어절 음절 수로 구분 (ㅍ/마침표와 동일)
    if n == "8" and _is_period_disambig_boundary(chars, i + 1):
        word_syl = _out_word_hangul_count(out) + 1
        if word_syl <= _JONG_PUNCT_DISAMBIG_MAX_SYL:
            return JONGSEONG["8"], i + 1, False
        return "?", i + 1, True

    # 느낌표(6) ↔ 종성 ㅋ(6) — 어절 음절 수로 구분 (마침표/ㅍ와 동일)
    if n == "6" and _is_period_disambig_boundary(chars, i + 1):
        word_syl = _out_word_hangul_count(out) + 1
        if word_syl <= _JONG_PUNCT_DISAMBIG_MAX_SYL:
            return JONGSEONG["6"], i + 1, False
        return "!", i + 1, True

    # 종성 ㅎ(0) — 다음에 닫는 따옴표 2칸이 오면 종성 아님(위에서 처리)
    # 단독 0 뒤가 경계이고 직전이 모음 음절이면 종성 ㅎ 가능
    # 종성 ㅇ(7) ↔ 드러냄+온표자모(7=…7): 표지 패턴이면 종성으로 쓰지 않음
    if n == "7" and _match_emph_on_jamo(chars, i) is not None:
        return None
    # 가·나·다…(ㅏ 계열 약자 음절) 뒤 77=…7 은 강·난…보다 가+선택지 표지로 본다
    # (참고 BRF 전위·압축). 텅(hs77…) 등 비-ㅏ 음절은 첫 7을 종성 ㅇ으로 유지.
    if (
        n == "7"
        and cho is not None
        and jung is not None
        and (cho, jung) in ABBREV_CV.values()
        and _peek(chars, i + 1) == "7"
        and _match_emph_on_jamo(chars, i + 1) is not None
    ):
        return None
    if n in JONGSEONG:
        return JONGSEONG[n], i + 1, False
    return None


def _can_begin_syllable(cell: str | None) -> bool:
    """이 셀이 새 음절 시작(초성·약자·모음·된소리표)이 될 수 있는지."""
    if cell is None:
        return False
    return (
        cell in CHOSEONG
        or cell in ABBREV_CV
        or cell in ABBREV_VC
        or cell in JUNGSEONG
        or cell in {k[0] for k in JUNGSEONG_DIGRAPHS}
        or cell == TENSED_PREFIX
        or cell == ON_SIGN
        or cell == NUMBER_SIGN
    )


def _jong_cell_can_be_reanalyzed_as_onset(cell: str) -> bool:
    """종성으로 읽은 셀을 다음 음절 초성으로 재해석할지.

    한국 점자는 초성·종성 점형이 대체로 다르며, `/` 는 종성 ㅆ과 중성 ㅖ가
    겹친다. 모음 뒤 `/` 는 였/었의 받침 ㅆ으로 유지해야 한다.
    """
    if cell == "/":
        return False
    # 종성 전용 셀은 재해석하지 않음. 초성·가류 약자와 겹치는 경우만.
    return cell in CHOSEONG or cell in ABBREV_CV or cell == TENSED_PREFIX


def _emit_syllable_with_optional_final(
    out: list[str],
    chars: list[str],
    cho: str,
    jung: str,
    i_after_vowel: int,
    *,
    skip_jong: frozenset[str] | None = None,
) -> int:
    # 종성 ㅇ과 드러냄 표지 7이 한 칸으로 압축된 경우(…hs7=37…, 뒤 음절 이어짐)
    emph = _match_emph_on_jamo(chars, i_after_vowel)
    if emph is not None:
        mark, end = emph
        after = _peek(chars, end)
        if after is not None and _can_begin_syllable(after):
            out.append(_syllable(cho, jung, "ㅇ"))
            out.append(mark)
            return end

    final = _take_final(
        chars, i_after_vowel, skip_jong=skip_jong, out=out, cho=cho, jung=jung
    )
    if final is None:
        out.append(_syllable(cho, jung))
        return i_after_vowel
    text, new_i, is_punct = final
    if is_punct:
        out.append(_syllable(cho, jung))
        out.append(text)
        return new_i
    # 종성 전용 셀은 다음 모음과 무관하게 받침 유지
    final_cell = _norm_cell(chars[i_after_vowel])
    after = _peek(chars, new_i)
    if (
        _jong_cell_can_be_reanalyzed_as_onset(final_cell)
        and after is not None
        and (
            after in JUNGSEONG
            or after in ABBREV_VC
            or after in ABBREV_CV
            or after in JONGSEONG
            or after in {k[0] for k in JUNGSEONG_DIGRAPHS}
            or after == TENSED_PREFIX
        )
    ):
        out.append(_syllable(cho, jung))
        return i_after_vowel
    out.append(_syllable(cho, jung, text))
    return new_i


def _emit_abbrev_cv(
    out: list[str],
    chars: list[str],
    cell: str,
    i: int,
    *,
    skip_jong: frozenset[str] | None = None,
) -> int:
    cho, jung = ABBREV_CV[cell]
    final = _take_final(
        chars, i + 1, skip_jong=skip_jong, out=out, cho=cho, jung=jung
    )
    if final is None:
        out.append(_syllable(cho, jung))
        return i + 1
    text, new_i, is_punct = final
    if is_punct:
        out.append(_syllable(cho, jung))
        out.append(text)
        return new_i
    final_cell = _norm_cell(chars[i + 1])
    after = _peek(chars, new_i)
    if (
        _jong_cell_can_be_reanalyzed_as_onset(final_cell)
        and after is not None
        and (
            after in JUNGSEONG
            or after in ABBREV_VC
            or after in ABBREV_CV
            or after in JONGSEONG
            or after in {k[0] for k in JUNGSEONG_DIGRAPHS}
            or after == TENSED_PREFIX
        )
    ):
        out.append(_syllable(cho, jung))
        return i + 1
    out.append(_syllable(cho, jung, text))
    return new_i


def _on_sign_after_ok(chars: list[str], after_i: int) -> bool:
    """온표 자모 본문 직후가 경계·다음 온표·닫는부호·구두점이면 온표로 인정.

    직후가 **모음·VC 약자**로 음절을 시작하면 온표가 아니다
    (``옹호`` ``=ju`` → ``ㅎ오`` 오인 방지). 초성·가류 약자 등 다음 음절은
    온표로 본다 (``‘ㄴ, ㄹ’`` 의 ``=3"`` — 쉼표 셀이 초성처럼 보여도
    구두점·다음 자모 경계로 처리).
    """
    after = _peek(chars, after_i)
    if _is_boundary(after) or after == ON_SIGN or after == "7":
        return True
    if after is not None and after in PUNCT_SINGLE:
        return True
    if _starts_closing_multi(chars, after_i):
        return True
    if after is not None and _match_punct(chars, after_i) is not None:
        return True
    # 모음이 바로 이어지면 옹 약자(+다음 음절) 우선
    if after is not None and (
        after in JUNGSEONG
        or after in ABBREV_VC
        or after in {k[0] for k in JUNGSEONG_DIGRAPHS}
    ):
        return False
    if after is not None and _can_begin_syllable(after):
        return True
    return False


def _match_on_sign_body(chars: list[str], i: int) -> tuple[str, int] | None:
    """chars[i]==온표일 때 본문 최장 일치 → (자모, 다음 인덱스)."""
    if _norm_cell(chars[i]) != ON_SIGN or i + 1 >= len(chars):
        return None
    for body, jamo in ON_SIGN_BODIES:
        end = i + 1 + len(body)
        if end > len(chars):
            continue
        if any(_norm_cell(chars[i + 1 + k]) != body[k] for k in range(len(body))):
            continue
        if not _on_sign_after_ok(chars, end):
            continue
        return jamo, end
    return None


def _match_emph_on_jamo(chars: list[str], i: int) -> tuple[str, int] | None:
    """드러냄+온표 자모+드러냄 ``7=…7`` → (``‘ㄱ’``, 끝 인덱스).

    ㉠ 등 원문자 점열이 이 형태로 오면 선택지 관례 ``‘ㄱ’`` 로 복원한다.
    """
    if i >= len(chars) or _norm_cell(chars[i]) != "7":
        return None
    if i + 1 >= len(chars) or _norm_cell(chars[i + 1]) != ON_SIGN:
        return None
    matched = _match_on_sign_body(chars, i + 1)
    if matched is None:
        return None
    jamo, after_body = matched
    if after_body >= len(chars) or _norm_cell(chars[after_body]) != "7":
        return None
    return f"‘{jamo}’", after_body + 1


def _try_emph_on_jamo(chars: list[str], i: int, out: list[str]) -> int | None:
    matched = _match_emph_on_jamo(chars, i)
    if matched is None:
        return None
    ink, end = matched
    out.append(ink)
    return end


def _try_on_sign(chars: list[str], i: int, out: list[str]) -> int | None:
    """온표(=) + 단독 자모. 옹 약자와 동일 셀이므로 문맥으로 구분.

    본문은 JAMO_COMPAT 역매핑 최장 일치(ㅇ·된소리·이중모음·겹받침).
    본문 뒤가 경계·닫는부호·다음 온표이면 온표로 본다.
    """
    matched = _match_on_sign_body(chars, i)
    if matched is None:
        return None
    jamo, end = matched
    out.append(jamo)
    return end


def _try_standalone_rieul_period(
    chars: list[str], i: int, out: list[str]
) -> int | None:
    """음절 밖 단독 ⠂⠲(14) → ㄹ. (겹받침 ㄿ이 아님)."""
    if _norm_cell(chars[i]) != "1":
        return None
    if _peek(chars, i + 1) != "4":
        return None
    out.append("ㄹ.")
    return i + 2


def _try_skip_decorative_run(chars: list[str], i: int) -> int | None:
    """행 중간 장식/표선 반복 셀 건너뛰기 (ggg…, 333…)."""
    if i >= len(chars):
        return None
    cell = _norm_cell(chars[i])
    if cell not in set("3g7=*"):
        return None
    j = i
    while j < len(chars) and _norm_cell(chars[j]) == cell:
        j += 1
    if j - i >= 6:
        return j
    return None


def _try_passage_range(chars: list[str], i: int, out: list[str]) -> int | None:
    """지문/숫자 범위 부호.

    - 82#a`9#c;0 → [1~3]
    - #aj@9#ae → 10~15  (본문 중 범위)
    """
    rest = normalize_brf_ascii("".join(chars[i:]))
    m = _PASSAGE_RANGE_ASCII.match(rest)
    if m:
        a = _digits_braille_to_int(m.group(1))
        b = _digits_braille_to_int(m.group(2))
        if a is not None and b is not None:
            text = f"[{a}~{b}]"
            if m.group(3):
                text += "."
            out.append(text)
            return i + len(m.group(0))

    m2 = _NUM_RANGE_ASCII.match(rest)
    if m2:
        a = _digits_braille_to_int(m2.group(1))
        b = _digits_braille_to_int(m2.group(2))
        if a is not None and b is not None:
            out.append(f"{a}~{b}")
            return i + len(m2.group(0))
    return None


def _try_roman_mode(chars: list[str], i: int, out: list[str]) -> int | None:
    """로마자표(0) 이후 영문 구간.

    - `,` = 다음 1글자 대문자
    - `,,` = 단어 대문자(공백·구두점 전까지)
    - 공백·(,)|,. 등은 ENG 유지 (뒤에 로마자표/글자가 이어질 때)
    - 대문자 약어 직후 한글 조사 셀은 ENG 종료(출력 없음)
    - 로마자종료표(4/⠲)는 마침표로 내보내지 않고 모드만 종료
    """
    if _norm_cell(chars[i]) != ROMAN_SIGN:
        return None
    if i + 1 >= len(chars):
        return None
    nxt = _norm_cell(chars[i + 1])
    if nxt != "," and nxt not in _LATIN_LETTERS:
        return None

    i += 1  # consume roman sign (no output)
    capital_next = False
    caps_word = False
    all_caps_letters = True
    letters_emitted = 0

    while i < len(chars):
        ch = chars[i]
        n = _norm_cell(ch)

        if ch == " ":
            # 뒤가 또 영문(로마자표 또는 글자)이면 공백 유지
            j = i + 1
            if j < len(chars) and (
                _norm_cell(chars[j]) == ROMAN_SIGN
                or _norm_cell(chars[j]) == ","
                or _norm_cell(chars[j]) in _LATIN_LETTERS
            ):
                out.append(" ")
                caps_word = False
                capital_next = False
                all_caps_letters = True
                letters_emitted = 0
                i += 1
                # 새 단어가 로마자표로 시작하면 표만 소비
                if i < len(chars) and _norm_cell(chars[i]) == ROMAN_SIGN:
                    peek = _peek(chars, i + 1)
                    if peek == "," or peek in _LATIN_LETTERS:
                        i += 1
                continue
            break

        # 복합 구두점 (괄호 등) — ENG 안에서 허용
        punct = _match_punct(chars, i)
        if punct:
            ink, ncons = punct
            if ink:
                out.append(ink)
            caps_word = False
            capital_next = False
            all_caps_letters = True
            letters_emitted = 0
            i += ncons
            # 닫는 대괄호/소괄호 뒤는 로마자 구간 종료
            if ink in {"]", ")"}:
                break
            continue

        # 레거시: 소괄호를 '-' 한 칸으로 쓴 경우
        if n == "-" and letters_emitted > 0:
            # 뒤에 로마자/글자가 오면 '(' , 아니면 이미 eng 끝 근처면 ')'
            after = _peek(chars, i + 1)
            if after == ROMAN_SIGN or after in _LATIN_LETTERS or after == ",":
                out.append("(")
            else:
                out.append(")")
            i += 1
            caps_word = False
            capital_next = False
            letters_emitted = 0
            if out[-1] == ")":
                break
            continue

        # 단어 대문자표 ,,
        if n == "," and i + 1 < len(chars) and _norm_cell(chars[i + 1]) == ",":
            caps_word = True
            capital_next = False
            i += 2
            continue

        # 단일 대문자표
        if n == ",":
            capital_next = True
            i += 1
            continue

        if n in _LATIN_LETTERS:
            plen = _hangul_particle_len(chars, i)
            if (
                plen
                and all_caps_letters
                and not capital_next
                and not caps_word
                and (
                    letters_emitted >= 2
                    or (letters_emitted == 1 and n in {"v", "w"})
                )
            ):
                break
            upper = capital_next or caps_word
            out.append(n.upper() if upper else n)
            if not upper:
                all_caps_letters = False
            capital_next = False
            letters_emitted += 1
            i += 1
            continue

        # 로마자종료표(⠲) — 마침표(동일 셀)로 출력하지 않음
        if n == ROMAN_END_SIGN:
            i += 1
            break

        # 단순 영문 구두점
        if n in PUNCT_SINGLE and n in {"1", "8", "6"}:
            # 쉼표는 “ 셀과 충돌 — eng에서는 1
            if n == "1":
                out.append(",")
                i += 1
                continue
            # 8/? 는 eng 질의에만 — 기본적으로 종료
            break

        # 그 외(한글 음절 시작 등) — 모드 종료, 셀은 남김
        break

    return i


def reverse_translate_line(raw_ascii: str) -> str:
    text = normalize_brf_ascii(raw_ascii)
    if text.strip() == FIGURE_BRAILLE_ASCII:
        return FIGURE_INK
    if text.strip() == PLOT_SUMMARY_END_BRAILLE_ASCII:
        return PLOT_SUMMARY_END_INK
    bracket_rule = _bracket_rule_ink(text)
    if bracket_rule is not None:
        return bracket_rule
    if _is_separator_line(text):
        return _separator_ink(text)

    chars = list(text)
    i = 0
    out: list[str] = []
    # 직전 출력이 여는 따옴표/낫표면 온표 해석을 우선
    open_quote_depth = 0
    emph_open = False

    while i < len(chars):
        ch = chars[i]
        n = _norm_cell(ch)
        skip_jong = frozenset({"7"}) if emph_open else None

        if ch == " ":
            out.append(" ")
            i += 1
            continue

        # 1) 지문 범위 복합 부호
        jumped = _try_passage_range(chars, i, out)
        if jumped is not None:
            i = jumped
            continue

        # 1b0) 수표+수식 (#5→+, #33→= …) — 원문자 #1…#5 보다 먼저
        jumped = _try_math_op(chars, i, out)
        if jumped is not None:
            i = jumped
            continue

        # 1b) 원문자 선택지 번호
        jumped = _try_circled_digit(chars, i, out)
        if jumped is not None:
            i = jumped
            continue

        # 1b2) 숨김/기호 표 (_0…0l, _7…7l, _+l, _xl) — 선택지 _0 보다 먼저
        jumped = None
        for _try_hide in (
            _try_hide_circles,
            _try_hide_squares,
            _try_hide_triangle,
            _try_hide_x_mark,
        ):
            jumped = _try_hide(chars, i, out)
            if jumped is not None:
                i = jumped
                break
        if jumped is not None:
            continue

        # 1b3) 오른쪽 화살표 (/화살표/)
        jumped = _try_arrow_right(chars, i, out)
        if jumped is not None:
            i = jumped
            continue

        # 1c) 선택지 항목 표지 _0 (⠇⠴)
        jumped = _try_choice_item_mark(chars, i, out)
        if jumped is not None:
            i = jumped
            continue

        # 1d) 장식/표선 반복
        jumped = _try_skip_decorative_run(chars, i)
        if jumped is not None:
            i = jumped
            continue

        # 2) 대괄호 우선 (;0 / 82) — 다른 복합부호보다 먼저 닫는 ] 확보
        if _slice_norm(chars, i, 2) == ";0":
            out.append("]")
            i += 2
            continue
        if _slice_norm(chars, i, 2) == "82":
            rest = normalize_brf_ascii("".join(chars[i:]))
            if not _PASSAGE_RANGE_ASCII.match(rest):
                out.append("[")
                i += 2
                continue

        # 2a) 제39항 한글표 ,- (강조 ,-…-' 보다 앞 — 짝 없을 때만)
        jumped = _try_hangul_indicator(chars, i, out)
        if jumped is not None:
            i = jumped
            continue

        # 2b) 복합 문장부호 최장 일치
        punct = _match_punct(chars, i)
        if punct:
            ink, ncons = punct
            if ink:
                out.append(ink)
            if ink in {"‘", "“", "『", "「"}:
                open_quote_depth += 1
            elif ink in {"’", "”", "』", "」"} and open_quote_depth > 0:
                open_quote_depth -= 1
            i += ncons
            continue

        # 로마자표(0) 없는 라틴 모양 셀은 한글 약자·자모로 본다.
        # 원문 로마자 z 는 정방향이 0z 로 넣는다 (‘은’=z 와 구분).

        # 3) 온표 + 단독 자모 (종성/초성/모음 본문, 닫는따옴표 보호)
        if n == ON_SIGN:
            jumped = _try_on_sign(chars, i, out)
            if jumped is not None:
                i = jumped
                continue
            # else: fall through → 옹 약자

        # 3b) 드러냄+온표 자모(7=…7) — 종성 ㅇ보다 표지 우선
        jumped = _try_emph_on_jamo(chars, i, out)
        if jumped is not None:
            i = jumped
            continue

        # 3c) 드러냄표 ⠶(7) … 7 — 종성 ㅇ으로 붙지 못한 위치
        if n == "7":
            # 여분의 7 + 7=…7 (압축·전위된 드러냄) → 한 칸 건너뛰기
            if (
                not emph_open
                and _peek(chars, i + 1) == "7"
                and _match_emph_on_jamo(chars, i + 1) is not None
            ):
                i += 1
                continue
            if emph_open:
                out.append("’")
                emph_open = False
            else:
                out.append("‘")
                emph_open = True
            i += 1
            continue

        # 4) 숫자
        if n == NUMBER_SIGN:
            i += 1
            digits: list[str] = []
            while i < len(chars) and _norm_cell(chars[i]) in NUMBER_MAP:
                digits.append(NUMBER_MAP[_norm_cell(chars[i])])
                i += 1
            out.append("".join(digits) if digits else "#")
            continue

        # 5) 영문 (로마자표 상태 기계)
        jumped = _try_roman_mode(chars, i, out)
        if jumped is not None:
            i = jumped
            continue

        # 레거시 ;,X 영문
        if n == LETTER_SIGN and i + 1 < len(chars) and _norm_cell(chars[i + 1]) == ",":
            if i + 2 < len(chars) and _norm_cell(chars[i + 2]) in _LATIN_LETTERS:
                # 로마자표 없이도 ;, 형태면 동일 엔진에 맡기기 위해 0 삽입 흉내
                # → 간단히 한 글자씩
                i += 1
                capital = False
                while i < len(chars) and chars[i] != " ":
                    cn = _norm_cell(chars[i])
                    if cn == ",":
                        capital = True
                        i += 1
                        continue
                    if cn in _LATIN_LETTERS:
                        out.append(cn.upper() if capital else cn)
                        capital = False
                        i += 1
                        continue
                    break
                continue

        # 6) 단어 약어
        if i + 1 < len(chars):
            two = n + _norm_cell(chars[i + 1])
            if two in WORD_ABBREV:
                out.append(WORD_ABBREV[two])
                i += 2
                continue
            if two == ABBREV_GEOT:
                out.append("것")
                i += 2
                continue

        # 7) 된소리 초성
        if n == TENSED_PREFIX and i + 1 < len(chars):
            body = _norm_cell(chars[i + 1])
            # 된소리 + 가약자($) → 까 (ㄲ+ㅏ) — ,@ 대신 쓰인 경우
            if body == "$":
                j = i + 2
                # 중복 표기된 ㅏ(<) 건너뛰기
                if _peek(chars, j) == "<":
                    j += 1
                i = _emit_syllable_with_optional_final(
                    out, chars, "ㄲ", "ㅏ", j, skip_jong=skip_jong
                )
                continue
            if body in TENSED_MAP:
                cho = TENSED_MAP[body]
                j = i + 2
                nxt = _peek(chars, j)
                if nxt == "]" and cho in YEONG_ONSET_OVERRIDE:
                    out.append(YEONG_ONSET_OVERRIDE[cho])
                    i = j + 1
                    continue
                if nxt in ABBREV_VC:
                    jung, jong = ABBREV_VC[nxt]
                    out.append(_syllable(cho, jung, jong))
                    i = j + 1
                    continue
                vowel = _take_vowel(chars, j)
                if vowel:
                    jung, k = vowel
                    i = _emit_syllable_with_optional_final(
                        out, chars, cho, jung, k, skip_jong=skip_jong
                    )
                    continue
                # 된소리 초성 뒤 모음이 없으면 가류처럼 암시 ㅏ
                i = _emit_syllable_with_optional_final(
                    out, chars, cho, "ㅏ", j, skip_jong=skip_jong
                )
                continue

        # 8) 초성 + VC 약자
        if n in CHOSEONG and i + 1 < len(chars) and _norm_cell(chars[i + 1]) in ABBREV_VC:
            cho = CHOSEONG[n]
            vc = _norm_cell(chars[i + 1])
            if vc == "]" and cho in YEONG_ONSET_OVERRIDE:
                out.append(YEONG_ONSET_OVERRIDE[cho])
            else:
                jung, jong = ABBREV_VC[vc]
                out.append(_syllable(cho, jung, jong))
            i += 2
            continue

        # 9) VC 약자 (초성 ㅇ) — 온표가 아닌 =
        if n in ABBREV_VC:
            jung, jong = ABBREV_VC[n]
            out.append(_syllable("ㅇ", jung, jong))
            i += 1
            continue

        # 10) 초성 + 모음 / CV 약자
        # 붙임줄(-): 초성셀+붙임+모음(+받침) → 혔/졌… (하+였 j:/ 과 구분)
        if n in CHOSEONG and _peek(chars, i + 1) == "-":
            vowel = _take_vowel(chars, i + 2)
            if vowel:
                jung, k = vowel
                cho = CHOSEONG[n]
                i = _emit_syllable_with_optional_final(
                    out, chars, cho, jung, k, skip_jong=skip_jong
                )
                continue
        # 하(j)+였/었(:/ 또는 s/) → 하였/하었. 자(.)+ㅕ+ㅆ → 졌 (자였 아님).
        if n in CHOSEONG:
            cho = CHOSEONG[n]
            vowel = _take_vowel(chars, i + 1)
            if vowel and n == "j":
                jung, k = vowel
                if jung in {"ㅕ", "ㅓ"} and _peek(chars, k) == "/":
                    out.append(_syllable("ㅎ", "ㅏ"))
                    i = _emit_syllable_with_optional_final(
                        out, chars, "ㅇ", jung, k, skip_jong=skip_jong
                    )
                    continue
            if vowel:
                jung, k = vowel
                i = _emit_syllable_with_optional_final(
                    out, chars, cho, jung, k, skip_jong=skip_jong
                )
                continue
            if n in ABBREV_CV:
                i = _emit_abbrev_cv(out, chars, n, i, skip_jong=skip_jong)
                continue
            # ㄹ(“)은 쉼표(⠐)와 동일 셀 — 뒤에 음절이 이어지지 않으면 쉼표
            if n == '"':
                out.append(",")
                i += 1
                continue
            out.append(_unknown(n))
            i += 1
            continue

        if n in ABBREV_CV:
            i = _emit_abbrev_cv(out, chars, n, i, skip_jong=skip_jong)
            continue

        # 11) 중성만 (초성 ㅇ 생략) — 온표가 없을 때 ‘아’
        vowel = _take_vowel(chars, i)
        if vowel:
            jung, k = vowel
            i = _emit_syllable_with_optional_final(
                out, chars, "ㅇ", jung, k, skip_jong=skip_jong
            )
            continue

        # 12) 음절 밖 단독 ⠂⠲ → ㄹ. (쉼표+마침표·ㄿ 아님)
        jumped = _try_standalone_rieul_period(chars, i, out)
        if jumped is not None:
            i = jumped
            continue

        # 13) 1칸 구두점
        if n in PUNCT_SINGLE:
            # 8: 문장 끝·닫는부호 앞이면 물음표 (점역 공백 구분용 스페이스 제거)
            if n == "8" and _is_period_disambig_boundary(chars, i + 1):
                if out and out[-1] == " ":
                    out.pop()
                out.append("?")
                i += 1
                continue
            # 8: 문장 중간·뒤에 한글이 이어지면 여는 “ 로 보는 편이 나을 수 있음
            if n == "8" and i + 1 < len(chars) and chars[i + 1] != " ":
                nxt = _peek(chars, i + 1)
                if nxt and (
                    nxt in CHOSEONG
                    or nxt in JUNGSEONG
                    or nxt in ABBREV_CV
                    or nxt in ABBREV_VC
                    or nxt == ON_SIGN
                ):
                    out.append("“")
                    open_quote_depth += 1
                    i += 1
                    continue
            # 마침표·느낌표 앞 공백은 종성 구분용 → 묵자에서는 제거
            if n in ("4", "6") and out and out[-1] == " ":
                out.pop()
            out.append(PUNCT_SINGLE[n])
            i += 1
            continue

        # 닫는 큰따옴표 후보: 단독 0 + 경계 (종성 ㅎ이 아닌 경우)
        if n == "0" and _is_boundary(_peek(chars, i + 1)):
            # 직전 출력이 한글·따옴표 내용이면 ” 가능. 다만 종성 ㅎ 음절도 많음.
            # open_quote_depth가 있으면 닫는 따옴표 우선
            if open_quote_depth > 0:
                out.append("”")
                open_quote_depth -= 1
                i += 1
                continue

        out.append(_unknown(ch if ch.strip() else n))
        i += 1

    return "".join(out)
