"""BRF 구조 태그·주석 JSON 저장/복원."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from korean_exam_braille.app.brf.models import BrfDocument, BrfLine
from korean_exam_braille.app.brf.parser import refresh_derived_fields


ANNOTATION_VERSION = 1


def annotation_path_for(brf_path: str | Path) -> Path:
    path = Path(brf_path)
    return path.with_suffix(path.suffix + ".annotations.json")


def export_annotations(document: BrfDocument) -> dict[str, Any]:
    lines_out: list[dict[str, Any]] = []
    for line in document.lines:
        if not line.tags and not line.notes:
            continue
        lines_out.append(
            {
                "global_index": line.global_index,
                "page_index": line.page_index,
                "line_index": line.line_index,
                "tags": list(line.tags),
                "notes": line.notes,
            }
        )
    return {
        "version": ANNOTATION_VERSION,
        "source_path": document.source_path,
        "line_count": document.line_count,
        "page_count": document.page_count,
        "lines": lines_out,
    }


def apply_annotations(document: BrfDocument, data: dict[str, Any]) -> int:
    """주석 JSON을 문서에 적용. 적용된 행 수를 반환."""
    by_global: dict[int, BrfLine] = {line.global_index: line for line in document.lines}
    applied = 0
    for item in data.get("lines", []):
        gid = int(item["global_index"])
        line = by_global.get(gid)
        if line is None:
            continue
        line.tags = list(item.get("tags") or [])
        line.notes = item.get("notes")
        applied += 1
    return applied


def save_annotations(document: BrfDocument, path: str | Path | None = None) -> Path:
    if path is None:
        if not document.source_path:
            raise ValueError("document.source_path is required when path is omitted")
        path = annotation_path_for(document.source_path)
    target = Path(path)
    payload = export_annotations(document)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def load_annotations(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_brf_with_annotations(brf_path: str | Path) -> BrfDocument:
    from korean_exam_braille.app.brf.parser import load_brf

    document = load_brf(brf_path)
    ann = annotation_path_for(brf_path)
    if ann.exists():
        apply_annotations(document, load_annotations(ann))
    refresh_derived_fields(document)
    return document
