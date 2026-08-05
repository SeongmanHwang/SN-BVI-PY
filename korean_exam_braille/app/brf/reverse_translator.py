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
from korean_exam_braille.app.brf.korean_tables import (
    ABBREV_CV,
    ABBREV_GEOT,
    ABBREV_VC,
    CHOSEONG,
    JONGSEONG,
    JONGSEONG_DIGRAPHS,
    JUNGSEONG,
    JUNGSEONG_DIGRAPHS,
    LETTER_SIGN,
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

# 최장 일치용 정렬
_PUNCT_MULTI_SORTED: list[tuple[str, str]] = sorted(
    PUNCT_MULTI.items(), key=lambda kv: -len(kv[0])
)

# 종성으로 붙이면 안 되는 닫는 복합 부호 접두 (2칸+)
_CLOSING_MULTI_PREFIXES = frozenset(
    k
    for k, v in PUNCT_MULTI.items()
    if v in {"’", "”", "』", "」", ")", "}", "]", "〉", "》", ">"}
) | frozenset({"0'", "02", "01", "00", ",0", "07", ";0"})

_LATIN_LETTERS = frozenset("abcdefghijklmnopqrstuvwxyz")

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
    """
    for key, ink in _PUNCT_MULTI_SORTED:
        got = _slice_norm(chars, i, len(key))
        if got != key:
            continue
        if key == "82":
            rest = normalize_brf_ascii("".join(chars[i:]))
            if _PASSAGE_RANGE_ASCII.match(rest):
                continue
        return ink, len(key)
    return None


def _try_circled_digit(chars: list[str], i: int, out: list[str]) -> int | None:
    """원문자 선택지 번호.

    - 관례 A: 7#a7 … 7#e7 → ①…⑤ (정방향 인코딩)
    - 관례 B: #1 … #5 (⠼⠂…⠼⠢) → ①…⑤ (참고 시험지 BRF)
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

    # B) #1 … #5 (수표 뒤 하부 점형 — 일반 숫자 a–j 와 구분)
    if _norm_cell(chars[i]) == NUMBER_SIGN and i + 1 < len(chars):
        dig = _norm_cell(chars[i + 1])
        if dig in "12345":
            out.append("①②③④⑤"["12345".index(dig)])
            return i + 2
    return None


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


def _take_final(
    chars: list[str],
    i: int,
    *,
    skip_jong: frozenset[str] | None = None,
) -> tuple[str, int, bool] | None:
    """(종성 또는 문장부호, 새 인덱스, 문장부호 여부).

    닫는 복합 부호 시작이면 종성으로 가져가지 않는다.
    skip_jong: 드러냄표(7) 등 종성으로 쓰지 않을 셀.
    """
    if i >= len(chars):
        return None
    if _starts_closing_multi(chars, i):
        return None

    n = _norm_cell(chars[i])
    if skip_jong and n in skip_jong:
        return None
    nxt = _peek(chars, i + 1)

    if nxt is not None and (n + nxt) in JONGSEONG_DIGRAPHS:
        # 겹받침 vs 종성+닫는부호: 두 칸이 닫는 복합이면 포기
        if not _starts_closing_multi(chars, i + 1):
            return JONGSEONG_DIGRAPHS[n + nxt], i + 2, False

    # 문장 끝 구두점 (종성과 동일 셀) — 다음이 경계일 때만
    if n in PUNCT_SINGLE and n in {"4", "6", "8"} and _is_boundary(nxt):
        return PUNCT_SINGLE[n], i + 1, True

    # 종성 ㅎ(0) — 다음에 닫는 따옴표 2칸이 오면 종성 아님(위에서 처리)
    # 단독 0 뒤가 경계이고 직전이 모음 음절이면 종성 ㅎ 가능
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
    final = _take_final(chars, i_after_vowel, skip_jong=skip_jong)
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
    final = _take_final(chars, i + 1, skip_jong=skip_jong)
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
    """온표 자모 본문 직후가 경계·다음 온표·닫는부호·구두점·다음 음절이면 온표로 인정."""
    after = _peek(chars, after_i)
    if _is_boundary(after) or after == ON_SIGN or after == "7":
        return True
    if after is not None and after in PUNCT_SINGLE:
        return True
    if _starts_closing_multi(chars, after_i):
        return True
    if after is not None and _match_punct(chars, after_i) is not None:
        return True
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
    - 모드 종료 부호를 마침표로 내보내지 않음
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

        # 단순 영문 구두점
        if n in PUNCT_SINGLE and n in {"1", "4", "8", "6"}:
            # 쉼표는 “ 셀과 충돌 — eng에서는 1
            if n == "1":
                out.append(",")
                i += 1
                continue
            if n == "4":
                out.append(".")
                i += 1
                continue
            # 8/? 는 eng 질의에만 — 기본적으로 종료
            break

        # 그 외(한글 음절 시작 등) — 모드 종료, 셀은 남김
        break

    return i


def reverse_translate_line(raw_ascii: str) -> str:
    text = normalize_brf_ascii(raw_ascii)
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

        # 1b) 원문자 선택지 번호
        jumped = _try_circled_digit(chars, i, out)
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

        # 2) 복합 문장부호 최장 일치
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

        # 2b) 따옴표·낫표 직후 단독 로마자 한 글자 (‘a’~‘e’).
        if (
            open_quote_depth > 0
            and n in _LATIN_LETTERS
            and out
            and out[-1] in {"‘", "“", "「", "『"}
        ):
            nxt_i = i + 1
            if (
                _starts_closing_multi(chars, nxt_i)
                or (
                    nxt_i < len(chars)
                    and _match_punct(chars, nxt_i) is not None
                )
                or _is_boundary(_peek(chars, nxt_i))
            ):
                out.append(n)
                i += 1
                continue

        # 3) 온표 + 단독 자모 (종성/초성/모음 본문, 닫는따옴표 보호)
        if n == ON_SIGN:
            jumped = _try_on_sign(chars, i, out)
            if jumped is not None:
                i = jumped
                continue
            # else: fall through → 옹 약자

        # 3b) 드러냄표 ⠶(7) … 7 — 종성 ㅇ으로 붙지 못한 위치
        if n == "7":
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

        # 12) 1칸 구두점
        if n in PUNCT_SINGLE:
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
