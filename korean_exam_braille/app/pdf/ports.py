"""PDF 추출 포트 — 구현 교체 지점."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from korean_exam_braille.app.pdf.models import PdfDocumentStructure


class PdfStructureExtractor(Protocol):
    def extract(
        self,
        path: str | Path,
        *,
        page_numbers: list[int] | None = None,
    ) -> PdfDocumentStructure: ...
