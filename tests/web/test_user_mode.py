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
    assert conv.json()["status"]["dtbook_download_available"] is True

    brf = client.get("/api/download/brf")
    assert brf.status_code == 200
    assert len(brf.content) > 0

    dtb = client.get("/api/download/dtbook")
    assert dtb.status_code == 200
    assert b"dtbook" in dtb.content.lower()
    assert b"2005-3" in dtb.content


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
    page0 = data["pdf_pages"][0]
    assert "blocks" in page0
    assert "width" in page0 and "height" in page0
    root = data["exam_tree"]["root"]
    assert "block_ids" in root or "children" in root

    page = data["page_number"]
    png = client.get(f"/api/dev/pdf-page/{page}")
    assert png.status_code == 200
    assert png.headers["content-type"].startswith("image/png")
    assert len(png.content) > 100


def test_developer_review_mode_reference_brf(client, tiny_pdf_bytes: bytes):
    client.post(
        "/api/upload",
        files={"file": ("sample.pdf", tiny_pdf_bytes, "application/pdf")},
    )
    client.post("/api/convert")
    brf = client.get("/api/download/brf")
    assert brf.status_code == 200
    generated = brf.content

    # 참고본: 첫 비공백 행을 살짝 바꿈
    text = generated.decode("utf-8", errors="replace")
    lines = text.splitlines(keepends=True)
    tweaked = []
    changed = False
    for line in lines:
        if not changed and line.strip() and "\x0c" not in line:
            tweaked.append(("X" + line[1:]) if len(line) > 1 else "X\n")
            changed = True
        else:
            tweaked.append(line)
    reference = "".join(tweaked).encode("utf-8")

    missing = client.get("/api/dev/review")
    assert missing.status_code == 400

    up = client.post(
        "/api/dev/reference-brf",
        files={"file": ("vendor.brf", reference, "text/plain")},
    )
    assert up.status_code == 200
    assert up.json()["ok"] is True
    assert up.json()["status"]["has_reference_brf"] is True

    review = client.get("/api/dev/review")
    assert review.status_code == 200
    body = review.json()
    assert body["ok"] is True
    assert body["reference_name"] == "vendor.brf"
    assert body["review_pages"]
    page0 = body["review_pages"][0]
    assert "generated" in page0 and "reference" in page0
    assert "unicode_lines" in page0["generated"]
    assert "mismatch" in page0["generated"]["unicode_lines"][0]
    assert "compare" in body
    assert "cell_match_ratio" in body["compare"]

    # UI에 모드 C 진입점
    dev = client.get("/dev")
    assert "모드 C" in dev.text
    assert "review-gen-braille" in dev.text
