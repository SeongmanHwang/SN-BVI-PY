"""Exam 구조 검증기."""

from __future__ import annotations

from korean_exam_braille.app.exam.models import ExamDocument, ExamNode


def _walk(node: ExamNode):
    yield node
    for child in node.children:
        yield from _walk(child)


class RuleExamStructureValidator:
    """문항 소속·선택지 개수 등 기본 제약 검사."""

    def validate(self, exam: ExamDocument) -> list[str]:
        warnings: list[str] = []

        if exam.unclassified_ids:
            warnings.append(
                f"unclassified blocks: {len(exam.unclassified_ids)}"
            )

        orphan_questions = 0
        choice_issues = 0
        for node in _walk(exam.root):
            if node.node_type != "Question":
                continue
            # PassageGroup 직속이 아니면 고아로 본다
            parent_is_group = False
            for maybe in _walk(exam.root):
                if maybe.node_type == "PassageGroup" and any(
                    c.id == node.id for c in maybe.children
                ):
                    parent_is_group = True
                    break
            if not parent_is_group and node.id != exam.root.id:
                # 루트 직속 Question
                if any(c.id == node.id for c in exam.root.children):
                    orphan_questions += 1

            n_choices = sum(1 for c in node.children if c.node_type == "Choice")
            if n_choices and n_choices != 5:
                choice_issues += 1
                warnings.append(
                    f"question {node.id}: expected 5 choices, found {n_choices}"
                )

        if orphan_questions:
            warnings.append(
                f"questions outside PassageGroup: {orphan_questions}"
            )

        return warnings
