"""기존 extract_pdf를 포트에 맞춘 어댑터."""

from __future__ import annotations

from pathlib import Path

from korean_exam_braille.app.pdf.extractor import extract_pdf
from korean_exam_braille.app.pdf.models import PdfDocumentStructure


class DefaultPdfStructureExtractor:
    def extract(
        self,
        path: str | Path,
        *,
        page_numbers: list[int] | None = None,
    ) -> PdfDocumentStructure:
        return extract_pdf(path, page_numbers=page_numbers)
