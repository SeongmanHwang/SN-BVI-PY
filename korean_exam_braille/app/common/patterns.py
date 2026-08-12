"""묵자(PDF 후보·Exam 빌더·점역)가 공유하는 구조 정규식.

매체별(BRF ASCII) 탐지기는 brf/structure_detect 등 별도 패턴을 쓴다.
"""

from __future__ import annotations

import re

# [16~17], [16-17] 등 지문 범위
PASSAGE_RANGE = re.compile(r"\[\s*(\d{1,2})\s*[~\-–—]\s*(\d{1,2})\s*\]")

# 문항 번호: "16." / "16．" / "16 발문…" (줄 시작 또는 개행 뒤)
# 매치 자체는 번호 모양일 뿐, Question 확정은 Exam 빌더가 문맥으로 한다.
QUESTION_NUM = re.compile(
    r"(?:^|\n)\s*(?:"
    r"(\d{1,2})\s*[\.．。]"
    r"|(\d{1,2})\s+"
    r")"
)

_QUESTION_NUM_MAX = 45


def question_number_from_text(text: str | None) -> int | None:
    """줄 앞 번호(1~45)를 뽑는다. 시험 문항인지는 호출측 문맥이 판정한다."""
    m = QUESTION_NUM.search(text or "")
    if not m:
        return None
    for g in m.groups():
        if g and g.isdigit():
            n = int(g)
            if 1 <= n <= _QUESTION_NUM_MAX:
                return n
    return None
