"""ExamDocument → DTBook 2005-3 구조 XML (DAISY 중간 원고)."""

from __future__ import annotations

import hashlib
import re
from xml.etree.ElementTree import Element, SubElement, tostring

from korean_exam_braille.app.exam.bracket_metadata import bracket_labels
from korean_exam_braille.app.exam.models import ExamDocument, ExamNode

_NS = "http://www.daisy.org/z3986/2005/dtbook/"
_DOCTYPE = (
    '<!DOCTYPE dtbook PUBLIC "-//NISO//DTD dtbook 2005-3//EN" '
    '"http://www.daisy.org/z3986/2005/dtbook-2005-3.dtd">'
)

# 계층(level)으로 올릴 Exam 타입
_LEVEL1 = frozenset({"PassageGroup", "Header", "Footer", "EndNotice"})
_LEVEL2 = frozenset({"Question", "ExampleBox"})
# 문단으로 낼 타입
_PARAGRAPH = frozenset(
    {
        "Passage",
        "Prompt",
        "Choice",
        "Footnote",
        "Body",
        "Unknown",
    }
)


def _xml_id(raw: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_\-.]", "_", raw or "node")
    if not cleaned or cleaned[0].isdigit() or cleaned[0] in ".-":
        cleaned = "n_" + cleaned
    return cleaned[:120]


def _heading_for(node: ExamNode) -> str:
    qn = node.metadata.get("question_number")
    if qn is not None:
        return f"문항 {qn}"
    start = node.metadata.get("start_question")
    end = node.metadata.get("end_question")
    if start is not None and end is not None:
        return f"지문 [{start}~{end}]"
    labels = {
        "PassageGroup": "지문",
        "Question": "문항",
        "ExampleBox": "보기",
        "Header": "머리말",
        "Footer": "바닥글",
        "EndNotice": "끝 안내",
    }
    return labels.get(node.node_type, node.node_type)


def _text_of(node: ExamNode) -> str:
    """노드 원문. 점역용 ``<u>`` 마커는 DTBook에 넣지 않는다."""
    raw = (node.source_range.raw_text or "").strip()
    return re.sub(r"</?u>", "", raw)


class ExamDtbookExporter:
    """수능 Exam 트리를 DTBook 2005-3 XML로보낸다.

    DAISY 패키지(SMIL·오디오·NCX)는 만들지 않는다.
    사용자가 DAISY 제작 도구에 넣을 **중간 구조 원고**이다.
    """

    @property
    def available(self) -> bool:
        return True

    def export(self, exam: ExamDocument, *, title: str | None = None) -> str:
        book_title = title or str(exam.metadata.get("title") or "국어 시험지")
        uid = "keb-" + hashlib.sha1(book_title.encode("utf-8")).hexdigest()[:16]

        root = Element(
            "dtbook",
            {
                "version": "2005-3",
                "xmlns": _NS,
                "xml:lang": "ko",
            },
        )
        head = SubElement(root, "head")
        SubElement(head, "meta", {"name": "dtb:uid", "content": uid})
        SubElement(head, "meta", {"name": "dc:Title", "content": book_title})
        SubElement(head, "meta", {"name": "dc:Language", "content": "ko"})
        SubElement(
            head,
            "meta",
            {
                "name": "korean-exam-braille:format",
                "content": "dtbook-2005-3-structure",
            },
        )

        book = SubElement(root, "book")
        front = SubElement(book, "frontmatter")
        doctitle = SubElement(front, "doctitle")
        doctitle.text = book_title

        body = SubElement(book, "bodymatter")
        rear_nodes: list[ExamNode] = []

        children = list(exam.root.children)
        if not children and _text_of(exam.root):
            p = SubElement(body, "p", {"id": _xml_id(exam.root.id)})
            p.text = _text_of(exam.root)
        else:
            for child in children:
                if child.node_type in {"Footer", "EndNotice"}:
                    rear_nodes.append(child)
                    continue
                if child.node_type == "Header":
                    self._emit_level(front, child, depth=1)
                    continue
                self._emit_node(body, child, depth=1)

        if rear_nodes:
            rear = SubElement(book, "rearmatter")
            for node in rear_nodes:
                self._emit_level(rear, node, depth=1)

        xml_body = tostring(root, encoding="unicode")
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            + _DOCTYPE
            + "\n"
            + xml_body
        )

    def _emit_node(self, parent: Element, node: ExamNode, *, depth: int) -> None:
        self._emit_bracket_markers(parent, node)
        self._emit_node_body(parent, node, depth=depth)
        self._emit_bracket_end_markers(parent, node)

    def _emit_node_body(self, parent: Element, node: ExamNode, *, depth: int) -> None:
        ntype = node.node_type
        if ntype == "Question":
            self._emit_question(parent, node, depth=min(max(depth, 2), 6))
            return
        if ntype == "ExampleBox":
            self._emit_level(parent, node, depth=min(max(depth, 2), 6))
            return
        if ntype == "PassageGroup" or ntype in _LEVEL1:
            self._emit_level(parent, node, depth=1)
            return
        if ntype == "Choice":
            # 문항 밖 고아 선택지
            p = SubElement(
                parent,
                "p",
                {"class": "Choice", "id": _xml_id(node.id)},
            )
            p.text = _text_of(node) or None
            return
        if ntype in _PARAGRAPH or (not node.children and _text_of(node)):
            attrs = {"id": _xml_id(node.id)}
            if ntype not in {"Passage", "Prompt", "Body"}:
                attrs["class"] = ntype
            p = SubElement(parent, "p", attrs)
            text = _text_of(node)
            if text:
                p.text = text
            for child in node.children:
                self._emit_node(parent, child, depth=depth)
            return

        # 기타: 레벨로 감싸 자식 유지
        self._emit_level(parent, node, depth=min(max(depth, 1), 6))

    def _emit_bracket_markers(self, parent: Element, node: ExamNode) -> None:
        """BRF와 같은 Exam 메타를 사용해 구간 시작 표지를 XML에 낸다."""
        for index, label in enumerate(
            bracket_labels(node.metadata, starts_only=True),
            start=1,
        ):
            marker = SubElement(
                parent,
                "p",
                {
                    "class": "BracketLabel",
                    "id": _xml_id(f"{node.id}-bracket-{index}"),
                },
            )
            marker.text = f"┌──── {label} ─────────────────┐"

    def _emit_bracket_end_markers(self, parent: Element, node: ExamNode) -> None:
        """BRF와 같은 Exam 메타를 사용해 구간 종료 표지를 XML에 낸다."""
        for index, label in enumerate(
            bracket_labels(node.metadata, ends_only=True),
            start=1,
        ):
            marker = SubElement(
                parent,
                "p",
                {
                    "class": "BracketEndLabel",
                    "id": _xml_id(f"{node.id}-bracket-end-{index}"),
                },
            )
            marker.text = "└──────────────────────────────┘"

    def _emit_level(self, parent: Element, node: ExamNode, *, depth: int) -> None:
        depth = min(max(depth, 1), 6)
        el = SubElement(
            parent,
            f"level{depth}",
            {"class": node.node_type, "id": _xml_id(node.id)},
        )
        h = SubElement(el, f"h{depth}")
        h.text = _heading_for(node)
        text = _text_of(node)
        if text:
            p = SubElement(el, "p")
            p.text = text
        # 선택지만 모이면 list로
        choices = [c for c in node.children if c.node_type == "Choice"]
        others = [c for c in node.children if c.node_type != "Choice"]
        for child in others:
            self._emit_node(el, child, depth=depth + 1)
        if choices:
            self._emit_choice_list(el, choices)

    def _emit_question(self, parent: Element, node: ExamNode, *, depth: int) -> None:
        depth = min(max(depth, 2), 6)
        el = SubElement(
            parent,
            f"level{depth}",
            {"class": "Question", "id": _xml_id(node.id)},
        )
        h = SubElement(el, f"h{depth}")
        h.text = _heading_for(node)

        prompts = [
            c
            for c in node.children
            if c.node_type in {"Prompt", "Passage", "Body"} or c.node_type == "Unknown"
        ]
        choices = [c for c in node.children if c.node_type == "Choice"]
        others = [
            c
            for c in node.children
            if c not in prompts and c not in choices
        ]

        text = _text_of(node)
        if text:
            p = SubElement(el, "p", {"class": "Prompt"})
            p.text = text
        for child in prompts:
            self._emit_bracket_markers(el, child)
            p = SubElement(el, "p", {"class": child.node_type, "id": _xml_id(child.id)})
            t = _text_of(child)
            if t:
                p.text = t
            self._emit_bracket_end_markers(el, child)
        for child in others:
            self._emit_node(el, child, depth=depth + 1)
        if choices:
            self._emit_choice_list(el, choices)

    def _emit_choice_list(self, parent: Element, choices: list[ExamNode]) -> None:
        lst = SubElement(parent, "list", {"type": "pl", "class": "Choices"})
        for choice in choices:
            li = SubElement(lst, "li", {"id": _xml_id(choice.id)})
            self._emit_bracket_markers(li, choice)
            p = SubElement(li, "p", {"class": "Choice"})
            text = _text_of(choice)
            if text:
                p.text = text
            self._emit_bracket_end_markers(li, choice)


# 하위 호환 별칭 (개발자 미리보기 경로)
class PreviewDtbookExporter(ExamDtbookExporter):
    """ExamDtbookExporter와 동일 — 이전 import 경로 유지."""
