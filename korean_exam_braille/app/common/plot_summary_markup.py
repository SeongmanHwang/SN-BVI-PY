"""줄거리 요약 구간 끝 표지 묵자·점자 ASCII."""

from __future__ import annotations

# PDF 원문에 [중략 부분의 줄거리] 등이 있으므로 시작 표지는 넣지 않고
# 글씨체(돋움·작은 글씨) 구간이 끝나는 곳에만 붙인다.
PLOT_SUMMARY_END_INK = "[줄거리 끝]"
# hangul_text_to_ascii("[줄거리 끝]") 와 동일 — 전용 상수로 왕복 고정
PLOT_SUMMARY_END_BRAILLE_ASCII = '82.&`s"o ,`[8;0'

__all__ = [
    "PLOT_SUMMARY_END_BRAILLE_ASCII",
    "PLOT_SUMMARY_END_INK",
]
