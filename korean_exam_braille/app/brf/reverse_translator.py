"""한국 점자 규정 기반 묵자 역점역.

Inspector 분석용. 약자·약어·초성ㅇ 생략·된소리·숫자·영문을 처리한다.
"""

from __future__ import annotations

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
    ROMAN_SIGN,
    TENSED_MAP,
    TENSED_PREFIX,
    WORD_ABBREV,
    YEONG_ONSET_OVERRIDE,
    compose_hangul,
)

_PUNCT_AT_END = {
    "4": ".",  # ⠲ = 종성 ㅍ과 동일
    "6": "!",  # ⠖ = 종성 ㅋ과 동일
    "8": "?",  # ⠦ = 종성 ㅌ과 동일
}


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
    return compose_hangul(cho, jung, jong) or "·"


def _peek(chars: list[str], i: int) -> str | None:
    if i >= len(chars):
        return None
    return _norm_cell(chars[i])


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
    """(종성 또는 문장부호, 새 인덱스, 문장부호 여부)."""
    if i >= len(chars):
        return None
    n = _norm_cell(chars[i])
    nxt = _peek(chars, i + 1)

    if nxt is not None and (n + nxt) in JONGSEONG_DIGRAPHS:
        return JONGSEONG_DIGRAPHS[n + nxt], i + 2, False

    if n in _PUNCT_AT_END and _is_boundary(nxt):
        return _PUNCT_AT_END[n], i + 1, True

    if n in JONGSEONG:
        return JONGSEONG[n], i + 1, False
    return None


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
    # 종성 다음이 모음이면 종성이 아니라 다음 음절 시작
    after = _peek(chars, new_i)
    if after is not None and (
        after in JUNGSEONG or after in ABBREV_VC or after in {k[0] for k in JUNGSEONG_DIGRAPHS}
    ):
        out.append(_syllable(cho, jung))
        return i + 1
    out.append(_syllable(cho, jung, text))
    return new_i


def reverse_translate_line(raw_ascii: str) -> str:
    text = normalize_brf_ascii(raw_ascii)
    if _is_separator_line(text):
        return text.strip()

    chars = list(text)
    i = 0
    out: list[str] = []

    while i < len(chars):
        ch = chars[i]
        n = _norm_cell(ch)

        if ch == " ":
            out.append(" ")
            i += 1
            continue

        # 숫자
        if n == NUMBER_SIGN:
            i += 1
            digits: list[str] = []
            while i < len(chars) and _norm_cell(chars[i]) in NUMBER_MAP:
                digits.append(NUMBER_MAP[_norm_cell(chars[i])])
                i += 1
            out.append("".join(digits) if digits else "#")
            continue

        # 영문: 로마자표 0(⠴) 뒤에 로마자. ; 는 초성 ㅊ이므로 쓰지 않음.
        if n == ROMAN_SIGN and i + 1 < len(chars):
            nxt = _norm_cell(chars[i + 1])
            if nxt == "," or nxt in "abcdefghijklmnopqrstuvwxyz":
                i += 1
                capital = False
                while i < len(chars) and chars[i] != " ":
                    cn = _norm_cell(chars[i])
                    if cn == ",":
                        capital = True
                        i += 1
                        continue
                    if cn in "abcdefghijklmnopqrstuvwxyz":
                        out.append(cn.upper() if capital else cn)
                        capital = False
                        i += 1
                        continue
                    break
                continue

        # 레거시/혼용: ; 뒤가 대문자표+로마자일 때만 영문으로 본다
        if n == LETTER_SIGN and i + 1 < len(chars) and _norm_cell(chars[i + 1]) == ",":
            if i + 2 < len(chars) and _norm_cell(chars[i + 2]) in "abcdefghijklmnopqrstuvwxyz":
                i += 1
                capital = False
                while i < len(chars) and chars[i] != " ":
                    cn = _norm_cell(chars[i])
                    if cn == ",":
                        capital = True
                        i += 1
                        continue
                    if cn in "abcdefghijklmnopqrstuvwxyz":
                        out.append(cn.upper() if capital else cn)
                        capital = False
                        i += 1
                        continue
                    break
                continue

        # 단어 약어
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

        # 된소리 초성
        if n == TENSED_PREFIX and i + 1 < len(chars) and _norm_cell(chars[i + 1]) in TENSED_MAP:
            cho = TENSED_MAP[_norm_cell(chars[i + 1])]
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

        # 초성 + VC 약자 / 영 변형
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

        # VC 약자 (초성 ㅇ)
        if n in ABBREV_VC:
            jung, jong = ABBREV_VC[n]
            out.append(_syllable("ㅇ", jung, jong))
            i += 1
            continue

        # 초성 + 모음 → 음절 / 모음 없으면 약자
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
            out.append("·")
            i += 1
            continue

        # 전용 약자 (가 $, 사 l)
        if n in ABBREV_CV:
            i = _emit_abbrev_cv(out, chars, n, i)
            continue

        # 중성만 (ㅇ 생략)
        vowel = _take_vowel(chars, i)
        if vowel:
            jung, k = vowel
            i = _emit_syllable_with_optional_final(out, chars, "ㅇ", jung, k)
            continue

        # 단독 문장부호·구분 문자
        if n in _PUNCT_AT_END:
            out.append(_PUNCT_AT_END[n])
            i += 1
            continue

        simple_punct = {"1": ",", "-": "-"}
        if n in simple_punct:
            out.append(simple_punct[n])
            i += 1
            continue

        if n in "=@g.-_":
            out.append(ch)
            i += 1
            continue

        out.append("·")
        i += 1

    return "".join(out)


def reverse_translate_unicode(unicode_braille: str) -> str:
    from korean_exam_braille.app.brf.ascii_braille import unicode_to_ascii

    return reverse_translate_line(unicode_to_ascii(unicode_braille))


def preview_pair(raw_ascii: str) -> tuple[str, str]:
    normalized = normalize_brf_ascii(raw_ascii)
    return ascii_to_unicode(normalized), reverse_translate_line(raw_ascii)
