"""웹 사용자 모드 API."""

import fitz
import pytest

pytest.importorskip("starlette")

from starlette.testclient import TestClient

from korean_exam_braille.app.exam.stub import StubExamStructureBuilder
from korean_exam_braille.app.pipeline import default_stub_pipeline
from korean_exam_braille.app.session import ConversionWorkspace, PdfStructureService
from korean_exam_braille.app.web.server import create_app


@pytest.fixture
def tiny_pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def client():
    ws = ConversionWorkspace(
        service=PdfStructureService(
            exam_builder=StubExamStructureBuilder(),
            pipeline_factory=default_stub_pipeline,
        )
    )
    with TestClient(create_app(workspace=ws)) as c:
        yield c


def test_user_flow_upload_convert_brf(client, tiny_pdf_bytes: bytes):
    home = client.get("/")
    assert home.status_code == 200
    assert "분석 및 변환" in home.text

    up = client.post(
        "/api/upload",
        files={"file": ("sample.pdf", tiny_pdf_bytes, "application/pdf")},
    )
    assert up.status_code == 200
    body = up.json()
    assert body["ok"] is True
    assert body["status"]["has_pdf"] is True

    conv = client.post("/api/convert")
    assert conv.status_code == 200
    assert conv.json()["status"]["has_brf"] is True
    assert conv.json()["status"]["dtbook_download_available"] is False

    brf = client.get("/api/download/brf")
    assert brf.status_code == 200
    assert len(brf.content) > 0

    dtb = client.get("/api/download/dtbook")
    assert dtb.status_code == 501


def test_developer_bundle_and_page(client, tiny_pdf_bytes: bytes):
    assert client.get("/dev").status_code == 200

    client.post(
        "/api/upload",
        files={"file": ("sample.pdf", tiny_pdf_bytes, "application/pdf")},
    )
    # convert not required — bundle calls ensure_converted
    bundle = client.get("/api/dev/bundle")
    assert bundle.status_code == 200
    data = bundle.json()
    assert data["ok"] is True
    assert "pdf_pages" in data
    assert "braille_pages" in data
    assert data["braille_pages"]
    assert "unicode" in data["braille_pages"][0]
    assert "reverse" in data["braille_pages"][0]
    assert "brf_text" not in data
    assert data["page_numbers"]

    page = data["page_number"]
    png = client.get(f"/api/dev/pdf-page/{page}")
    assert png.status_code == 200
    assert png.headers["content-type"].startswith("image/png")
    assert len(png.content) > 100
