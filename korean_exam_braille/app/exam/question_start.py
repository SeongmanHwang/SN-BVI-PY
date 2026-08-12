"""숫자 번호 → 시험 문항 확정. QUESTION_NUM 매치만으로는 확정하지 않는다."""

from __future__ import annotations

from korean_exam_braille.app.common.patterns import question_number_from_text


def is_question_start(
    text: str,
    *,
    question_range: tuple[int, int] | None = None,
    last_question: int | None = None,
) -> int | None:
    """시험 문항 시작이면 문항 번호, 아니면 None.

    PassageGroup ``[start~end]``가 있으면 그 범위만 허용하고,
    직전 확정 문항보다 번호가 커야 한다 (28→29→30, 1·2·17·31 거부).
    범위가 없으면 1~45 번호를 그대로 문항으로 본다 (지문 없는 단독 문항).
    """
    n = question_number_from_text(text)
    if n is None:
        return None
    if question_range is not None:
        start, end = question_range
        if not (start <= n <= end):
            return None
        if last_question is not None and n <= last_question:
            return None
    return n
