"""묵자(PDF 후보·Exam 빌더·점역)가 공유하는 구조 정규식.

매체별(BRF ASCII) 탐지기는 brf/structure_detect 등 별도 패턴을 쓴다.
"""

from __future__ import annotations

import re

# [16~17], [16-17] 등 지문 범위
PASSAGE_RANGE = re.compile(r"\[\s*(\d{1,2})\s*[~\-–—]\s*(\d{1,2})\s*\]")

# 문항 번호: "16." / "16．" / "16 발문…" (줄 시작 또는 개행 뒤)
QUESTION_NUM = re.compile(
    r"(?:^|\n)\s*(?:"
    r"(\d{1,2})\s*[\.．。]"
    r"|(\d{1,2})\s+"
    r")"
)
