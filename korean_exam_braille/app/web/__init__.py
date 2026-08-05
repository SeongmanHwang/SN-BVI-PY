"""웹 사용자 모드 셸 — WCAG 지향 단순 플로우."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from korean_exam_braille.app.web.server import create_app, main

__all__ = ["create_app", "main"]


def __getattr__(name: str):
    if name in __all__:
        from korean_exam_braille.app.web import server as _server

        return getattr(_server, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
