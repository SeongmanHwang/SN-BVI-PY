"""PDF 구조 진단·편집·변환 세션 — Qt 없이 UI 셸이 쓰는 경계."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from korean_exam_braille.app.brf.exam_diff import ExamDiffReport, compare_exam_content
from korean_exam_braille.app.exam.builder import RuleExamStructureBuilder
from korean_exam_braille.app.exam.models import ExamDocument
from korean_exam_braille.app.exam.ports import ExamStructureBuilder
from korean_exam_braille.app.nav import TreeExamNavigator
from korean_exam_braille.app.nav.ports import ExamNavigator
from korean_exam_braille.app.pdf.adapter import DefaultPdfStructureExtractor
from korean_exam_braille.app.pdf.block_builder import merge_blocks, split_block
from korean_exam_braille.app.pdf.candidates import detect_block_candidates
from korean_exam_braille.app.pdf.extractor import render_page_pixmap
from korean_exam_braille.app.pdf.io import save_structure
from korean_exam_braille.app.pdf.models import PdfBlock, PdfDocumentStructure, PdfPageStructure
from korean_exam_braille.app.pdf.ports import PdfStructureExtractor
from korean_exam_braille.app.pdf.reading_order import assign_reading_order, move_block_order
from korean_exam_braille.app.pipeline.pipeline import ConversionPipeline, PipelineResult, default_pipeline


@dataclass
class PdfStructureService:
    """열린 PDF 구조 문서를 보유하고 편집·탐색·변환을 제공한다.

    UI는 파일 대화상자·메시지 박스·렌더 위젯만 담당하고, 이 클래스만 호출한다.
    """

    extractor: PdfStructureExtractor = field(default_factory=DefaultPdfStructureExtractor)
    exam_builder: ExamStructureBuilder = field(default_factory=RuleExamStructureBuilder)
    pipeline_factory: Callable[[], ConversionPipeline] = field(default=default_pipeline)
    navigator_factory: Callable[[], ExamNavigator] = field(default=TreeExamNavigator)

    path: Path | None = None
    document: PdfDocumentStructure | None = None

    def open(self, path: str | Path) -> PdfDocumentStructure:
        path = Path(path)
        self.document = self.extractor.extract(path)
        self.path = path
        return self.document

    def require_document(self) -> PdfDocumentStructure:
        if self.document is None:
            raise ValueError("PDF가 열려 있지 않습니다.")
        return self.document

    def require_path(self) -> Path:
        if self.path is None:
            raise ValueError("PDF 경로가 없습니다.")
        return self.path

    def get_page(self, page_number: int) -> PdfPageStructure:
        return self.require_document().get_page(page_number)

    def page_numbers(self) -> list[int]:
        return [p.page_number for p in self.require_document().pages]

    def save(self) -> Path:
        doc = self.require_document()
        self.require_path()
        return save_structure(doc)

    def render_page(self, page_number: int, *, zoom: float = 2.0) -> bytes:
        return render_page_pixmap(self.require_path(), page_number, zoom=zoom)

    def layout_status_extra(self) -> str:
        """상태줄용 레이아웃 요약 (없으면 빈 문자열)."""
        doc = self.require_document()
        layout = (doc.metadata or {}).get("layout_profile") or {}
        cut = layout.get("column_cut_x")
        if isinstance(cut, (int, float)):
            return f" · cut={cut:.0f}"
        return ""

    def find_block(self, page_number: int, block_id: str) -> PdfBlock | None:
        page = self.get_page(page_number)
        return next((b for b in page.blocks if b.id == block_id), None)

    def set_block_tags(
        self,
        page_number: int,
        block_id: str,
        tags: list[str],
        *,
        known_tags: frozenset[str] | set[str],
    ) -> list[str]:
        """태그 설정. 알려진 목록에 없는 태그를 반환한다."""
        block = self.find_block(page_number, block_id)
        if block is None:
            raise KeyError(block_id)
        block.tags = list(tags)
        return [t for t in tags if t not in known_tags]

    def set_block_notes(self, page_number: int, block_id: str, note: str | None) -> None:
        block = self.find_block(page_number, block_id)
        if block is None:
            raise KeyError(block_id)
        block.notes = note or None

    def accept_candidates(self, page_number: int) -> int:
        """후보 태그를 비어 있는 tags에 적용. 적용한 블록 수를 반환."""
        page = self.get_page(page_number)
        applied = 0
        for block in page.blocks:
            if block.candidate_tags and not block.tags:
                block.tags = list(block.candidate_tags)
                applied += 1
        return applied

    def merge_selected(self, page_number: int, left_id: str, right_id: str) -> None:
        page = self.get_page(page_number)
        page.blocks = merge_blocks(page.blocks, left_id, right_id)
        self._refresh_candidates(page)

    def split_block_mid(self, page_number: int, block_id: str) -> None:
        """블록 행 목록의 중간에서 분할."""
        page = self.get_page(page_number)
        block = next((b for b in page.blocks if b.id == block_id), None)
        if block is None:
            raise KeyError(block_id)
        if len(block.line_ids) < 2:
            raise ValueError("행이 2개 이상인 블록만 분할할 수 있습니다.")
        mid = block.line_ids[len(block.line_ids) // 2 - 1]
        left, right = split_block(block, page.lines, mid)
        new_blocks: list[PdfBlock] = []
        for b in page.blocks:
            if b.id == block.id:
                new_blocks.append(left)
                new_blocks.append(right)
            else:
                new_blocks.append(b)
        page.blocks = assign_reading_order(new_blocks)
        self._refresh_candidates(page)

    def nudge_order(self, page_number: int, block_id: str, delta: int) -> None:
        page = self.get_page(page_number)
        block = next((b for b in page.blocks if b.id == block_id), None)
        if block is None:
            raise KeyError(block_id)
        page.blocks = move_block_order(page.blocks, block.id, block.reading_order + delta)

    def build_exam(self) -> ExamDocument:
        return self.exam_builder.build(self.require_document())

    def create_navigator(self) -> tuple[ExamNavigator, ExamDocument]:
        """Exam을 빌드하고 새 Navigator를 만든다 (패널 bind용)."""
        exam = self.build_exam()
        nav = self.navigator_factory()
        return nav, exam

    def convert(self) -> PipelineResult:
        """편집된 문서로 파이프라인 이후 단계만 실행."""
        doc = self.require_document()
        meta = {"pdf_path": str(self.path) if self.path else None}
        return self.pipeline_factory().run_document(doc, metadata=meta)

    def compare_content(self, reference_brf: str | Path) -> ExamDiffReport:
        result = self.convert()
        return compare_exam_content(result.brf_text, Path(reference_brf))

    @staticmethod
    def _refresh_candidates(page: PdfPageStructure) -> None:
        for block in page.blocks:
            block.candidate_tags = detect_block_candidates(block.text)
        assign_reading_order(page.blocks)
