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

from korean_exam_braille.app.brf.ascii_braille import ascii_to_unicode, normalize_brf_ascii
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
    ON_SIGN_JAMO,
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
    k for k, v in PUNCT_MULTI.items() if v in {"’", "”", "』", "」", ")", "}"}
) | frozenset({"0'", "02", "01", "00", ",0"})

_LATIN_LETTERS = frozenset("abcdefghijklmnopqrstuvwxyz")
# 대문자 약어(EXW) 직후 한글 조사로만 종료. a–z↔한글 겹침을 피한다.
_PARTICLE_AFTER_ACRONYM = frozenset(JUNGSEONG) | frozenset({"c", "z", "!", "$"})

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
    if s.startswith("=") and s.endswith("=") and set(body) <= set("=gG"):
        return True
    if len(body) >= 6 and len(set(body)) == 1:
        return True
    if len(body) >= 6 and all(ch in "-=._*gG=" for ch in body):
        return True
    return False


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

    `82`는 뒤에 `#`가 오면 지문 범위이므로 대괄호로 보지 않는다.
    """
    for key, ink in _PUNCT_MULTI_SORTED:
        got = _slice_norm(chars, i, len(key))
        if got != key:
            continue
        if key == "82":
            nxt = _peek(chars, i + 2)
            if nxt == NUMBER_SIGN:
                continue
        return ink, len(key)
    return None


def _try_circled_digit(chars: list[str], i: int, out: list[str]) -> int | None:
    """원문자 번호 7#a7 → ① … 7#e7 → ⑤."""
    if _slice_norm(chars, i, 2) != "7#":
        return None
    if i + 3 >= len(chars):
        return None
    dig = _norm_cell(chars[i + 2])
    if dig not in "abcde":
        return None
    if _norm_cell(chars[i + 3]) != "7":
        return None
    out.append(str("①②③④⑤"[ "abcde".index(dig) ]))
    return i + 4


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


def _latin_word_continues(chars: list[str], i: int) -> bool:
    """i부터 영단어가 이어지면 True (조사 후보가 아닐 때)."""
    if _hangul_particle_len(chars, i) > 0:
        return False
    count = 0
    j = i
    while j < len(chars) and chars[j] != " ":
        n = _norm_cell(chars[j])
        if n == ",":
            j += 1
            continue
        if n in _LATIN_LETTERS:
            count += 1
            j += 1
            continue
        break
    return count >= 2


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


def _take_final(chars: list[str], i: int) -> tuple[str, int, bool] | None:
    """(종성 또는 문장부호, 새 인덱스, 문장부호 여부).

    닫는 복합 부호 시작이면 종성으로 가져가지 않는다.
    """
    if i >= len(chars):
        return None
    if _starts_closing_multi(chars, i):
        return None

    n = _norm_cell(chars[i])
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
    """종성으로 읽은 셀이 사실은 다음 음절 시작일 수 있는지.

    한국 점자는 초성·종성 점형이 다르므로, 종성 전용 셀(a,b,7,…)은
    다음이 모음이어도 받침으로 유지해야 한다. (합의·대상에서·승낙이)
    """
    return _can_begin_syllable(cell)


def _emit_syllable_with_optional_final(
    out: list[str],
    chars: list[str],
    cho: str,
    jung: str,
    i_after_vowel: int,
) -> int:
    final = _take_final(chars, i_after_vowel)
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


def _emit_abbrev_cv(out: list[str], chars: list[str], cell: str, i: int) -> int:
    cho, jung = ABBREV_CV[cell]
    final = _take_final(chars, i + 1)
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


def _try_on_sign(chars: list[str], i: int, out: list[str]) -> int | None:
    """온표(=) + 단독 자모. 옹 약자와 동일 셀이므로 문맥으로 구분.

    다음이 자모이고, 그 다음이 경계·닫는부호·문자열 끝이면 온표로 본다.
    (따옴표 안 ‘ㅣ’ 등). 그 외 `=` 단독/뒤에 이어지는 음절은 옹 약자로 둔다.
    """
    if _norm_cell(chars[i]) != ON_SIGN:
        return None
    if i + 1 >= len(chars):
        return None

    # 온표 + 된소리표 + 초성
    if _norm_cell(chars[i + 1]) == TENSED_PREFIX and i + 2 < len(chars):
        body = _norm_cell(chars[i + 2])
        if body in TENSED_MAP:
            after = _peek(chars, i + 3)
            if _is_boundary(after) or _starts_closing_multi(chars, i + 3) or (
                after is not None and _match_punct(chars, i + 3)
            ):
                out.append(TENSED_MAP[body])
                return i + 3

    nxt = _norm_cell(chars[i + 1])
    jamo = ON_SIGN_JAMO.get(nxt)
    if jamo is None:
        return None

    after = _peek(chars, i + 2)
    # 온표 문맥: 자모 한 칸 뒤가 끝·공백·닫는 부호
    if not (
        _is_boundary(after)
        or _starts_closing_multi(chars, i + 2)
        or (after is not None and _match_punct(chars, i + 2) is not None)
    ):
        return None

    out.append(jamo)
    return i + 2


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
        return text.strip()

    chars = list(text)
    i = 0
    out: list[str] = []
    # 직전 출력이 여는 따옴표/낫표면 온표 해석을 우선
    open_quote_depth = 0

    while i < len(chars):
        ch = chars[i]
        n = _norm_cell(ch)

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

        # 2) 복합 문장부호 최장 일치
        punct = _match_punct(chars, i)
        if punct:
            ink, ncons = punct
            if ink:
                out.append(ink)
            if ink in {"‘", "“", "『", "「", "(", "["}:
                open_quote_depth += 1
            elif ink in {"’", "”", "』", "」", ")", "]"} and open_quote_depth > 0:
                open_quote_depth -= 1
            i += ncons
            continue

        # 3) 온표 + 단독 자모 (따옴표 안이거나 자모+닫힘 문맥)
        if n == ON_SIGN:
            # 따옴표 안에서는 자모 뒤 조건 완화: 다음이 자모면 온표 시도
            if open_quote_depth > 0 and i + 1 < len(chars):
                nxt = _norm_cell(chars[i + 1])
                if nxt == TENSED_PREFIX and i + 2 < len(chars):
                    body = _norm_cell(chars[i + 2])
                    if body in TENSED_MAP:
                        out.append(TENSED_MAP[body])
                        i += 3
                        continue
                if nxt in ON_SIGN_JAMO:
                    out.append(ON_SIGN_JAMO[nxt])
                    i += 2
                    continue
            jumped = _try_on_sign(chars, i, out)
            if jumped is not None:
                i = jumped
                continue
            # else: fall through → 옹 약자

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
                i = _emit_syllable_with_optional_final(out, chars, "ㄲ", "ㅏ", j)
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
                    i = _emit_syllable_with_optional_final(out, chars, cho, jung, k)
                    continue
                # 된소리 초성 뒤 모음이 없으면 가류처럼 암시 ㅏ
                i = _emit_syllable_with_optional_final(out, chars, cho, "ㅏ", j)
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
        if n in CHOSEONG:
            cho = CHOSEONG[n]
            vowel = _take_vowel(chars, i + 1)
            if vowel:
                jung, k = vowel
                i = _emit_syllable_with_optional_final(out, chars, cho, jung, k)
                continue
            if n in ABBREV_CV:
                i = _emit_abbrev_cv(out, chars, n, i)
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
            i = _emit_abbrev_cv(out, chars, n, i)
            continue

        # 11) 중성만 (초성 ㅇ 생략) — 온표가 없을 때 ‘아’
        vowel = _take_vowel(chars, i)
        if vowel:
            jung, k = vowel
            i = _emit_syllable_with_optional_final(out, chars, "ㅇ", jung, k)
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

        if n in "=@g.-_":
            out.append(ch if ch in "=@g.-_" else n)
            i += 1
            continue

        out.append(_unknown(ch if ch.strip() else n))
        i += 1

    return "".join(out)


def reverse_translate_unicode(unicode_braille: str) -> str:
    from korean_exam_braille.app.brf.ascii_braille import unicode_to_ascii

    return reverse_translate_line(unicode_to_ascii(unicode_braille))


def preview_pair(raw_ascii: str) -> tuple[str, str]:
    normalized = normalize_brf_ascii(raw_ascii)
    return ascii_to_unicode(normalized), reverse_translate_line(raw_ascii)
