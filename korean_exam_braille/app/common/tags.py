"""계층 공통 상수·타입."""

from __future__ import annotations

# PDF / BRF / Exam 구조가 공유하는 태그 집합
STRUCTURE_TAGS: tuple[str, ...] = (
    "Exam",
    "Instruction",
    "PassageGroup",
    "Passage",
    "Paragraph",
    "Question",
    "Prompt",
    "Choice",
    "ExampleBox",
    "Quotation",
    "Footnote",
    "TableDescription",
    "FigureDescription",
    "TableAsset",
    "FigureAsset",
    "Header",
    "Footer",
    "Separator",
    "PageBreak",
    "EndNotice",
    "Unknown",
)

# 수능 국어 의미 노드 (ExamDocument 트리)
EXAM_NODE_TYPES: tuple[str, ...] = (
    "ExamDocument",
    "ExamSection",
    "Instruction",
    "PassageGroup",
    "Passage",
    "Paragraph",
    "Question",
    "Prompt",
    "Choice",
    "ExampleBox",
    "Quotation",
    "Footnote",
    "TableAsset",
    "FigureAsset",
    "EndNotice",
    "Unknown",
)
