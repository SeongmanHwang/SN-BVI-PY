"""변환 미리보기 — Exam 트리·경고·선택적 참고 BRF 비교."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from korean_exam_braille.app.brf.compare import compare_to_reference_file
from korean_exam_braille.app.exam.models import ExamNode
from korean_exam_braille.app.exam.tree_text import format_exam_summary
from korean_exam_braille.app.pipeline.pipeline import PipelineResult


class ConversionPreviewDialog(QDialog):
    def __init__(self, parent, result: PipelineResult) -> None:
        super().__init__(parent)
        self.result = result
        self.setWindowTitle("BRF 변환 미리보기 — 구조·관계")
        self.resize(900, 640)

        layout = QVBoxLayout(self)
        summary = format_exam_summary(result.exam)
        layout.addWidget(QLabel(summary))

        splitter = QSplitter()
        layout.addWidget(splitter, stretch=1)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["유형", "id / 미리보기"])
        self.tree.setColumnWidth(0, 140)
        self._fill_tree(result.exam.root, None)
        self.tree.expandToDepth(2)
        splitter.addWidget(self.tree)

        right = QVBoxLayout()
        right_w = QPlainTextEdit()
        # placeholder container
        from PySide6.QtWidgets import QWidget

        box = QWidget()
        box.setLayout(right)
        splitter.addWidget(box)

        right.addWidget(QLabel("경고 · 관계 · 비교"))
        self.side = QPlainTextEdit()
        self.side.setReadOnly(True)
        right.addWidget(self.side)

        rel_lines = [
            f"{r.relation_type}: {r.source_id} → {r.target_id}"
            for r in result.exam.relations[:40]
        ]
        warn_lines = [f"· {w}" for w in result.warnings] or ["(경고 없음)"]
        body = "경고\n" + "\n".join(warn_lines)
        body += "\n\nrelations\n" + ("\n".join(rel_lines) or "(없음)")
        if len(result.exam.relations) > 40:
            body += f"\n… 외 {len(result.exam.relations) - 40}건"
        self.side.setPlainText(body)

        row = QHBoxLayout()
        self.btn_compare = QPushButton("참고 BRF와 줄 비교…")
        self.btn_compare.clicked.connect(self._compare_reference)
        self.btn_exam_diff = QPushButton("참고 BRF와 내용 비교…")
        self.btn_exam_diff.clicked.connect(self._exam_content_diff)
        self.btn_nav = QPushButton("계층 탐색기…")
        self.btn_nav.clicked.connect(self._open_navigator)
        row.addWidget(self.btn_compare)
        row.addWidget(self.btn_exam_diff)
        row.addWidget(self.btn_nav)
        row.addStretch(1)
        right.addLayout(row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            "BRF Inspector에서 보기"
        )
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
        splitter.setSizes([480, 400])

    def _fill_tree(self, node: ExamNode, parent: QTreeWidgetItem | None) -> None:
        raw = (node.source_range.raw_text or "").replace("\n", " ").strip()
        preview = raw[:56] + ("…" if len(raw) > 56 else "")
        qn = node.metadata.get("question_number")
        label = node.node_type + (f" #{qn}" if qn is not None else "")
        item = QTreeWidgetItem([label, f"{node.id}  {preview}"])
        if parent is None:
            self.tree.addTopLevelItem(item)
        else:
            parent.addChild(item)
        for child in node.children:
            self._fill_tree(child, item)

    def _compare_reference(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "참고 BRF 선택",
            "",
            "BRF (*.brf *.BRF);;All files (*.*)",
        )
        if not path:
            return
        # 생성본 앞부분만 (참고와 면 수가 크게 다를 수 있음)
        page_limit = max(1, len(self.result.braille_document.pages))
        cmp = compare_to_reference_file(
            self.result.brf_text,
            Path(path),
            page_limit=min(page_limit, 8),
        )
        text = self.side.toPlainText()
        text += "\n\n── 참고 BRF 비교 ──\n"
        text += cmp.summary(max_diffs=8)
        self.side.setPlainText(text)

    def _exam_content_diff(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "참고 BRF 선택 (시각장애용)",
            "",
            "BRF (*.brf *.BRF);;All files (*.*)",
        )
        if not path:
            return
        from korean_exam_braille.app.brf.exam_diff import compare_exam_content

        report = compare_exam_content(self.result.brf_text, Path(path))
        text = self.side.toPlainText()
        text += "\n\n" + report.summary(max_items=10)
        self.side.setPlainText(text)

    def _open_navigator(self) -> None:
        from korean_exam_braille.app.ui.nav.dialog import NavigatorDialog

        NavigatorDialog(self, self.result.exam).exec()
