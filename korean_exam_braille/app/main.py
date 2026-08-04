"""애플리케이션 진입점 — BRF Inspector / PDF Structure Viewer."""

from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="korean-exam-braille",
        description="수능 국어 PDF–BRF 도구",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="열 파일 (.brf 또는 .pdf). 없으면 모드에 따라 빈 창",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "brf", "pdf"),
        default="auto",
        help="auto: 확장자로 선택 (기본). 실행 중 보기 메뉴로 전환 가능",
    )
    return parser.parse_args(argv)


def _resolve_mode(mode: str, path: str | None) -> str:
    if mode != "auto":
        return mode
    if not path:
        return "brf"
    lower = path.lower()
    if lower.endswith(".pdf"):
        return "pdf"
    return "brf"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    mode = _resolve_mode(args.mode, args.path)

    app = QApplication(sys.argv if argv is None else [sys.argv[0], *sys.argv[1:]])
    app.setOrganizationName("korean-exam-braille")
    app.setApplicationName(
        "PDF Structure Viewer" if mode == "pdf" else "BRF Inspector"
    )

    from korean_exam_braille.app.ui.mode_switch import open_initial

    open_initial(mode, args.path)
    return app.exec()


def main_pdf(argv: list[str] | None = None) -> int:
    """pdf-viewer 콘솔 스크립트용."""
    raw = list(sys.argv[1:] if argv is None else argv)
    if "--mode" not in raw:
        raw = ["--mode", "pdf", *raw]
    return main(raw)


if __name__ == "__main__":
    raise SystemExit(main())
