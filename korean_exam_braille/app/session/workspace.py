"""사용자·개발자 셸 공용 작업 공간 — 편집 API 없음."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from korean_exam_braille.app.daisy.exporter import ExamDtbookExporter
from korean_exam_braille.app.daisy.ports import DtbookExporter
from korean_exam_braille.app.exam.models import ExamDocument
from korean_exam_braille.app.exam.tree_text import format_exam_summary, format_exam_tree
from korean_exam_braille.app.pipeline.pipeline import PipelineResult
from korean_exam_braille.app.session.pdf_structure import PdfStructureService


@dataclass
class ConversionWorkspace:
    """업로드 → 분석·변환 → BRF/DTBook 다운로드용 세션.

    제품 UI(웹 사용자 모드·개발자 진단)는 이 클래스만 호출한다.
    PDF 블록 병합/분할/태그 편집은 노출하지 않는다.
    """

    service: PdfStructureService = field(default_factory=PdfStructureService)
    # Exam → DTBook 2005-3 구조 XML (사용자 다운로드 · 개발자 미리보기 공용)
    user_dtbook: DtbookExporter = field(default_factory=ExamDtbookExporter)
    preview_dtbook: DtbookExporter = field(default_factory=ExamDtbookExporter)
    _tmpdir: tempfile.TemporaryDirectory[str] | None = field(default=None, repr=False)

    last_result: PipelineResult | None = None
    last_dtbook_xml: str | None = None
    source_name: str | None = None

    def load_pdf(self, path: str | Path) -> dict[str, object]:
        path = Path(path)
        self.service.open(path)
        self.source_name = path.name
        self.last_result = None
        self.last_dtbook_xml = None
        doc = self.service.require_document()
        return {
            "name": path.name,
            "page_count": doc.page_count,
            "extracted_pages": len(doc.pages),
        }

    def load_pdf_bytes(self, data: bytes, *, filename: str = "upload.pdf") -> dict[str, object]:
        if self._tmpdir is None:
            self._tmpdir = tempfile.TemporaryDirectory(prefix="keb-upload-")
        safe = Path(filename).name or "upload.pdf"
        if not safe.lower().endswith(".pdf"):
            safe = f"{safe}.pdf"
        path = Path(self._tmpdir.name) / safe
        path.write_bytes(data)
        return self.load_pdf(path)

    @property
    def source_path(self) -> Path | None:
        return self.service.path

    @property
    def has_pdf(self) -> bool:
        return self.service.document is not None

    @property
    def has_brf(self) -> bool:
        return self.last_result is not None and bool(self.last_result.brf_text)

    @property
    def dtbook_download_available(self) -> bool:
        return self.user_dtbook.available and self.last_result is not None

    def analyze_and_convert(self) -> PipelineResult:
        result = self.service.convert()
        self.last_result = result
        # 미리보기용 XML은 변환 직후 캐시 (개발자 B · 향후 사용자 다운로드)
        try:
            self.last_dtbook_xml = self.preview_dtbook.export(
                result.exam,
                title=self.source_name,
            )
        except Exception:  # noqa: BLE001
            self.last_dtbook_xml = None
        return result

    def brf_text(self) -> str:
        if not self.last_result:
            raise ValueError("먼저 분석 및 변환을 실행하세요.")
        return self.last_result.brf_text

    def brf_bytes(self) -> bytes:
        return self.brf_text().encode("utf-8")

    def dtbook_xml(self, *, for_user_download: bool = False) -> str:
        if not self.last_result:
            raise ValueError("먼저 분석 및 변환을 실행하세요.")
        exporter = self.user_dtbook if for_user_download else self.preview_dtbook
        if for_user_download and not exporter.available:
            raise NotImplementedError("DTBook XML 내보내기는 아직 준비 중입니다.")
        xml = exporter.export(self.last_result.exam, title=self.source_name)
        if not for_user_download:
            self.last_dtbook_xml = xml
        return xml

    def exam_document(self) -> ExamDocument:
        if self.last_result is not None:
            return self.last_result.exam
        return self.service.build_exam()

    def ensure_converted(self) -> PipelineResult:
        """변환 결과가 없으면 한 번 실행한다 (개발자 모드 진입용)."""
        if self.last_result is None:
            return self.analyze_and_convert()
        return self.last_result

    def pdf_page_numbers(self) -> list[int]:
        return self.service.page_numbers()

    def pdf_page_png(self, page_number: int, *, zoom: float = 1.5) -> bytes:
        return self.service.render_page(page_number, zoom=zoom)

    def pdf_page_text(self, page_number: int) -> str:
        """읽기 순서 블록 텍스트 (스크린 리더·검색용)."""
        page = self.service.get_page(page_number)
        blocks = sorted(page.blocks, key=lambda b: b.reading_order)
        return "\n\n".join(b.text.strip() for b in blocks if b.text.strip())

    def reverse_translation_text(self) -> str:
        """생성 BRF 전체 역점역 (면 구분 유지)."""
        return "\n\n".join(str(p["reverse"]) for p in self.braille_pages_view())

    def braille_pages_view(self) -> list[dict[str, object]]:
        """점자 면별 유니코드 점자·역점역 (ASCII는 넣지 않음)."""
        from korean_exam_braille.app.brf.ascii_braille import ascii_to_unicode
        from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line

        brf = self.brf_text()
        pages: list[dict[str, object]] = []
        for index, page in enumerate(brf.split("\x0c"), start=1):
            raw_lines = page.splitlines()
            # 끝 빈 면 스킵
            if not any(line.strip() for line in raw_lines):
                continue
            uni_lines: list[str] = []
            rev_lines: list[str] = []
            for line in raw_lines:
                if line.strip() == "":
                    uni_lines.append("")
                    rev_lines.append("")
                else:
                    uni_lines.append(ascii_to_unicode(line))
                    rev_lines.append(reverse_translate_line(line))
            pages.append(
                {
                    "index": index,
                    "unicode": "\n".join(uni_lines),
                    "reverse": "\n".join(rev_lines),
                }
            )
        return pages

    def exam_tree_text(self) -> str:
        exam = self.exam_document()
        return format_exam_summary(exam) + "\n\n" + format_exam_tree(exam)

    def pdf_page_payload(self, page_number: int) -> dict[str, object]:
        """면 텍스트·크기·블록 bbox (하이라이트용)."""
        page = self.service.get_page(page_number)
        blocks = sorted(page.blocks, key=lambda b: b.reading_order)
        return {
            "page_number": page_number,
            "text": "\n\n".join(b.text.strip() for b in blocks if b.text.strip()),
            "width": page.width,
            "height": page.height,
            "blocks": [
                {
                    "id": b.id,
                    "bbox": [b.bbox[0], b.bbox[1], b.bbox[2], b.bbox[3]],
                }
                for b in blocks
            ],
        }

    def exam_tree_nodes(self) -> dict[str, object]:
        """접근성 트리용 JSON (PDF 연동 메타 포함)."""

        def walk(node) -> dict[str, object]:
            raw = (node.source_range.raw_text or "").replace("\n", " ").strip()
            if len(raw) > 120:
                raw = raw[:119] + "…"
            label = node.node_type
            qn = node.metadata.get("question_number")
            if qn is not None:
                label = f"{node.node_type} #{qn}"
            return {
                "id": node.id,
                "type": node.node_type,
                "label": label,
                "text": raw,
                "page_number": node.source_range.page_number,
                "block_ids": list(node.source_range.block_ids),
                "children": [walk(c) for c in node.children],
            }

        exam = self.exam_document()
        return {
            "summary": format_exam_summary(exam),
            "root": walk(exam.root),
        }

    def developer_bundle(self, *, page_number: int | None = None) -> dict[str, object]:
        """개발자 A/B용 전체 스냅샷 — 면 전환은 클라이언트가 캐시에서 처리."""
        if not self.has_pdf:
            raise ValueError("PDF를 먼저 업로드하세요.")
        self.ensure_converted()
        pages = self.pdf_page_numbers()
        page = page_number if page_number in pages else (pages[0] if pages else 1)
        pdf_pages = [self.pdf_page_payload(n) for n in pages]
        braille_pages = self.braille_pages_view()
        return {
            "status": self.status_snapshot(),
            "page_number": page,
            "page_numbers": pages,
            "pdf_pages": pdf_pages,
            "braille_pages": braille_pages,
            "braille_page_index": 1 if braille_pages else 0,
            "exam_tree_text": self.exam_tree_text(),
            "exam_tree": self.exam_tree_nodes(),
            "dtbook_xml": self.dtbook_xml(for_user_download=False),
            "warnings": list(self.last_result.warnings) if self.last_result else [],
        }

    def status_snapshot(self) -> dict[str, object]:
        return {
            "has_pdf": self.has_pdf,
            "source_name": self.source_name,
            "has_brf": self.has_brf,
            "dtbook_download_available": self.dtbook_download_available,
            "warnings": list(self.last_result.warnings) if self.last_result else [],
            "brf_pages": (
                len(self.last_result.braille_document.pages) if self.last_result else 0
            ),
        }

    def close(self) -> None:
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
            self._tmpdir = None
