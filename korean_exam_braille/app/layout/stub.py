"""레이아웃·직렬화 스텁."""

from __future__ import annotations

from korean_exam_braille.app.braille.models import BrailleSequence
from korean_exam_braille.app.layout.models import (
    BrailleDocument,
    BrailleLine,
    BraillePage,
    LayoutProfile,
)


class StubBrailleLayoutEngine:
    """토큰의 source_text를 그대로 한 줄씩 넣는 자리표시."""

    def layout(
        self,
        sequences: list[BrailleSequence],
        *,
        profile: LayoutProfile | None = None,
    ) -> BrailleDocument:
        prof = profile or LayoutProfile()
        lines: list[BrailleLine] = []
        for seq in sequences:
            text = "".join(t.source_text for t in seq.tokens)
            for raw_line in (text.splitlines() or [""]):
                lines.append(
                    BrailleLine(
                        cells=[],
                        source_node_ids=[seq.source_node_id] if seq.source_node_id else [],
                        ascii_text=raw_line,
                    )
                )
        # 면 분할 (줄 수 기준)
        usable = max(1, prof.lines_per_page - prof.top_margin - prof.bottom_margin)
        pages: list[BraillePage] = []
        for i in range(0, max(len(lines), 1), usable):
            chunk = lines[i : i + usable]
            pages.append(BraillePage(page_index=len(pages), lines=chunk))
        if not pages:
            pages.append(BraillePage(page_index=0, lines=[]))
        return BrailleDocument(
            pages=pages,
            profile=prof,
            metadata={"layout": "StubBrailleLayoutEngine"},
        )


class StubBrfSerializer:
    """ASCII 미리보기 텍스트로 직렬화 (점자 셀 미사용)."""

    def serialize(self, document: BrailleDocument) -> str:
        page_texts: list[str] = []
        for page in document.pages:
            page_texts.append("\n".join(ln.ascii_text for ln in page.lines))
        return "\x0c".join(page_texts)
