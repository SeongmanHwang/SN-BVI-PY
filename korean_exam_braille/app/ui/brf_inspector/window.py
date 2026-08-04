"""BRF Inspector 메인 윈도우."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from korean_exam_braille.app.brf.annotations import (
    annotation_path_for,
    load_brf_with_annotations,
    save_annotations,
)
from korean_exam_braille.app.brf.models import STRUCTURE_TAGS, BrfDocument, BrfLine
from korean_exam_braille.app.brf.parser import save_brf


class BrfInspectorWindow(QMainWindow):
    def __init__(self, initial_path: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("BRF Inspector — 수능 국어 점자")
        self.resize(1280, 800)

        self.document: BrfDocument | None = None
        self._current_page = 0
        self._updating = False

        self._build_actions()
        self._build_toolbar()
        self._build_ui()
        self.setStatusBar(QStatusBar())

        if initial_path:
            self.open_path(Path(initial_path))

    def _build_actions(self) -> None:
        self.act_open = QAction("열기…", self)
        self.act_open.setShortcut(QKeySequence.Open)
        self.act_open.triggered.connect(self.open_file_dialog)

        self.act_save_ann = QAction("태그 저장", self)
        self.act_save_ann.setShortcut(QKeySequence.Save)
        self.act_save_ann.triggered.connect(self.save_current_annotations)

        self.act_save_brf = QAction("BRF 다른 이름으로 저장…", self)
        self.act_save_brf.triggered.connect(self.save_brf_as)

        self.act_prev = QAction("이전 면", self)
        self.act_prev.setShortcut(QKeySequence.MoveToPreviousPage)
        self.act_prev.triggered.connect(self.prev_page)

        self.act_next = QAction("다음 면", self)
        self.act_next.setShortcut(QKeySequence.MoveToNextPage)
        self.act_next.triggered.connect(self.next_page)

        self.act_accept_candidates = QAction("후보→태그 적용(현재 면)", self)
        self.act_accept_candidates.triggered.connect(self.accept_candidates_on_page)

    def _build_toolbar(self) -> None:
        bar = QToolBar("메인")
        bar.setMovable(False)
        self.addToolBar(bar)
        bar.addAction(self.act_open)
        bar.addAction(self.act_save_ann)
        bar.addAction(self.act_save_brf)
        bar.addSeparator()
        bar.addAction(self.act_prev)
        bar.addAction(self.act_next)
        bar.addSeparator()
        bar.addAction(self.act_accept_candidates)

        bar.addWidget(QLabel("  점자 면: "))
        self.page_combo = QComboBox()
        self.page_combo.setMinimumWidth(120)
        self.page_combo.currentIndexChanged.connect(self._on_page_combo)
        bar.addWidget(self.page_combo)

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)

        top = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(top)

        mono = QFont("Consolas", 12)
        braille_font = QFont("Segoe UI Symbol", 14)
        if not braille_font.exactMatch():
            braille_font = QFont("Arial Unicode MS", 14)

        self.ascii_view = QPlainTextEdit()
        self.ascii_view.setReadOnly(True)
        self.ascii_view.setFont(mono)
        self.ascii_view.setPlaceholderText("BRF 원문 (ASCII)")
        top.addWidget(self._wrap("BRF 원문", self.ascii_view))

        self.unicode_view = QPlainTextEdit()
        self.unicode_view.setReadOnly(True)
        self.unicode_view.setFont(braille_font)
        self.unicode_view.setPlaceholderText("유니코드 점자")
        top.addWidget(self._wrap("유니코드 점자", self.unicode_view))

        self.reverse_view = QPlainTextEdit()
        self.reverse_view.setReadOnly(True)
        self.reverse_view.setFont(mono)
        self.reverse_view.setPlaceholderText("묵자 역점역")
        top.addWidget(self._wrap("묵자 역점역", self.reverse_view))

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["전역행", "면", "행", "후보", "태그", "주석", "미리보기"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.horizontalHeader().setStretchLastSection(True)
        splitter.addWidget(self._wrap("행 번호 / 구조 태그 / 주석", self.table))

        splitter.setSizes([420, 320])
        top.setSizes([400, 400, 400])

        self.pos_label = QLabel("파일 없음")
        layout.addWidget(self.pos_label)

    @staticmethod
    def _wrap(title: str, widget: QWidget) -> QWidget:
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(QLabel(title))
        v.addWidget(widget)
        return box

    def open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "BRF 파일 열기",
            "",
            "BRF files (*.brf *.BRF);;All files (*.*)",
        )
        if path:
            self.open_path(Path(path))

    def open_path(self, path: Path) -> None:
        try:
            self.document = load_brf_with_annotations(path)
        except OSError as exc:
            QMessageBox.critical(self, "열기 실패", str(exc))
            return
        self._current_page = 0
        self._rebuild_page_combo()
        self.show_page(0)
        ann = annotation_path_for(path)
        extra = f" · 주석 {ann.name}" if ann.exists() else ""
        self.statusBar().showMessage(
            f"열림: {path.name} · {self.document.page_count}면 · "
            f"{self.document.line_count}행{extra}"
        )

    def save_current_annotations(self) -> None:
        if not self.document or not self.document.source_path:
            QMessageBox.information(self, "저장", "먼저 BRF 파일을 여세요.")
            return
        self._flush_table_edits()
        path = save_annotations(self.document)
        self.statusBar().showMessage(f"태그 저장: {path}")

    def save_brf_as(self) -> None:
        if not self.document:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "BRF 저장",
            self.document.source_path or "output.brf",
            "BRF files (*.brf);;All files (*.*)",
        )
        if not path:
            return
        save_brf(self.document, path)
        self.statusBar().showMessage(f"BRF 저장: {path}")

    def accept_candidates_on_page(self) -> None:
        if not self.document:
            return
        page = self.document.pages[self._current_page]
        for line in page.lines:
            if line.candidate_tags and not line.tags:
                line.tags = list(line.candidate_tags)
        self.show_page(self._current_page)
        self.statusBar().showMessage("현재 면 후보 태그를 적용했습니다. 저장을 잊지 마세요.")

    def prev_page(self) -> None:
        if self.document and self._current_page > 0:
            self.show_page(self._current_page - 1)

    def next_page(self) -> None:
        if self.document and self._current_page < self.document.page_count - 1:
            self.show_page(self._current_page + 1)

    def _rebuild_page_combo(self) -> None:
        self._updating = True
        self.page_combo.clear()
        if self.document:
            for i in range(self.document.page_count):
                nlines = self.document.pages[i].line_count
                self.page_combo.addItem(f"{i + 1} / {self.document.page_count} ({nlines}행)", i)
        self._updating = False

    def _on_page_combo(self, index: int) -> None:
        if self._updating or index < 0:
            return
        self.show_page(index)

    def show_page(self, page_index: int) -> None:
        if not self.document:
            return
        page_index = max(0, min(page_index, self.document.page_count - 1))
        self._current_page = page_index
        self._updating = True
        self.page_combo.setCurrentIndex(page_index)
        self._updating = False

        page = self.document.pages[page_index]
        ascii_lines = [line.raw_ascii for line in page.lines]
        uni_lines = [line.unicode_braille for line in page.lines]
        rev_lines = [line.reverse_text or "" for line in page.lines]

        self.ascii_view.setPlainText("\n".join(ascii_lines))
        self.unicode_view.setPlainText("\n".join(uni_lines))
        self.reverse_view.setPlainText("\n".join(rev_lines))

        self._fill_table(page.lines)
        self.pos_label.setText(
            f"점자 면 {page_index + 1}/{self.document.page_count} · "
            f"행 {page.line_count} · 전역 행 "
            f"{page.lines[0].global_index if page.lines else '-'}–"
            f"{page.lines[-1].global_index if page.lines else '-'}"
        )

    def _fill_table(self, lines: list[BrfLine]) -> None:
        self._updating = True
        self.table.setRowCount(len(lines))
        for row, line in enumerate(lines):
            values = [
                str(line.global_index),
                str(line.page_index + 1),
                str(line.line_index + 1),
                ", ".join(line.candidate_tags),
                ", ".join(line.tags),
                line.notes or "",
                (line.reverse_text or line.raw_ascii)[:60],
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in (0, 1, 2, 3, 6):
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)
        self._updating = False

    def _flush_table_edits(self) -> None:
        if not self.document:
            return
        page = self.document.pages[self._current_page]
        for row, line in enumerate(page.lines):
            tag_item = self.table.item(row, 4)
            note_item = self.table.item(row, 5)
            if tag_item:
                raw = tag_item.text().strip()
                tags = [t.strip() for t in raw.split(",") if t.strip()]
                # 알려지지 않은 태그도 허용하되 공백 제거
                line.tags = tags
            if note_item:
                note = note_item.text().strip()
                line.notes = note or None

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating or not self.document:
            return
        if item.column() not in (4, 5):
            return
        page = self.document.pages[self._current_page]
        row = item.row()
        if row < 0 or row >= len(page.lines):
            return
        line = page.lines[row]
        if item.column() == 4:
            tags = [t.strip() for t in item.text().split(",") if t.strip()]
            unknown = [t for t in tags if t not in STRUCTURE_TAGS]
            line.tags = tags
            if unknown:
                self.statusBar().showMessage(
                    f"사용자 정의 태그: {', '.join(unknown)} (허용됨)"
                )
        elif item.column() == 5:
            note = item.text().strip()
            line.notes = note or None

    def _on_row_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows or not self.document:
            return
        row = rows[0].row()
        page = self.document.pages[self._current_page]
        if row >= len(page.lines):
            return
        line = page.lines[row]
        # 세 뷰에서 해당 행으로 커서 이동
        for view in (self.ascii_view, self.unicode_view, self.reverse_view):
            block = view.document().findBlockByLineNumber(row)
            if block.isValid():
                cursor = view.textCursor()
                cursor.setPosition(block.position())
                view.setTextCursor(cursor)
                view.centerCursor()
        self.pos_label.setText(
            f"면 {line.page_index + 1} · 행 {line.line_index + 1} · "
            f"전역 {line.global_index} · 열 수 {len(line.raw_ascii)} · "
            f"태그 {', '.join(line.tags) or '-'} · "
            f"후보 {', '.join(line.candidate_tags) or '-'}"
        )
