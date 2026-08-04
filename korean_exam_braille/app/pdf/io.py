"""PDF 구조 JSON 저장/로드."""

from __future__ import annotations

import json
from pathlib import Path

from korean_exam_braille.app.pdf.models import PdfDocumentStructure


def structure_path_for(pdf_path: str | Path) -> Path:
    path = Path(pdf_path)
    return path.with_suffix(path.suffix + ".structure.json")


def save_structure(document: PdfDocumentStructure, path: str | Path | None = None) -> Path:
    if path is None:
        if not document.source_path:
            raise ValueError("source_path required when path omitted")
        path = structure_path_for(document.source_path)
    target = Path(path)
    target.write_text(
        json.dumps(document.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def load_structure(path: str | Path) -> PdfDocumentStructure:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return PdfDocumentStructure.from_dict(data)
