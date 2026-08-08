"""그림 자리표시 묵자·점자 ASCII 대응.

추출 UI는 ``[그림]`` 으로 두고, 점역은 규정 관례 문자열
``⠠⠄⠈⠪⠐⠕⠢⠀⠠⠗⠶⠐⠜⠁⠠⠄`` (그림 생략)로 일괄 치환한다.
역점역도 같은 묵자로 되돌려 추출 표시와 맞춘다.
"""

from __future__ import annotations

FIGURE_INK = "[그림]"
# ⠠⠄⠈⠪⠐⠕⠢⠀⠠⠗⠶⠐⠜⠁⠠⠄
FIGURE_BRAILLE_ASCII = ",'@[\"o5 ,r7\">a,'"

__all__ = ["FIGURE_BRAILLE_ASCII", "FIGURE_INK"]
