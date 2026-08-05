"""미구현 표시용 DTBook exporter — 다운로드 비활성."""

from __future__ import annotations

from korean_exam_braille.app.exam.models import ExamDocument


class StubDtbookExporter:
    """아직 스키마가 고정되지 않았을 때 사용자 모드 버튼을 끈다."""

    @property
    def available(self) -> bool:
        return False

    def export(self, exam: ExamDocument, *, title: str | None = None) -> str:
        raise NotImplementedError(
            "DTBook XML 내보내기는 아직 준비 중입니다."
        )
