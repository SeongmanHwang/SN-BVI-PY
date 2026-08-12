"""규칙 기반 Exam 구조 빌더 — PDF candidate_tags → PassageGroup 트리."""

from __future__ import annotations

from dataclasses import dataclass, field

from korean_exam_braille.app.common.patterns import PASSAGE_RANGE
from korean_exam_braille.app.exam.bracket_metadata import (
    metadata_from_candidate_tags,
)
from korean_exam_braille.app.exam.genre_paragraph_split import apply_genre_paragraph_splits
from korean_exam_braille.app.exam.question_start import is_question_start
from korean_exam_braille.app.exam.models import (
    ExamDocument,
    ExamNode,
    ExamRelation,
    SourceRange,
)
from korean_exam_braille.app.pdf.models import PdfBlock, PdfDocumentStructure


def _primary_tag(block: PdfBlock) -> str | None:
    tags = list(block.tags) or list(block.candidate_tags)
    priority = (
        "Header",
        "Footer",
        "EndNotice",
        "PassageGroup",
        "Question",
        "Choice",
        "TableAsset",
        "FigureAsset",
        "ExampleBox",
    )
    for name in priority:
        if name in tags:
            return name
    return None


def _source(block: PdfBlock) -> SourceRange:
    return SourceRange(
        page_number=block.page_number,
        block_ids=[block.id],
        raw_text=block.text,
    )


def _node_from_block(
    block: PdfBlock,
    node_type: str,
    *,
    node_id: str | None = None,
    confidence: float = 0.85,
    **extra_meta: object,
) -> ExamNode:
    meta: dict = {
        "candidate_tags": list(block.candidate_tags),
        "tags": list(block.tags),
        **metadata_from_candidate_tags(block.candidate_tags),
        **extra_meta,
    }
    return ExamNode(
        id=node_id or block.id,
        node_type=node_type,
        source_range=_source(block),
        confidence=confidence,
        metadata=meta,
    )


def _iter_blocks(pdf: PdfDocumentStructure) -> list[PdfBlock]:
    blocks: list[PdfBlock] = []
    for page in sorted(pdf.pages, key=lambda p: p.page_number):
        page_blocks = sorted(page.blocks, key=lambda b: b.reading_order)
        blocks.extend(page_blocks)
    return blocks


@dataclass
class _GroupState:
    node: ExamNode
    start_q: int | None = None
    end_q: int | None = None
    current_question: ExamNode | None = None
    last_q: int | None = None

    @property
    def question_range(self) -> tuple[int, int] | None:
        if self.start_q is None or self.end_q is None:
            return None
        return (self.start_q, self.end_q)


@dataclass
class RuleExamStructureBuilder:
    """reading_order 순 상태 기계로 PassageGroup·문항·선택지를 묶는다."""

    _group_seq: int = field(default=0, init=False, repr=False)

    def build(self, pdf: PdfDocumentStructure) -> ExamDocument:
        root_children: list[ExamNode] = []
        relations: list[ExamRelation] = []
        unclassified: list[str] = []
        page_artifacts: list[ExamNode] = []
        group: _GroupState | None = None
        orphan_question: ExamNode | None = None

        def current_question() -> ExamNode | None:
            if group is not None and group.current_question is not None:
                return group.current_question
            return orphan_question

        def flush_group() -> None:
            nonlocal group
            if group is None:
                return
            group.current_question = None
            root_children.append(group.node)
            group = None

        def start_group(block: PdfBlock) -> None:
            nonlocal group, orphan_question
            flush_group()
            orphan_question = None
            self._group_seq += 1
            m = PASSAGE_RANGE.search(block.text or "")
            start_q = int(m.group(1)) if m else None
            end_q = int(m.group(2)) if m else None
            node = _node_from_block(
                block,
                "PassageGroup",
                node_id=f"passage-group-{self._group_seq}",
                start_question=start_q,
                end_question=end_q,
            )
            group = _GroupState(node=node, start_q=start_q, end_q=end_q)

        def start_question(block: PdfBlock, qnum: int | None) -> ExamNode:
            nonlocal orphan_question
            q = _node_from_block(
                block,
                "Question",
                question_number=qnum,
            )
            if group is not None:
                group.node.children.append(q)
                group.current_question = q
                if qnum is not None:
                    group.last_q = qnum
                orphan_question = None
                relations.append(
                    ExamRelation(
                        relation_type="refers_to_passage",
                        source_id=q.id,
                        target_id=group.node.id,
                    )
                )
            else:
                root_children.append(q)
                orphan_question = q
            return q

        def attach_body(block: PdfBlock) -> None:
            q = current_question()
            if group is None and q is None:
                unclassified.append(block.id)
                root_children.append(_node_from_block(block, "Unknown", confidence=0.0))
                return
            if q is not None:
                has_prompt = any(c.node_type == "Prompt" for c in q.children)
                child_type = "Paragraph" if has_prompt else "Prompt"
                q.children.append(_node_from_block(block, child_type))
                return
            assert group is not None
            group.node.children.append(_node_from_block(block, "Passage"))

        for block in _iter_blocks(pdf):
            if not (block.text or "").strip():
                continue
            tag = _primary_tag(block)

            if tag in {"Header", "Footer"}:
                # 페이지 장식은 본문 그룹화·점역 walk에서 제외한다.
                # flush하지 않음 — 페이지 경계 ≠ 지문 경계.
                # root에 끼워 넣지 않음 — PassageGroup보다 앞서 직렬화되는 것을 막음.
                page_artifacts.append(
                    _node_from_block(
                        block,
                        tag,
                        confidence=0.9,
                        reading_order=block.reading_order,
                    )
                )
                continue

            if tag == "EndNotice":
                flush_group()
                orphan_question = None
                root_children.append(_node_from_block(block, tag, confidence=0.9))
                continue

            if tag == "PassageGroup":
                start_group(block)
                continue

            if tag == "Question":
                # 후보 태그만으로는 확정하지 않는다.
                # PassageGroup [start~end] 안이면 그 번호만 문항, 밖의 1. 2.는 본문.
                q_range = group.question_range if group is not None else None
                last_q = group.last_q if group is not None else None
                qnum = is_question_start(
                    block.text or "",
                    question_range=q_range,
                    last_question=last_q,
                )
                if qnum is None:
                    attach_body(block)
                    continue
                start_question(block, qnum)
                continue

            if tag == "Choice":
                target_q = current_question()
                if target_q is None:
                    unclassified.append(block.id)
                    root_children.append(
                        _node_from_block(block, "Unknown", confidence=0.0)
                    )
                else:
                    target_q.children.append(_node_from_block(block, "Choice"))
                continue

            if tag == "ExampleBox":
                q = current_question()
                if q is not None:
                    q.children.append(_node_from_block(block, "ExampleBox"))
                elif group is not None:
                    group.node.children.append(_node_from_block(block, "ExampleBox"))
                else:
                    root_children.append(_node_from_block(block, "ExampleBox"))
                continue

            if tag == "TableAsset":
                q = current_question()
                if q is not None:
                    q.children.append(_node_from_block(block, "TableAsset", confidence=0.95))
                elif group is not None:
                    group.node.children.append(
                        _node_from_block(block, "TableAsset", confidence=0.95)
                    )
                else:
                    root_children.append(
                        _node_from_block(block, "TableAsset", confidence=0.95)
                    )
                continue

            if tag == "FigureAsset":
                q = current_question()
                if q is not None:
                    q.children.append(
                        _node_from_block(block, "FigureAsset", confidence=0.9)
                    )
                elif group is not None:
                    group.node.children.append(
                        _node_from_block(block, "FigureAsset", confidence=0.9)
                    )
                else:
                    root_children.append(
                        _node_from_block(block, "FigureAsset", confidence=0.9)
                    )
                continue

            attach_body(block)

        flush_group()

        root = ExamNode(
            id="exam-root",
            node_type="ExamDocument",
            source_range=SourceRange(raw_text=pdf.source_path),
            children=root_children,
            metadata={"source_path": pdf.source_path},
        )
        exam = ExamDocument(
            root=root,
            relations=relations,
            unclassified_ids=unclassified,
            metadata={
                "builder": "RuleExamStructureBuilder",
                # Header/Footer 등 — 디버그·후속 점자 면 머리말용. 본문 트리가 아님.
                "page_artifacts": [n.to_dict() for n in page_artifacts],
            },
        )
        apply_genre_paragraph_splits(exam, pdf)
        return exam
