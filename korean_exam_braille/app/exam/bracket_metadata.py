"""Exam 노드의 [A]~[E] 구간 메타데이터 공통 처리."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def _labels_from_value(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return list(dict.fromkeys(str(label) for label in value if str(label).strip()))


def labels_from_tags(tags: Iterable[object], *, prefix: str) -> list[str]:
    labels: list[str] = []
    for raw in tags:
        if not isinstance(raw, str) or not raw.startswith(prefix):
            continue
        for label in raw.removeprefix(prefix).split(","):
            label = label.strip()
            if label and label not in labels:
                labels.append(label)
    return labels


def metadata_from_candidate_tags(tags: Iterable[object]) -> dict[str, list[str]]:
    """PDF 태그를 출력 계층이 공유하는 명시적 Exam 메타로 바꾼다."""
    tag_list = list(tags)
    labels = labels_from_tags(tag_list, prefix="bracket:")
    starts = labels_from_tags(tag_list, prefix="bracket-start:")
    ends = labels_from_tags(tag_list, prefix="bracket-end:")
    out: dict[str, list[str]] = {}
    if labels:
        out["bracket_labels"] = labels
    if starts:
        out["bracket_start_labels"] = starts
    if ends:
        out["bracket_end_labels"] = ends
    return out


def bracket_labels(
    metadata: Mapping[str, Any],
    *,
    starts_only: bool = False,
    ends_only: bool = False,
) -> list[str]:
    """Exam 메타에서 구간 소속·시작·종료 표지를 읽는다."""
    if starts_only and ends_only:
        raise ValueError("starts_only and ends_only cannot both be true")
    if starts_only:
        key = "bracket_start_labels"
        prefix = "bracket-start:"
    elif ends_only:
        key = "bracket_end_labels"
        prefix = "bracket-end:"
    else:
        key = "bracket_labels"
        prefix = "bracket:"
    labels = _labels_from_value(metadata.get(key))
    if labels:
        return labels

    # 이전 구조와 저장 파일 호환
    raw_tags = metadata.get("candidate_tags")
    if not isinstance(raw_tags, list):
        return []
    return labels_from_tags(raw_tags, prefix=prefix)
