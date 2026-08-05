"""개발자 미리보기용 DTBook-ish XML (스키마 미확정 · preview 표시)."""

from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement, tostring

from korean_exam_braille.app.exam.models import ExamDocument, ExamNode

_LEVEL_TYPES = {
    "PassageGroup": 1,
    "Question": 2,
    "ExampleBox": 2,
    "Header": 1,
    "Footer": 1,
    "EndNotice": 1,
}


class PreviewDtbookExporter:
    """Exam 트리를 DTBook 유사 XML로 직렬화한다.

    사용자 모드 다운로드를 켜기 전 개발자 모드 B 미리보기·스키마 논의용.
    `available` 은 True이지만 출력에 preview 메타를 넣는다.
    """

    @property
    def available(self) -> bool:
        return True

    def export(self, exam: ExamDocument, *, title: str | None = None) -> str:
        book_title = title or str(exam.metadata.get("title") or "국어 시험지 (미리보기)")
        root = Element(
            "dtbook",
            {
                "version": "2005-3",
                "xml:lang": "ko",
                "xmlns": "http://www.daisy.org/z3986/2005/dtbook/",
            },
        )
        head = SubElement(root, "head")
        SubElement(head, "meta", {"name": "dtb:uid", "content": "preview-uid"})
        SubElement(
            head,
            "meta",
            {
                "name": "korean-exam-braille:status",
                "content": "preview-not-final-schema",
            },
        )
        SubElement(head, "meta", {"name": "dc:Title", "content": book_title})

        book = SubElement(root, "book")
        front = SubElement(book, "frontmatter")
        doctitle = SubElement(front, "doctitle")
        doctitle.text = book_title
        notice = SubElement(front, "level1")
        nh = SubElement(notice, "h1")
        nh.text = "미리보기"
        np = SubElement(notice, "p")
        np.text = (
            "이 파일은 DAISY용 중간 구조 미리보기이며 "
            "최종 DTBook 스키마가 아닙니다."
        )

        body = SubElement(book, "bodymatter")
        for child in exam.root.children:
            self._emit_node(body, child, level=1)
        if not exam.root.children:
            text = (exam.root.source_range.raw_text or "").strip()
            if text:
                p = SubElement(body, "p")
                p.text = text

        return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(
            root, encoding="unicode"
        )

    def _emit_node(self, parent: Element, node: ExamNode, *, level: int) -> None:
        text = (node.source_range.raw_text or "").strip()
        mapped = _LEVEL_TYPES.get(node.node_type)

        if mapped is not None or node.children:
            depth = min(max(mapped or level, 1), 6)
            el = SubElement(
                parent,
                f"level{depth}",
                {"class": node.node_type, "id": node.id},
            )
            h = SubElement(el, f"h{depth}")
            label = node.metadata.get("question_number") or node.node_type
            h.text = str(label)
            if text:
                p = SubElement(el, "p")
                p.text = text
            for child in node.children:
                self._emit_node(el, child, level=depth + 1)
            return

        el = SubElement(parent, "p", {"class": node.node_type, "id": node.id})
        if text:
            el.text = text
