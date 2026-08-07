"""사용자·개발자 셸 공용 작업 공간 — 편집 API 없음."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from korean_exam_braille.app.daisy.exporter import ExamDtbookExporter
from korean_exam_braille.app.daisy.ports import DtbookExporter
from korean_exam_braille.app.exam.models import ExamDocument
from korean_exam_braille.app.exam.tree_text import format_exam_summary, format_exam_tree
from korean_exam_braille.app.pdf.display_text import format_page_text_for_display
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
    generated_brf_text: str | None = None
    generated_name: str | None = None
    reference_brf_text: str | None = None
    reference_name: str | None = None

    def load_pdf(self, path: str | Path) -> dict[str, object]:
        path = Path(path)
        self.service.open(path)
        self.source_name = path.name
        self.last_result = None
        self.last_dtbook_xml = None
        self.generated_brf_text = None
        self.generated_name = None
        self.reference_brf_text = None
        self.reference_name = None
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
        """읽기 순서 블록 텍스트 (스크린 리더·검색·추출 창용).

        부분 밑줄은 ``<u>…</u>`` 로 표시한다 (변환용 블록에도 동일 마커가 들어가며,
        점역기는 강조부호 ``,-`` … ``-'`` 로 바꾼다).
        """
        page = self.service.get_page(page_number)
        return format_page_text_for_display(page)

    def reverse_translation_text(self) -> str:
        """생성 BRF 전체 역점역 (면 구분 유지)."""
        return "\n\n".join(str(p["reverse"]) for p in self.braille_pages_view())

    @property
    def has_generated_brf(self) -> bool:
        return bool(self.generated_brf_text) or self.has_brf

    @property
    def has_reference_brf(self) -> bool:
        return bool(self.reference_brf_text)

    def _brf_meta(self, text: str, name: str) -> dict[str, object]:
        from korean_exam_braille.app.session.review import brf_text_to_display_pages

        pages = brf_text_to_display_pages(text)
        return {
            "name": name,
            "pages": len(pages),
            "lines": sum(len(p["unicode_lines"]) for p in pages),  # type: ignore[arg-type]
        }

    def load_generated_brf_bytes(
        self, data: bytes, *, filename: str = "generated.brf"
    ) -> dict[str, object]:
        text = data.decode("utf-8", errors="replace")
        if not text.strip():
            raise ValueError("빈 BRF 파일입니다.")
        self.generated_brf_text = text
        self.generated_name = Path(filename).name or "generated.brf"
        return self._brf_meta(text, self.generated_name)

    def load_reference_brf_bytes(
        self, data: bytes, *, filename: str = "reference.brf"
    ) -> dict[str, object]:
        text = data.decode("utf-8", errors="replace")
        if not text.strip():
            raise ValueError("빈 BRF 파일입니다.")
        self.reference_brf_text = text
        self.reference_name = Path(filename).name or "reference.brf"
        return self._brf_meta(text, self.reference_name)

    def review_generated_brf_text(self) -> str:
        """검토용 생성측 BRF — 업로드본 우선, 없으면 변환 결과."""
        if self.generated_brf_text:
            return self.generated_brf_text
        if self.has_brf:
            return self.brf_text()
        raise ValueError(
            "생성 BRF를 업로드하거나 사용자 모드에서 PDF를 변환하세요."
        )

    def braille_pages_view(self) -> list[dict[str, object]]:
        """점자 면별 유니코드 점자·역점역 (ASCII는 넣지 않음)."""
        from korean_exam_braille.app.session.review import brf_text_to_display_pages

        return brf_text_to_display_pages(self.brf_text())

    def _exam_node_pdf_page_map(self) -> dict[str, int]:
        """Exam 노드 id → PDF 면 번호."""
        mapping: dict[str, int] = {}

        def walk(node) -> None:
            pn = node.source_range.page_number
            if pn is not None:
                mapping[node.id] = int(pn)
            for child in node.children:
                walk(child)

        walk(self.exam_document().root)
        return mapping

    def braille_pages_linked_to_pdf(self) -> tuple[list[dict[str, object]], dict[str, list[int]]]:
        """점자 표시 면 + PDF 면번호 → 점자 면 인덱스 목록.

        레이아웃 줄의 ``source_node_ids``와 Exam ``page_number``로 매핑한다.
        매핑이 비면 비례 분할로 폴백해 점자 면이 UI에서 유실되지 않게 한다.
        """
        from korean_exam_braille.app.session.review import brf_text_to_display_pages

        display = brf_text_to_display_pages(self.brf_text())
        pdf_nums = self.pdf_page_numbers()
        id_to_pdf = self._exam_node_pdf_page_map()

        layout_nonempty = []
        if self.last_result is not None:
            for page in self.last_result.braille_document.pages:
                if any((ln.ascii_text or "").strip() for ln in page.lines):
                    layout_nonempty.append(page)

        for i, disp in enumerate(display):
            pdfs: set[int] = set()
            if i < len(layout_nonempty):
                for line in layout_nonempty[i].lines:
                    for nid in line.source_node_ids:
                        if nid and nid in id_to_pdf:
                            pdfs.add(id_to_pdf[nid])
            disp["pdf_page_numbers"] = sorted(pdfs)
            disp["braille_index"] = i

        # 구분선만 있는 면 등: 앞·뒤 배정 면으로 채움
        last: list[int] | None = None
        for disp in display:
            nums = list(disp["pdf_page_numbers"])  # type: ignore[arg-type]
            if nums:
                last = nums
            elif last is not None:
                disp["pdf_page_numbers"] = list(last)
        last = None
        for disp in reversed(display):
            nums = list(disp["pdf_page_numbers"])  # type: ignore[arg-type]
            if nums:
                last = nums
            elif last is not None:
                disp["pdf_page_numbers"] = list(last)

        # 전면 미매핑이면 점자 면을 PDF 면에 비례 배분
        if display and pdf_nums and all(not d["pdf_page_numbers"] for d in display):
            n_brl = len(display)
            n_pdf = len(pdf_nums)
            for i, disp in enumerate(display):
                pi = min(n_pdf - 1, (i * n_pdf) // max(n_brl, 1))
                disp["pdf_page_numbers"] = [pdf_nums[pi]]

        pdf_to_braille: dict[str, list[int]] = {str(n): [] for n in pdf_nums}
        assigned: set[int] = set()
        for i, disp in enumerate(display):
            for pn in disp["pdf_page_numbers"]:  # type: ignore[union-attr]
                key = str(pn)
                if key in pdf_to_braille:
                    pdf_to_braille[key].append(i)
                    assigned.add(i)
        orphans = [i for i in range(len(display)) if i not in assigned]
        if orphans and pdf_nums:
            key = str(pdf_nums[-1])
            pdf_to_braille.setdefault(key, []).extend(orphans)
            for i in orphans:
                display[i]["pdf_page_numbers"] = [pdf_nums[-1]]

        for key, indices in pdf_to_braille.items():
            pdf_to_braille[key] = sorted(set(indices))

        return display, pdf_to_braille

    def review_bundle(
        self,
        *,
        on_progress=None,
    ) -> dict[str, object]:
        """생성 BRF ↔ 참고 BRF 검토 스냅샷 (생성 면 기준 창 배정)."""
        generated = self.review_generated_brf_text()
        if not self.reference_brf_text:
            raise ValueError("참고 BRF를 먼저 업로드하세요.")
        from korean_exam_braille.app.session.review import build_review_pages

        built = build_review_pages(
            generated,
            self.reference_brf_text,
            on_progress=on_progress,
        )
        gen_name = self.generated_name
        if not gen_name and self.has_brf:
            gen_name = (self.source_name or "exam").rsplit(".", 1)[0] + ".brf"
        return {
            "status": self.status_snapshot(),
            "generated_name": gen_name or "generated.brf",
            "reference_name": self.reference_name,
            **built,
        }

    def exam_tree_text(self) -> str:
        exam = self.exam_document()
        return format_exam_summary(exam) + "\n\n" + format_exam_tree(exam)

    def pdf_page_payload(self, page_number: int) -> dict[str, object]:
        """면 텍스트·크기·블록 bbox (하이라이트용)."""
        page = self.service.get_page(page_number)
        blocks = sorted(page.blocks, key=lambda b: b.reading_order)
        return {
            "page_number": page_number,
            "text": format_page_text_for_display(page),
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
        braille_pages, pdf_to_braille = self.braille_pages_linked_to_pdf()
        return {
            "status": self.status_snapshot(),
            "page_number": page,
            "page_numbers": pages,
            "pdf_pages": pdf_pages,
            "braille_pages": braille_pages,
            "pdf_to_braille": pdf_to_braille,
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
            "has_generated_brf": self.has_generated_brf,
            "generated_name": self.generated_name
            or (
                (self.source_name or "exam").rsplit(".", 1)[0] + ".brf"
                if self.has_brf
                else None
            ),
            "has_reference_brf": self.has_reference_brf,
            "reference_name": self.reference_name,
            "warnings": list(self.last_result.warnings) if self.last_result else [],
            "brf_pages": (
                len(self.last_result.braille_document.pages) if self.last_result else 0
            ),
        }

    def close(self) -> None:
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
            self._tmpdir = None
