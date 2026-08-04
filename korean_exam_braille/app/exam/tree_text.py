"""ExamDocument 트리 텍스트·요약."""

from __future__ import annotations

from korean_exam_braille.app.exam.models import ExamDocument, ExamNode


def exam_counts(exam: ExamDocument) -> dict[str, int]:
    counts: dict[str, int] = {}

    def walk(node: ExamNode) -> None:
        counts[node.node_type] = counts.get(node.node_type, 0) + 1
        for child in node.children:
            walk(child)

    walk(exam.root)
    return counts


def format_exam_summary(exam: ExamDocument) -> str:
    c = exam_counts(exam)
    return (
        f"PassageGroup {c.get('PassageGroup', 0)} · "
        f"Passage {c.get('Passage', 0)} · "
        f"Question {c.get('Question', 0)} · "
        f"Choice {c.get('Choice', 0)} · "
        f"ExampleBox {c.get('ExampleBox', 0)} · "
        f"relations {len(exam.relations)} · "
        f"unclassified {len(exam.unclassified_ids)}"
    )


def format_exam_tree(
    exam: ExamDocument,
    *,
    max_text: int = 48,
    max_nodes: int = 400,
) -> str:
    """들여쓰기 트리 문자열 (관계 검수용)."""
    lines: list[str] = []
    count = 0

    def walk(node: ExamNode, depth: int) -> None:
        nonlocal count
        if count >= max_nodes:
            return
        count += 1
        raw = (node.source_range.raw_text or "").replace("\n", " ").strip()
        if len(raw) > max_text:
            raw = raw[: max_text - 1] + "…"
        tip = f" — {raw}" if raw else ""
        extra = ""
        qn = node.metadata.get("question_number")
        if qn is not None:
            extra = f" #{qn}"
        lines.append(f"{'  ' * depth}{node.node_type}{extra} ({node.id}){tip}")
        for child in node.children:
            walk(child, depth + 1)

    walk(exam.root, 0)
    if count >= max_nodes:
        lines.append(f"… (truncated at {max_nodes} nodes)")
    if exam.relations:
        lines.append("relations:")
        for rel in exam.relations[:50]:
            lines.append(
                f"  {rel.relation_type}: {rel.source_id} → {rel.target_id}"
            )
        if len(exam.relations) > 50:
            lines.append(f"  … 외 {len(exam.relations) - 50}건")
    return "\n".join(lines)
