"""BRF Inspector ↔ PDF Structure Viewer 창 전환."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget

_brf_window: QMainWindow | None = None
_pdf_window: QMainWindow | None = None
_shutting_down = False


def brf_window() -> QMainWindow:
    global _brf_window
    if _brf_window is None:
        from korean_exam_braille.app.ui.brf_inspector.window import BrfInspectorWindow

        _brf_window = BrfInspectorWindow()
    return _brf_window


def pdf_window() -> QMainWindow:
    global _pdf_window
    if _pdf_window is None:
        from korean_exam_braille.app.ui.pdf_viewer.window import PdfStructureWindow

        _pdf_window = PdfStructureWindow()
    return _pdf_window


def _activate(window: QMainWindow) -> None:
    window.show()
    window.raise_()
    window.activateWindow()


def switch_to_brf(
    *,
    from_window: QWidget | None = None,
    path: str | Path | None = None,
    brf_text: str | None = None,
    status_message: str | None = None,
) -> QMainWindow:
    """PDF 뷰어에서 BRF Inspector로 전환."""
    app = QApplication.instance()
    if app is not None:
        app.setApplicationName("BRF Inspector")
    win = brf_window()
    if brf_text is not None:
        win.load_brf_text(  # type: ignore[attr-defined]
            brf_text,
            source_path=str(path) if path else None,
        )
    elif path is not None:
        win.open_path(Path(path))  # type: ignore[attr-defined]
    if status_message:
        win.statusBar().showMessage(status_message)
    if from_window is not None and from_window is not win:
        from_window.hide()
    _activate(win)
    return win


def switch_to_pdf(
    *,
    from_window: QWidget | None = None,
    path: str | Path | None = None,
) -> QMainWindow:
    """BRF Inspector에서 PDF Structure Viewer로 전환."""
    app = QApplication.instance()
    if app is not None:
        app.setApplicationName("PDF Structure Viewer")
    win = pdf_window()
    if path is not None:
        win.open_path(Path(path))  # type: ignore[attr-defined]
    if from_window is not None and from_window is not win:
        from_window.hide()
    _activate(win)
    return win


def open_initial(mode: str, path: str | None = None) -> QMainWindow:
    """진입점용 — 지정 모드 창만 표시."""
    if mode == "pdf":
        return switch_to_pdf(path=path)
    return switch_to_brf(path=path)


def handle_close(window: QMainWindow) -> bool:
    """창 닫기 시 숨겨 둔 상대 창까지 정리하고 종료.

    Returns:
        True면 이벤트를 accept해도 됨.
    """
    global _shutting_down, _brf_window, _pdf_window
    if _shutting_down:
        return True
    _shutting_down = True
    peers = [w for w in (_brf_window, _pdf_window) if w is not None and w is not window]
    for peer in peers:
        peer.close()
    _brf_window = None
    _pdf_window = None
    _shutting_down = False
    return True
