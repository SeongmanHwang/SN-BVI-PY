"""계층 탐색 대화상자 — 보조 진입점(도킹 패널이 기본).

메인 PDF 창은 `NavSidePanel` 도크(보기 → 계층 탐색)를 쓴다.
이 대화상자는 독립 Exam만 있을 때 쓸 수 있으나, 변환 미리보기에서는 쓰지 않는다.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from korean_exam_braille.app.exam.models import ExamDocument
from korean_exam_braille.app.exam.tree_text import format_exam_summary
from korean_exam_braille.app.nav import TreeExamNavigator
from korean_exam_braille.app.ui.nav.panel import NavSidePanel, format_location_status


class NavigatorDialog(QDialog):
    def __init__(self, parent, exam: ExamDocument, *, on_location=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("계층 탐색기")
        self.resize(420, 560)
        self._on_location = on_location

        self.navigator = TreeExamNavigator()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(format_exam_summary(exam)))
        self.status = QLabel("")
        layout.addWidget(self.status)

        self.panel = NavSidePanel()
        self.panel.bind(self.navigator, exam)
        self.panel.install_window_shortcuts(self)
        self.panel.locationChanged.connect(self._emit_location)
        layout.addWidget(self.panel)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn:
            close_btn.clicked.connect(self.accept)
        layout.addWidget(buttons)
        self._emit_location(self.navigator.location())

    def _emit_location(self, loc) -> None:
        self.status.setText(format_location_status(loc))
        if self._on_location is not None:
            self._on_location(loc)
