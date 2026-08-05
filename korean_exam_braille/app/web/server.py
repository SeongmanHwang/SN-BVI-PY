"""로컬 웹 셸 (Starlette) — 사용자·개발자 모드."""

from __future__ import annotations

import argparse
import mimetypes
from pathlib import Path
from urllib.parse import quote

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from korean_exam_braille.app.session import ConversionWorkspace

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(*, workspace: ConversionWorkspace | None = None) -> Starlette:
    ws = workspace or ConversionWorkspace()

    async def index(_request: Request) -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    async def developer_page(_request: Request) -> FileResponse:
        return FileResponse(STATIC_DIR / "developer.html")

    async def api_status(_request: Request) -> JSONResponse:
        return JSONResponse(ws.status_snapshot())

    async def api_upload(request: Request) -> JSONResponse:
        form = await request.form()
        upload = form.get("file")
        if upload is None:
            return JSONResponse(
                {"ok": False, "message": "PDF 파일이 없습니다."},
                status_code=400,
            )
        filename = getattr(upload, "filename", None) or "upload.pdf"
        data = await upload.read()  # type: ignore[union-attr]
        if not data:
            return JSONResponse(
                {"ok": False, "message": "빈 파일입니다."},
                status_code=400,
            )
        try:
            meta = ws.load_pdf_bytes(data, filename=str(filename))
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(
                {"ok": False, "message": f"PDF를 열 수 없습니다. {exc}"},
                status_code=400,
            )
        return JSONResponse(
            {
                "ok": True,
                "message": (
                    f"{meta['name']}을(를) 올렸습니다. "
                    f"{meta['page_count']}면 중 {meta['extracted_pages']}면을 준비했습니다. "
                    "이제 분석 및 변환을 실행할 수 있습니다."
                ),
                "meta": meta,
                "status": ws.status_snapshot(),
            }
        )

    async def api_convert(_request: Request) -> JSONResponse:
        if not ws.has_pdf:
            return JSONResponse(
                {"ok": False, "message": "PDF를 먼저 업로드하세요."},
                status_code=400,
            )
        try:
            result = ws.analyze_and_convert()
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(
                {"ok": False, "message": f"변환에 실패했습니다. {exc}"},
                status_code=500,
            )
        warn_n = len(result.warnings)
        pages = len(result.braille_document.pages)
        msg = (
            f"변환이 완료되었습니다. 점자 {pages}면"
            + (f", 경고 {warn_n}건" if warn_n else "")
            + ". BRF와 DTBook XML을 받을 수 있습니다."
        )
        return JSONResponse(
            {
                "ok": True,
                "message": msg,
                "status": ws.status_snapshot(),
            }
        )

    async def api_download_brf(_request: Request) -> Response:
        if not ws.has_brf:
            return JSONResponse(
                {"ok": False, "message": "먼저 분석 및 변환을 실행하세요."},
                status_code=400,
            )
        name = (ws.source_name or "exam").rsplit(".", 1)[0] + ".brf"
        body = ws.brf_bytes()
        return Response(
            body,
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"
            },
        )

    async def api_download_dtbook(_request: Request) -> Response:
        if not ws.dtbook_download_available:
            return JSONResponse(
                {
                    "ok": False,
                    "message": "먼저 분석 및 변환을 실행하세요.",
                },
                status_code=400,
            )
        try:
            xml = ws.dtbook_xml(for_user_download=True)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(
                {"ok": False, "message": str(exc)},
                status_code=500,
            )
        name = (ws.source_name or "exam").rsplit(".", 1)[0] + ".xml"
        return Response(
            xml.encode("utf-8"),
            media_type="application/xml; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"
            },
        )

    async def api_dev_bundle(request: Request) -> JSONResponse:
        page_raw = request.query_params.get("page")
        page_number = int(page_raw) if page_raw and page_raw.isdigit() else None
        try:
            bundle = ws.developer_bundle(page_number=page_number)
        except ValueError as exc:
            return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(
                {"ok": False, "message": f"개발자 데이터를 만들 수 없습니다. {exc}"},
                status_code=500,
            )
        return JSONResponse({"ok": True, **bundle})

    async def api_dev_pdf_page(request: Request) -> Response:
        if not ws.has_pdf:
            return JSONResponse(
                {"ok": False, "message": "PDF를 먼저 업로드하세요."},
                status_code=400,
            )
        try:
            page_number = int(request.path_params["page"])
        except (KeyError, ValueError):
            return JSONResponse(
                {"ok": False, "message": "면 번호가 올바르지 않습니다."},
                status_code=400,
            )
        try:
            png = ws.pdf_page_png(page_number, zoom=1.5)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(
                {"ok": False, "message": str(exc)},
                status_code=404,
            )
        return Response(png, media_type="image/png")

    async def api_dev_reference_brf(request: Request) -> JSONResponse:
        form = await request.form()
        upload = form.get("file")
        if upload is None:
            return JSONResponse(
                {"ok": False, "message": "BRF 파일이 없습니다."},
                status_code=400,
            )
        filename = getattr(upload, "filename", None) or "reference.brf"
        data = await upload.read()  # type: ignore[union-attr]
        try:
            meta = ws.load_reference_brf_bytes(data, filename=str(filename))
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(
                {"ok": False, "message": f"참고 BRF를 열 수 없습니다. {exc}"},
                status_code=400,
            )
        return JSONResponse(
            {
                "ok": True,
                "message": (
                    f"참고 BRF {meta['name']}을(를) 올렸습니다. "
                    f"{meta['pages']}면 · {meta['lines']}행."
                ),
                "meta": meta,
                "status": ws.status_snapshot(),
            }
        )

    async def api_dev_review(_request: Request) -> JSONResponse:
        try:
            bundle = ws.review_bundle()
        except ValueError as exc:
            return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(
                {"ok": False, "message": f"검토 데이터를 만들 수 없습니다. {exc}"},
                status_code=500,
            )
        return JSONResponse({"ok": True, **bundle})

    routes = [
        Route("/", index),
        Route("/dev", developer_page),
        Route("/api/status", api_status),
        Route("/api/upload", api_upload, methods=["POST"]),
        Route("/api/convert", api_convert, methods=["POST"]),
        Route("/api/download/brf", api_download_brf),
        Route("/api/download/dtbook", api_download_dtbook),
        Route("/api/dev/bundle", api_dev_bundle),
        Route("/api/dev/pdf-page/{page:int}", api_dev_pdf_page),
        Route("/api/dev/reference-brf", api_dev_reference_brf, methods=["POST"]),
        Route("/api/dev/review", api_dev_review),
        Mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static"),
    ]
    app = Starlette(routes=routes)
    app.state.workspace = ws  # type: ignore[attr-defined]
    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="국어 시험 PDF→BRF 웹 셸 (사용자·개발자 모드)"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    import uvicorn

    mimetypes.add_type("text/html", ".html")
    uvicorn.run(
        create_app(),
        host=args.host,
        port=args.port,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
