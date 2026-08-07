"""한자 → 한글 음독 치환 (현행 한국 점자 실무).

현행 『한국 점자 규정』에는 일반 한자용 전환 표(전치 기호)가 없다.
국립국어원 점자 출판 실무에 맞춰 다음만 한다.

1. 한자 단독 → 해당 음(음독)을 한글로 적는다.
2. 한글·한자 병기(음이 같으면) → 한자 쪽을 생략한다.

예::

    訓蒙字會 → 훈몽자회
    훈몽자회(訓蒙字會) → 훈몽자회
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

__all__ = [
    "is_cjk_ideograph",
    "hanja_reading",
    "replace_hanja_with_reading",
]

# 병기 접기: 訓蒙字會→훈몽자회 후 훈몽자회(훈몽자회) / 학교(학교)
_REDUNDANT_GLOSS = re.compile(r"([가-힣]+)[\(（]\1[\)）]")


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
        out = _REDUNDANT_GLOSS.sub(r"\1", out)
    return out
