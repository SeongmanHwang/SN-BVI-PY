"""BRF 파일 파서 — 행·빈 줄·폼피드를 손실 없이 보존한다."""

from __future__ import annotations

from pathlib import Path

from korean_exam_braille.app.brf.ascii_braille import FORM_FEED, ascii_to_unicode
from korean_exam_braille.app.brf.models import BrfDocument, BrfLine, BrfPage
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line
from korean_exam_braille.app.brf.structure_detect import detect_line_candidates


def _decode_bytes(data: bytes) -> tuple[str, str]:
    for encoding in ("utf-8", "utf-8-sig", "cp949", "latin-1"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8-replace"


def _split_pages(text: str) -> tuple[list[str], bool]:
    """폼피드로 면을 나누고, 원본 행 끝 개행 스타일은 면 내부에서 유지한다."""
    has_trailing_ff = text.endswith(FORM_FEED)
    # 끝의 폼피드만 제거해 split 후 빈 페이지가 생기지 않게 함
    body = text[:-1] if has_trailing_ff else text
    if not body:
        return [""], has_trailing_ff
    pages = body.split(FORM_FEED)
    return pages, has_trailing_ff


def _split_lines_preserve(page_text: str) -> list[str]:
    """페이지 텍스트를 행 목록으로 분리. 마지막 개행만 있는 빈 꼬리는 유지하지 않음.

    - 빈 페이지 → 빈 행 0개
    - "a\\n" → ["a"]  (파일에서 행 끝 개행은 행 구분자)
    - "a\\nb" → ["a", "b"]
    - "a\\nb\\n" → ["a", "b"]
    - "\\n" → [""]  (빈 줄 하나)
    - "a\\n\\nb" → ["a", "", "b"]
    """
    if page_text == "":
        return []
    # 통일: \r\n, \r → \n 후 분리. 원본 바이트 재직렬화 시 \n 사용.
    normalized = page_text.replace("\r\n", "\n").replace("\r", "\n")
    if normalized.endswith("\n"):
        normalized = normalized[:-1]
    return normalized.split("\n")


def parse_brf_text(text: str, *, source_path: str | None = None, encoding: str = "utf-8") -> BrfDocument:
    page_texts, has_trailing_ff = _split_pages(text)
    pages: list[BrfPage] = []
    global_index = 0

    for page_index, page_text in enumerate(page_texts):
        raw_lines = _split_lines_preserve(page_text)
        page = BrfPage(page_index=page_index)
        for line_index, raw in enumerate(raw_lines):
            unicode_braille = ascii_to_unicode(raw)
            reverse_text = reverse_translate_line(raw)
            candidates = detect_line_candidates(raw, reverse_text)
            line = BrfLine(
                global_index=global_index,
                page_index=page_index,
                line_index=line_index,
                raw_ascii=raw,
                unicode_braille=unicode_braille,
                reverse_text=reverse_text,
                candidate_tags=candidates,
            )
            page.lines.append(line)
            global_index += 1
        pages.append(page)

    return BrfDocument(
        source_path=source_path,
        pages=pages,
        encoding=encoding,
        has_trailing_formfeed=has_trailing_ff,
    )


def load_brf(path: str | Path) -> BrfDocument:
    path = Path(path)
    data = path.read_bytes()
    text, encoding = _decode_bytes(data)
    return parse_brf_text(text, source_path=str(path), encoding=encoding)


def serialize_brf(document: BrfDocument) -> str:
    """문서를 BRF 텍스트로 직렬화. 행·빈 줄·폼피드를 재현한다."""
    page_chunks: list[str] = []
    for page in document.pages:
        # 각 면: 행을 \n으로 잇고, 면 안에 행이 있으면 마지막에도 \n을 붙이지 않음
        # 표준 BRF는 보통 각 행 뒤에 \n, 면 사이에 \f
        if not page.lines:
            page_chunks.append("")
            continue
        lines = [line.raw_ascii for line in page.lines]
        # 관례: 각 행 끝에 개행. 마지막 행 뒤에도 개행을 두어 면 경계가 명확히 보이게 함.
        page_chunks.append("\n".join(lines) + "\n")

    text = FORM_FEED.join(page_chunks)
    if document.has_trailing_formfeed and not text.endswith(FORM_FEED):
        text += FORM_FEED
    return text


def save_brf(document: BrfDocument, path: str | Path | None = None) -> Path:
    target = Path(path or document.source_path or "output.brf")
    text = serialize_brf(document)
    # 원본이 latin-1/cp949여도 BRF ASCII는 7bit이므로 utf-8로 저장해도 내용 동일
    target.write_text(text, encoding="utf-8", newline="\n")
    document.source_path = str(target)
    return target


def refresh_derived_fields(document: BrfDocument) -> None:
    """태그 외 파생 필드(유니코드·역점역·후보)를 다시 계산."""
    for line in document.lines:
        line.unicode_braille = ascii_to_unicode(line.raw_ascii)
        line.reverse_text = reverse_translate_line(line.raw_ascii)
        line.candidate_tags = detect_line_candidates(line.raw_ascii, line.reverse_text)
