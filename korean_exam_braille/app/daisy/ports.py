"""DTBook 내보내기 포트."""

from __future__ import annotations

from typing import Protocol

from korean_exam_braille.app.exam.models import ExamDocument


class DtbookExporter(Protocol):
    """ExamDocument → DTBook XML 문자열.

    완성된 DAISY 패키지가 아니라, 사용자가 DAISY를 만들 때 쓰는
    중간 구조 파일이다. 스키마·완성도는 구현체별로 다르다.
    """

    @property
    def available(self) -> bool:
        """다운로드 버튼 활성화 여부. False면 UI는 비활성+안내."""
        ...

    def export(self, exam: ExamDocument, *, title: str | None = None) -> str:
        """DTBook XML 텍스트."""
        ...
