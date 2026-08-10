"""한자 → 한글 음독 치환 (현행 한국 점자 실무).

현행 『한국 점자 규정』에는 일반 한자용 전환 표(전치 기호)가 없다.
국립국어원 점자 출판 실무에 맞춰 다음만 한다.

1. 한자 단독 → 해당 음(음독)을 한글로 적는다.
2. 한글·한자 병기(음이 같으면) → 한자 쪽을 생략한다.
   음 비교 시 **두음법칙**를 적용한다
   (``노모(老母)`` → 사전이 ``로모``여도 ``노모``로 접기).

예::

    訓蒙字會 → 훈몽자회
    훈몽자회(訓蒙字會) → 훈몽자회
    노모(老母) → 노모
    學校(학교) → 학교

``⠴``(ASCII ``0``) 등을 한자 전환 표로 임의 사용하지 않는다.
원문에 한자가 있었다는 시각 정보를 점자에 남기는 것은 공식 규정이 아니라
프로젝트 확장 표기이며, 이 모듈 범위 밖이다.

사전에 없는 CJK는 음독을 만들 수 없어 빗금(``/``)으로 남긴다.
"""

from __future__ import annotations

import re
import unicodedata

import hanjadict

from korean_exam_braille.app.common.korean_tables import (
    CHO_INDEX,
    JONG_INDEX,
    JUNG_INDEX,
    compose_hangul,
)

__all__ = [
    "is_cjk_ideograph",
    "hanja_reading",
    "apply_dueum_beop",
    "replace_hanja_with_reading",
]

# 병기 접기: 왼쪽·괄호 안 한글이 (두음법칙 포함) 동등이면 왼쪽(정규화)만 남김
_REDUNDANT_GLOSS = re.compile(r"([가-힣]+)[\(（]([가-힣]+)[\)）]")

# 두음법칙: 단어 첫머리 ㄴ/ㄹ + ㅑㅕㅖㅛㅠㅣ(·ㅒ)
_IOTIZED_JUNG = frozenset({"ㅑ", "ㅒ", "ㅕ", "ㅖ", "ㅛ", "ㅠ", "ㅣ"})

_CHO_LIST = [None] * 19
for _ch, _i in CHO_INDEX.items():
    _CHO_LIST[_i] = _ch
_JUNG_LIST = [None] * 21
for _ch, _i in JUNG_INDEX.items():
    _JUNG_LIST[_i] = _ch
_JONG_LIST = [""] * 28
for _ch, _i in JONG_INDEX.items():
    _JONG_LIST[_i] = _ch


def is_cjk_ideograph(ch: str) -> bool:
    """한자(CJK 표의·확장·호환) 여부."""
    if len(ch) != 1:
        return False
    if hanjadict.is_hanja(ch):
        return True
    code = ord(ch)
    if 0x3400 <= code <= 0x4DBF:  # Ext A
        return True
    if 0x4E00 <= code <= 0x9FFF:  # Unified
        return True
    if 0xF900 <= code <= 0xFAFF:  # Compatibility
        return True
    if 0x20000 <= code <= 0x2A6DF:  # Ext B
        return True
    name = unicodedata.name(ch, "")
    return name.startswith("CJK UNIFIED IDEOGRAPH") or name.startswith(
        "CJK COMPATIBILITY IDEOGRAPH"
    )


def hanja_reading(ch: str) -> str | None:
    """한 글자의 음독. 없으면 None."""
    if len(ch) != 1:
        return None
    reading = hanjadict.pronunciation(ch)
    if reading and reading.strip():
        # 복수 음이 있으면 첫 음만
        return reading.strip().split(",")[0].split("/")[0].strip()
    return None


def _decompose(ch: str) -> tuple[str, str, str] | None:
    code = ord(ch) - 0xAC00
    if not 0 <= code < 11172:
        return None
    cho_i = code // (21 * 28)
    jung_i = (code % (21 * 28)) // 28
    jong_i = code % 28
    return _CHO_LIST[cho_i], _JUNG_LIST[jung_i], _JONG_LIST[jong_i]


def _dueum_first_syllable(ch: str) -> str:
    """단어 첫 음절에 남한 한글 맞춤법 두음법칙 적용."""
    parts = _decompose(ch)
    if parts is None:
        return ch
    cho, jung, jong = parts
    if cho == "ㄹ":
        cho = "ㅇ" if jung in _IOTIZED_JUNG else "ㄴ"
    elif cho == "ㄴ" and jung in _IOTIZED_JUNG:
        cho = "ㅇ"
    else:
        return ch
    out = compose_hangul(cho, jung, jong)
    return out if out else ch


def apply_dueum_beop(word: str) -> str:
    """한글 어절 맨 앞 음절에 두음법칙만 적용 (병기 동등 비교용)."""
    if not word:
        return word
    return _dueum_first_syllable(word[0]) + word[1:]


def _readings_equivalent(a: str, b: str) -> bool:
    if a == b:
        return True
    return apply_dueum_beop(a) == apply_dueum_beop(b)


def _collapse_redundant_gloss(match: re.Match[str]) -> str:
    left, right = match.group(1), match.group(2)
    if not _readings_equivalent(left, right):
        return match.group(0)
    # 교과서 표기에 가깝게 두음법칙 적용형을 남긴다
    return apply_dueum_beop(left)


def replace_hanja_with_reading(text: str) -> str:
    """한자 단독은 음독으로, 한글·한자 병기는 한자를 생략한다."""
    if not text:
        return text
    parts: list[str] = []
    for ch in text:
        if not is_cjk_ideograph(ch):
            parts.append(ch)
            continue
        reading = hanja_reading(ch)
        parts.append(reading if reading else "/")
    out = "".join(parts)
    prev = None
    while prev != out:
        prev = out
        out = _REDUNDANT_GLOSS.sub(_collapse_redundant_gloss, out)
    return out
