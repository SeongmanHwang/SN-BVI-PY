"""PDF Structure Viewer — 페이지 렌더 + 블록 오버레이."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QAction, QColor, QImage, QKeySequence, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from korean_exam_braille.app.brf.models import STRUCTURE_TAGS
from korean_exam_braille.app.pdf.block_builder import merge_blocks, split_block
from korean_exam_braille.app.pdf.candidates import detect_block_candidates
from korean_exam_braille.app.pdf.extractor import extract_pdf, render_page_pixmap
from korean_exam_braille.app.pdf.io import save_structure
from korean_exam_braille.app.pdf.models import PdfDocumentStructure, PdfPageStructure
from korean_exam_braille.app.pdf.reading_order import assign_reading_order, move_block_order
from korean_exam_braille.app.ui import mode_switch

_TAG_COLORS = {
    "Question": QColor(220, 60, 60, 70),
    "Choice": QColor(40, 120, 220, 70),
    "ExampleBox": QColor(200, 140, 20, 70),
    "PassageGroup": QColor(80, 160, 80, 70),
    "Footnote": QColor(140, 80, 180, 70),
    "EndNotice": QColor(100, 100, 100, 70),
    "Header": QColor(120, 120, 120, 55),
    "Footer": QColor(120, 120, 120, 55),
}
_DEFAULT_FILL = QColor(30, 144, 255, 40)
_SELECTED_PEN = QPen(QColor(255, 80, 0), 2.0)


class PdfCanvas(QGraphicsView):
    blockClicked = Signal(str)
    viewScaleChanged = Signal(float)

    _MIN_VIEW_SCALE = 0.25
    _MAX_VIEW_SCALE = 6.0

    def __init__(self) -> None:
        super().__init__()
        self.setRenderHints(
            self.renderHints()
            | QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._overlay_items: dict[str, QGraphicsRectItem] = {}
        self._render_zoom = 2.0
        self._view_scale = 1.0
        self._fit_mode = True
        self._page_height = 1.0

    @property
    def view_scale(self) -> float:
        return self._view_scale

    def set_page_image(
        self,
        png_bytes: bytes,
        page_height_pt: float,
        render_zoom: float,
        *,
        keep_view: bool = False,
    ) -> None:
        self._render_zoom = render_zoom
        self._page_height = page_height_pt
        image = QImage.fromData(png_bytes, "PNG")
        pix = QPixmap.fromImage(image)
        self._scene.clear()
        self._overlay_items.clear()
        self._pixmap_item = self._scene.addPixmap(pix)
        self._scene.setSceneRect(QRectF(pix.rect()))
        if keep_view and not self._fit_mode:
            self._apply_view_scale(self._view_scale)
        else:
            self.fit_page()

    def fit_page(self) -> None:
        self._fit_mode = True
        if self._scene.sceneRect().isEmpty():
            return
        self.resetTransform()
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        # fitInView 후 실제 배율 추정
        sx = self.transform().m11()
        self._view_scale = max(self._MIN_VIEW_SCALE, min(self._MAX_VIEW_SCALE, sx))
        self.viewScaleChanged.emit(self._view_scale)

    def reset_zoom(self) -> None:
        """렌더 해상도 기준 1:1에 가깝게."""
        self._fit_mode = False
        self._apply_view_scale(1.0)

    def zoom_by(self, factor: float) -> None:
        self._fit_mode = False
        self._apply_view_scale(self._view_scale * factor)

    def set_view_scale(self, scale: float) -> None:
        self._fit_mode = False
        self._apply_view_scale(scale)

    def _apply_view_scale(self, scale: float) -> None:
        scale = max(self._MIN_VIEW_SCALE, min(self._MAX_VIEW_SCALE, scale))
        self._view_scale = scale
        self.resetTransform()
        self.scale(scale, scale)
        self.viewScaleChanged.emit(self._view_scale)

    def set_overlays(
        self,
        boxes: list[tuple[str, tuple[float, float, float, float], list[str], int]],
        *,
        selected_id: str | None,
        show: bool,
    ) -> None:
        for item in self._overlay_items.values():
            self._scene.removeItem(item)
        self._overlay_items.clear()
        if not show:
            return
        z = self._render_zoom
        for block_id, bbox, tags, order in boxes:
            x0, y0, x1, y1 = bbox
            rect = QRectF(x0 * z, y0 * z, (x1 - x0) * z, (y1 - y0) * z)
            item = QGraphicsRectItem(rect)
            fill = _DEFAULT_FILL
            for tag in tags:
                if tag in _TAG_COLORS:
                    fill = _TAG_COLORS[tag]
                    break
            item.setBrush(fill)
            item.setPen(_SELECTED_PEN if block_id == selected_id else QPen(QColor(30, 90, 180), 1.0))
            item.setData(0, block_id)
            item.setToolTip(f"#{order} {block_id}\n{', '.join(tags) or '-'}")
            self._scene.addItem(item)
            self._overlay_items[block_id] = item

    def wheelEvent(self, event) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_by(1.15)
            elif delta < 0:
                self.zoom_by(1 / 1.15)
            event.accept()
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(event.position().toPoint())
            for block_id, item in self._overlay_items.items():
                if item.contains(item.mapFromScene(pos)):
                    self.blockClicked.emit(block_id)
                    break
        super().mousePressEvent(event)


class PdfStructureWindow(QMainWindow):
    def __init__(self, initial_path: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("PDF Structure Viewer — 수능 국어")
        self.resize(1400, 860)

        self.pdf_path: Path | None = None
        self.document: PdfDocumentStructure | None = None
        self._page_number = 1
        self._render_zoom = 2.0
        self._selected_block_id: str | None = None
        self._updating = False
        self._keep_view_on_refresh = False

        self._build_actions()
        self._build_menu()
        self._build_toolbar()
        self._build_ui()
        self.setStatusBar(QStatusBar())

        if initial_path:
            self.open_path(Path(initial_path))

    def _build_actions(self) -> None:
        self.act_open = QAction("열기…", self)
        self.act_open.setShortcut(QKeySequence.Open)
        self.act_open.triggered.connect(self.open_file_dialog)

        self.act_save = QAction("구조 저장", self)
        self.act_save.setShortcut(QKeySequence.Save)
        self.act_save.triggered.connect(self.save_structure)

        self.act_prev = QAction("이전 면", self)
        self.act_prev.setShortcut(QKeySequence.MoveToPreviousPage)
        self.act_prev.triggered.connect(self.prev_page)

        self.act_next = QAction("다음 면", self)
        self.act_next.setShortcut(QKeySequence.MoveToNextPage)
        self.act_next.triggered.connect(self.next_page)

        self.act_merge = QAction("선택 블록 병합", self)
        self.act_merge.triggered.connect(self.merge_selected)

        self.act_split = QAction("선택 블록 분할(중간)", self)
        self.act_split.triggered.connect(self.split_selected)

        self.act_accept = QAction("후보→태그 적용", self)
        self.act_accept.triggered.connect(self.accept_candidates)

        self.act_reorder_up = QAction("읽기순서 ↑", self)
        self.act_reorder_up.triggered.connect(lambda: self.nudge_order(-1))
        self.act_reorder_down = QAction("읽기순서 ↓", self)
        self.act_reorder_down.triggered.connect(lambda: self.nudge_order(1))

        self.act_zoom_in = QAction("확대", self)
        self.act_zoom_in.setShortcut(QKeySequence.ZoomIn)
        self.act_zoom_in.triggered.connect(lambda: self.canvas.zoom_by(1.25))

        self.act_zoom_out = QAction("축소", self)
        self.act_zoom_out.setShortcut(QKeySequence.ZoomOut)
        self.act_zoom_out.triggered.connect(lambda: self.canvas.zoom_by(1 / 1.25))

        self.act_zoom_fit = QAction("맞춤", self)
        self.act_zoom_fit.setShortcut(QKeySequence("Ctrl+0"))
        self.act_zoom_fit.triggered.connect(self.zoom_fit)

        self.act_zoom_100 = QAction("100%", self)
        self.act_zoom_100.setShortcut(QKeySequence("Ctrl+1"))
        self.act_zoom_100.triggered.connect(self.zoom_reset)

        self.act_switch_brf = QAction("BRF Inspector로 전환", self)
        self.act_switch_brf.setShortcut(QKeySequence("Ctrl+2"))
        self.act_switch_brf.triggered.connect(self.switch_to_brf_inspector)

        self.act_preview_brf = QAction("BRF 변환 미리보기", self)
        self.act_preview_brf.setShortcut(QKeySequence("Ctrl+Shift+B"))
        self.act_preview_brf.triggered.connect(self.preview_brf_conversion)

    def _build_menu(self) -> None:
        menu_file = self.menuBar().addMenu("파일")
        menu_file.addAction(self.act_open)
        menu_file.addAction(self.act_save)
        menu_file.addSeparator()
        menu_file.addAction(self.act_preview_brf)

        menu_view = self.menuBar().addMenu("보기")
        menu_view.addAction(self.act_prev)
        menu_view.addAction(self.act_next)
        menu_view.addSeparator()
        menu_view.addAction(self.act_zoom_out)
        menu_view.addAction(self.act_zoom_in)
        menu_view.addAction(self.act_zoom_fit)
        menu_view.addAction(self.act_zoom_100)
        menu_view.addSeparator()
        menu_view.addAction(self.act_preview_brf)
        menu_view.addAction(self.act_switch_brf)

    def _build_toolbar(self) -> None:
        bar = QToolBar("메인")
        bar.setMovable(False)
        self.addToolBar(bar)
        for act in (
            self.act_open,
            self.act_save,
            self.act_prev,
            self.act_next,
            self.act_zoom_out,
            self.act_zoom_in,
            self.act_zoom_fit,
            self.act_zoom_100,
            self.act_merge,
            self.act_split,
            self.act_accept,
            self.act_reorder_up,
            self.act_reorder_down,
            self.act_preview_brf,
            self.act_switch_brf,
        ):
            bar.addAction(act)
            if act in (
                self.act_save,
                self.act_next,
                self.act_zoom_100,
                self.act_split,
                self.act_accept,
                self.act_reorder_down,
                self.act_preview_brf,
            ):
                bar.addSeparator()

        self.zoom_label = QLabel(" 100% ")
        self.zoom_label.setMinimumWidth(56)
        bar.addWidget(self.zoom_label)

        bar.addWidget(QLabel(" 면: "))
        self.page_combo = QComboBox()
        self.page_combo.setMinimumWidth(100)
        self.page_combo.currentIndexChanged.connect(self._on_page_combo)
        bar.addWidget(self.page_combo)

        self.chk_blocks = QCheckBox("블록")
        self.chk_blocks.setChecked(True)
        self.chk_blocks.toggled.connect(lambda: self.refresh_view())
        bar.addWidget(self.chk_blocks)

        self.chk_lines = QCheckBox("행 윤곽")
        self.chk_lines.setChecked(False)
        self.chk_lines.toggled.connect(lambda: self.refresh_view())
        bar.addWidget(self.chk_lines)

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        self.canvas = PdfCanvas()
        self.canvas.blockClicked.connect(self.select_block)
        self.canvas.viewScaleChanged.connect(self._on_view_scale_changed)
        splitter.addWidget(self.canvas)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("블록 / 읽기 순서 / 태그"))

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["순서", "후보", "태그", "주석", "미리보기"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.itemSelectionChanged.connect(self._on_table_selection)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.horizontalHeader().setStretchLastSection(True)
        right_layout.addWidget(self.table)

        self.detail = QLabel("PDF를 여세요.")
        self.detail.setWordWrap(True)
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        right_layout.addWidget(self.detail)

        splitter.addWidget(right)
        splitter.setSizes([900, 500])

    def switch_to_brf_inspector(self) -> None:
        mode_switch.switch_to_brf(from_window=self)

    def preview_brf_conversion(self) -> None:
        """현재 PDF 구조로 파이프라인을 돌려 BRF Inspector에서 확인."""
        if not self.document:
            QMessageBox.information(self, "변환 미리보기", "먼저 PDF를 여세요.")
            return
        from korean_exam_braille.app.pipeline import default_pipeline

        self.statusBar().showMessage("BRF 변환 중…")
        QApplication.processEvents()
        try:
            result = default_pipeline().run_document(self.document)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "변환 실패", str(exc))
            self.statusBar().showMessage("변환 실패")
            return

        summary = _exam_summary(result.exam)
        warn_text = "\n".join(f"· {w}" for w in result.warnings[:8]) or "(없음)"
        more = ""
        if len(result.warnings) > 8:
            more = f"\n… 외 {len(result.warnings) - 8}건"
        QMessageBox.information(
            self,
            "변환 요약",
            f"{summary}\n\n경고:\n{warn_text}{more}\n\n"
            "확인을 누르면 BRF Inspector에서 점자·역점역을 봅니다.",
        )
        src = self.pdf_path.name if self.pdf_path else "preview"
        mode_switch.switch_to_brf(
            from_window=self,
            brf_text=result.brf_text,
            path=f"{src}.preview.brf",
            status_message=(
                f"변환 미리보기 · {len(result.braille_document.pages)}면 · "
                f"경고 {len(result.warnings)}건 · Ctrl+2로 PDF로 복귀"
            ),
        )

    def open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "파일 열기",
            "",
            "PDF / BRF (*.pdf *.PDF *.brf *.BRF);;PDF (*.pdf);;BRF (*.brf *.BRF);;All files (*.*)",
        )
        if path:
            self.open_path(Path(path))

    def open_path(self, path: Path) -> None:
        if path.suffix.lower() in {".brf"}:
            mode_switch.switch_to_brf(from_window=self, path=path)
            return
        try:
            self.document = extract_pdf(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "열기 실패", str(exc))
            return
        self.pdf_path = path
        self._page_number = self.document.pages[0].page_number if self.document.pages else 1
        self._keep_view_on_refresh = False
        self._rebuild_page_combo()
        self.refresh_view()
        layout = (self.document.metadata or {}).get("layout_profile") or {}
        cut = layout.get("column_cut_x")
        extra = f" · cut={cut:.0f}" if isinstance(cut, (int, float)) else ""
        self.statusBar().showMessage(
            f"열림: {path.name} · {self.document.page_count}면 · "
            f"추출 {len(self.document.pages)}면{extra}"
        )

    def save_structure(self) -> None:
        if not self.document or not self.pdf_path:
            QMessageBox.information(self, "저장", "먼저 PDF를 여세요.")
            return
        self._flush_table()
        path = save_structure(self.document)
        self.statusBar().showMessage(f"구조 저장: {path}")

    def prev_page(self) -> None:
        if not self.document:
            return
        nums = [p.page_number for p in self.document.pages]
        idx = nums.index(self._page_number) if self._page_number in nums else 0
        if idx > 0:
            self.show_page(nums[idx - 1])

    def next_page(self) -> None:
        if not self.document:
            return
        nums = [p.page_number for p in self.document.pages]
        idx = nums.index(self._page_number) if self._page_number in nums else 0
        if idx + 1 < len(nums):
            self.show_page(nums[idx + 1])

    def _rebuild_page_combo(self) -> None:
        self._updating = True
        self.page_combo.clear()
        if self.document:
            for page in self.document.pages:
                self.page_combo.addItem(
                    f"{page.page_number} ({len(page.blocks)}블록)",
                    page.page_number,
                )
        self._updating = False

    def _on_page_combo(self, index: int) -> None:
        if self._updating or index < 0:
            return
        page_number = self.page_combo.itemData(index)
        if page_number is not None:
            self.show_page(int(page_number))

    def current_page(self) -> PdfPageStructure | None:
        if not self.document:
            return None
        try:
            return self.document.get_page(self._page_number)
        except IndexError:
            return None

    def show_page(self, page_number: int) -> None:
        self._page_number = page_number
        self._selected_block_id = None
        self._updating = True
        for i in range(self.page_combo.count()):
            if self.page_combo.itemData(i) == page_number:
                self.page_combo.setCurrentIndex(i)
                break
        self._updating = False
        self.refresh_view()

    def refresh_view(self) -> None:
        page = self.current_page()
        if not page or not self.pdf_path:
            return
        png = render_page_pixmap(
            self.pdf_path, page.page_number, zoom=self._render_zoom
        )
        self.canvas.set_page_image(
            png,
            page.height,
            self._render_zoom,
            keep_view=self._keep_view_on_refresh,
        )
        self._keep_view_on_refresh = True
        self._draw_overlays(page)
        self._fill_table(page)
        self.detail.setText(
            f"면 {page.page_number} · span {len(page.spans)} · "
            f"행 {len(page.lines)} · 블록 {len(page.blocks)}"
        )

    def zoom_fit(self) -> None:
        self.canvas.fit_page()

    def zoom_reset(self) -> None:
        self.canvas.reset_zoom()

    def _on_view_scale_changed(self, scale: float) -> None:
        self.zoom_label.setText(f" {scale * 100:.0f}% ")

    def _fill_table(self, page: PdfPageStructure) -> None:
        self._updating = True
        blocks = sorted(page.blocks, key=lambda b: b.reading_order)
        self.table.setRowCount(len(blocks))
        for row, block in enumerate(blocks):
            values = [
                str(block.reading_order),
                ", ".join(block.candidate_tags),
                ", ".join(block.tags),
                block.notes or "",
                block.text.replace("\n", " ")[:80],
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, block.id)
                if col in (0, 1, 4):
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)
        self._updating = False

    def _selected_block_ids(self) -> list[str]:
        ids: list[str] = []
        for idx in self.table.selectionModel().selectedRows():
            item = self.table.item(idx.row(), 0)
            if item:
                bid = item.data(Qt.ItemDataRole.UserRole)
                if bid:
                    ids.append(str(bid))
        return ids

    def select_block(self, block_id: str) -> None:
        self._selected_block_id = block_id
        page = self.current_page()
        if not page:
            return
        self._updating = True
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == block_id:
                self.table.selectRow(row)
                break
        self._updating = False
        block = next((b for b in page.blocks if b.id == block_id), None)
        if block:
            self.detail.setText(
                f"[{block.reading_order}] {block.id}\n"
                f"후보: {', '.join(block.candidate_tags) or '-'}\n"
                f"태그: {', '.join(block.tags) or '-'}\n\n"
                f"{block.text}"
            )
        self._draw_overlays(page)

    def _draw_overlays(self, page: PdfPageStructure) -> None:
        boxes: list[tuple[str, tuple[float, float, float, float], list[str], int]] = []
        if self.chk_blocks.isChecked():
            for block in sorted(page.blocks, key=lambda b: b.reading_order):
                tags = block.tags or block.candidate_tags
                boxes.append((block.id, block.bbox, tags, block.reading_order))
        if self.chk_lines.isChecked():
            for line in page.lines:
                boxes.append((line.id, line.bbox, [], line.reading_order))
        self.canvas.set_overlays(
            boxes,
            selected_id=self._selected_block_id,
            show=True,
        )

    def _on_table_selection(self) -> None:
        if self._updating:
            return
        ids = self._selected_block_ids()
        if ids:
            self.select_block(ids[0])
    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating:
            return
        page = self.current_page()
        if not page:
            return
        block_id = item.data(Qt.ItemDataRole.UserRole)
        block = next((b for b in page.blocks if b.id == block_id), None)
        if not block:
            return
        if item.column() == 2:
            tags = [t.strip() for t in item.text().split(",") if t.strip()]
            unknown = [t for t in tags if t not in STRUCTURE_TAGS]
            block.tags = tags
            if unknown:
                self.statusBar().showMessage(f"사용자 태그: {', '.join(unknown)}")
        elif item.column() == 3:
            note = item.text().strip()
            block.notes = note or None

    def _flush_table(self) -> None:
        page = self.current_page()
        if not page:
            return
        for row in range(self.table.rowCount()):
            id_item = self.table.item(row, 0)
            tag_item = self.table.item(row, 2)
            note_item = self.table.item(row, 3)
            if not id_item:
                continue
            block_id = id_item.data(Qt.ItemDataRole.UserRole)
            block = next((b for b in page.blocks if b.id == block_id), None)
            if not block:
                continue
            if tag_item:
                block.tags = [t.strip() for t in tag_item.text().split(",") if t.strip()]
            if note_item:
                note = note_item.text().strip()
                block.notes = note or None

    def accept_candidates(self) -> None:
        page = self.current_page()
        if not page:
            return
        for block in page.blocks:
            if block.candidate_tags and not block.tags:
                block.tags = list(block.candidate_tags)
        self.refresh_view()
        self.statusBar().showMessage("후보 태그를 적용했습니다.")

    def merge_selected(self) -> None:
        page = self.current_page()
        if not page:
            return
        ids = self._selected_block_ids()
        if len(ids) != 2:
            QMessageBox.information(self, "병합", "블록을 정확히 2개 선택하세요.")
            return
        try:
            page.blocks = merge_blocks(page.blocks, ids[0], ids[1])
            for block in page.blocks:
                block.candidate_tags = detect_block_candidates(block.text)
            assign_reading_order(page.blocks)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "병합 실패", str(exc))
            return
        self.refresh_view()

    def split_selected(self) -> None:
        page = self.current_page()
        if not page:
            return
        ids = self._selected_block_ids()
        if len(ids) != 1:
            QMessageBox.information(self, "분할", "블록을 하나 선택하세요.")
            return
        block = next(b for b in page.blocks if b.id == ids[0])
        if len(block.line_ids) < 2:
            QMessageBox.information(self, "분할", "행이 2개 이상인 블록만 분할할 수 있습니다.")
            return
        mid = block.line_ids[len(block.line_ids) // 2 - 1]
        try:
            left, right = split_block(block, page.lines, mid)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "분할 실패", str(exc))
            return
        new_blocks = []
        for b in page.blocks:
            if b.id == block.id:
                new_blocks.append(left)
                new_blocks.append(right)
            else:
                new_blocks.append(b)
        for b in new_blocks:
            b.candidate_tags = detect_block_candidates(b.text)
        page.blocks = assign_reading_order(new_blocks)
        self.refresh_view()

    def nudge_order(self, delta: int) -> None:
        page = self.current_page()
        if not page or not self._selected_block_id:
            return
        block = next((b for b in page.blocks if b.id == self._selected_block_id), None)
        if not block:
            return
        page.blocks = move_block_order(page.blocks, block.id, block.reading_order + delta)
        self.refresh_view()
        self.select_block(block.id)

    def closeEvent(self, event) -> None:  # noqa: N802
        if mode_switch.handle_close(self):
            event.accept()
        else:
            event.ignore()


def _exam_summary(exam) -> str:
    groups = passages = questions = choices = 0

    def walk(node) -> None:
        nonlocal groups, passages, questions, choices
        if node.node_type == "PassageGroup":
            groups += 1
        elif node.node_type == "Passage":
            passages += 1
        elif node.node_type == "Question":
            questions += 1
        elif node.node_type == "Choice":
            choices += 1
        for child in node.children:
            walk(child)

    walk(exam.root)
    return (
        f"PassageGroup {groups} · Passage {passages} · "
        f"Question {questions} · Choice {choices}"
    )
