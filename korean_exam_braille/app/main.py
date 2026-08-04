"""BRF Inspector 진입점."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from korean_exam_braille.app.ui.brf_inspector.window import BrfInspectorWindow


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    app = QApplication(sys.argv if argv is None else [sys.argv[0], *args])
    app.setApplicationName("BRF Inspector")
    app.setOrganizationName("korean-exam-braille")

    initial = args[0] if args else None
    window = BrfInspectorWindow(initial_path=initial)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
