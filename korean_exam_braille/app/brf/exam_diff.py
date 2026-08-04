"""생성 BRF ↔ 참고(시각장애용) BRF 내용 비교.

참고본에만 있는 안내문·머리말 등은 '예상 차이'로 분류하고,
지문·문항 앵커로 맞춘 구간에서만 내용 불일치를 '오류 후보'로 본다.
줄번호 정렬(compare.py)과 달리 문서 구조 차이를 허용한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from korean_exam_braille.app.brf.models import BrfDocument
from korean_exam_braille.app.brf.parser import load_brf, parse_brf_text
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line

# 앵커 (ASCII / 묵자)
_PASSAGE_ASCII = re.compile(r"82#[a-jA-J]+`9#[a-jA-J]+;0")
_QUESTION_ASCII = re.compile(r"^\s*#([a-jA-J]+)4\b")
_PASSAGE_INK = re.compile(
    r"\[\s*\d{1,2}\s*[~\-–—～]\s*\d{1,2}\s*\]"
    r"|다음.+(물음|발표|글|토의)"
)
_QUESTION_INK = re.compile(r"^\s*(\d{1,2})\s*[\.．。]")

# 참고본에만 있을 법한 안내·메타
_GUIDANCE_INK = re.compile(
    r"안내|유의\s*사항|점자\s*문제|시각\s*장애|이\s*문제지"
    r"|답안지|컴퓨터용|사인펜|수정\s*테이프|문항\s*번호"
    r"|선택지|해당\s*번호|뒷면|넘기|끝\s*입니다|수고"
    r"|점역|점자\s*교재|점자\s*도서"
)

_SEP_ASCII = re.compile(r"^=[gG=.\-_]*=")


@dataclass
class BrfLineView:
    page_index: int
    line_index: int
    ascii: str
    ink: str
    kind: str  # blank | separator | passage_group | question | guidance | body


@dataclass
class ContentSegment:
    key: str  # e.g. passage:1-3 / question:16 / preamble / trailer
    kind: str
    lines: list[BrfLineView] = field(default_factory=list)

    @property
    def ink_text(self) -> str:
        return "\n".join(ln.ink for ln in self.lines if ln.ink.strip())

    @property
    def ascii_text(self) -> str:
        return "\n".join(ln.ascii for ln in self.lines)


@dataclass
class SegmentDiff:
    classification: str
    # expected_guidance | expected_layout | missing_in_generated
    # missing_in_reference | content_mismatch | aligned_ok
    key: str
    score: float
    generated_ink: str
    reference_ink: str
    detail: str = ""


@dataclass
class ExamDiffReport:
    generated_segments: int
    reference_segments: int
    aligned: int
    aligned_ok: int
    content_mismatches: list[SegmentDiff] = field(default_factory=list)
    expected_diffs: list[SegmentDiff] = field(default_factory=list)
    missing_in_generated: list[SegmentDiff] = field(default_factory=list)
    missing_in_reference: list[SegmentDiff] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def summary(self, *, max_items: int = 8) -> str:
        lines = [
            "=== 시험 내용 비교 (안내문 허용) ===",
            f"구간 생성 {self.generated_segments} / 참고 {self.reference_segments}",
            f"정렬됨 {self.aligned} · 내용 일치 {self.aligned_ok}",
            f"오류 후보(내용 불일치) {len(self.content_mismatches)}",
            f"예상 차이(안내·레이아웃 등) {len(self.expected_diffs)}",
            f"생성에 없음 {len(self.missing_in_generated)} · "
            f"참고에 없음 {len(self.missing_in_reference)}",
        ]
        if self.content_mismatches:
            lines.append("")
            lines.append("> 오류 후보")
            for d in self.content_mismatches[:max_items]:
                lines.append(f"  [{d.key}] 유사도 {d.score:.0%} — {d.detail}")
                lines.append(f"    gen: {_clip(d.generated_ink)}")
                lines.append(f"    ref: {_clip(d.reference_ink)}")
            if len(self.content_mismatches) > max_items:
                lines.append(
                    f"  … 외 {len(self.content_mismatches) - max_items}건"
                )
        if self.expected_diffs:
            lines.append("")
            lines.append("> 예상 차이 (참고에만 있는 안내·메타 등)")
            for d in self.expected_diffs[:max_items]:
                lines.append(f"  [{d.key}] {d.detail}")
                lines.append(f"    ref: {_clip(d.reference_ink)}")
            if len(self.expected_diffs) > max_items:
                lines.append(f"  … 외 {len(self.expected_diffs) - max_items}건")
        if self.missing_in_generated:
            lines.append("")
            lines.append("> 생성본에 없는 시험 구간 (참고에만 있음)")
            for d in self.missing_in_generated[:max_items]:
                lines.append(f"  [{d.key}] {_clip(d.reference_ink)}")
        if self.missing_in_reference:
            lines.append("")
            lines.append("> 참고본에 없는 생성 구간")
            for d in self.missing_in_reference[:max_items]:
                lines.append(f"  [{d.key}] {_clip(d.generated_ink)}")
        return "\n".join(lines)


def _clip(text: str, n: int = 72) -> str:
    t = text.replace("\n", " ").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def _norm_ink(text: str) -> str:
    t = text.lower()
    t = re.sub(r"\s+", "", t)
    t = re.sub(r"[·\.\?\!\,\;\:\'\"\"\"''\[\]\(\)<>〈〉【】]", "", t)
    t = t.replace("～", "~").replace("—", "-").replace("–", "-")
    return t


def _digit_braille_to_int(cells: str) -> int | None:
    mapping = dict(zip("abcdefghij", "1234567890"))
    digits = "".join(mapping.get(c.lower(), "") for c in cells)
    return int(digits) if digits.isdigit() else None


def _classify_line(ascii_text: str, ink: str) -> str:
    s = ascii_text.strip()
    if not s:
        return "blank"
    if _SEP_ASCII.match(s) or (
        len(s) >= 6 and set(s.replace(" ", "")) <= set("=gG-._*")
    ):
        return "separator"
    if _PASSAGE_ASCII.search(s) or _PASSAGE_INK.search(ink):
        return "passage_group"
    if _QUESTION_ASCII.match(s) or _QUESTION_INK.match(ink):
        return "question"
    if _GUIDANCE_INK.search(ink):
        return "guidance"
    return "body"


def _passage_key(ascii_text: str, ink: str) -> str:
    m = _PASSAGE_ASCII.search(ascii_text)
    if m:
        body = m.group(0)
        # 82#a`9#c;0
        parts = re.findall(r"#([a-jA-J]+)", body)
        if len(parts) >= 2:
            a = _digit_braille_to_int(parts[0])
            b = _digit_braille_to_int(parts[1])
            if a is not None and b is not None:
                return f"passage:{a}-{b}"
    m2 = re.search(r"\[\s*(\d{1,2})\s*[~\-–—～]\s*(\d{1,2})\s*\]", ink)
    if m2:
        return f"passage:{int(m2.group(1))}-{int(m2.group(2))}"
    return "passage:unknown"


def _question_key(ascii_text: str, ink: str) -> str:
    m = _QUESTION_ASCII.match(ascii_text.strip())
    if m:
        n = _digit_braille_to_int(m.group(1))
        if n is not None:
            return f"question:{n}"
    m2 = _QUESTION_INK.match(ink)
    if m2:
        return f"question:{int(m2.group(1))}"
    return "question:unknown"


def document_to_line_views(doc: BrfDocument) -> list[BrfLineView]:
    out: list[BrfLineView] = []
    for page in doc.pages:
        for ln in page.lines:
            ink = reverse_translate_line(ln.raw_ascii)
            kind = _classify_line(ln.raw_ascii, ink)
            out.append(
                BrfLineView(
                    page_index=page.page_index,
                    line_index=ln.line_index,
                    ascii=ln.raw_ascii,
                    ink=ink,
                    kind=kind,
                )
            )
    return out


def segment_lines(lines: list[BrfLineView]) -> list[ContentSegment]:
    """앵커(지문묶음·문항) 기준으로 구간 분할."""
    segments: list[ContentSegment] = []
    current = ContentSegment(key="preamble", kind="preamble")

    def flush() -> None:
        nonlocal current
        if current.lines:
            # 빈·구분선만이면 preamble/trailer guidance로
            useful = [
                ln
                for ln in current.lines
                if ln.kind not in {"blank", "separator"}
            ]
            if useful or current.kind in {"passage_group", "question"}:
                segments.append(current)
        current = ContentSegment(key="body", kind="body")

    for ln in lines:
        if ln.kind == "passage_group":
            flush()
            key = _passage_key(ln.ascii, ln.ink)
            current = ContentSegment(key=key, kind="passage_group", lines=[ln])
        elif ln.kind == "question":
            flush()
            key = _question_key(ln.ascii, ln.ink)
            current = ContentSegment(key=key, kind="question", lines=[ln])
        else:
            if not current.lines and current.kind == "body":
                current = ContentSegment(key="preamble", kind="preamble")
            current.lines.append(ln)
    flush()

    # trailing rename last orphan body after last question
    if segments and segments[0].kind == "preamble":
        ink = segments[0].ink_text
        if not ink.strip():
            segments.pop(0)
        elif _looks_like_guidance_block(segments[0]):
            segments[0].key = "guidance:preamble"
            segments[0].kind = "guidance"

    return segments


def _looks_like_guidance_block(seg: ContentSegment) -> bool:
    ink = seg.ink_text
    if not ink.strip():
        return True
    if _GUIDANCE_INK.search(ink):
        return True
    # 시험 앵커(지문 묶음·문항)가 없는 머리말·꼬리말은 안내·메타로 본다
    if seg.kind in {"preamble", "guidance", "body"}:
        has_anchor = bool(
            _PASSAGE_INK.search(ink)
            or _QUESTION_INK.search(ink)
            or _PASSAGE_ASCII.search(seg.ascii_text)
            or _QUESTION_ASCII.search(seg.ascii_text)
        )
        if not has_anchor:
            return True
    return False


def _similarity(a: str, b: str) -> float:
    na, nb = _norm_ink(a), _norm_ink(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def compare_exam_content(
    generated: BrfDocument | str,
    reference: BrfDocument | str | Path,
    *,
    match_threshold: float = 0.72,
) -> ExamDiffReport:
    """내용 중심 비교 리포트."""
    gen_doc = (
        generated
        if isinstance(generated, BrfDocument)
        else parse_brf_text(generated)
    )
    if isinstance(reference, BrfDocument):
        ref_doc = reference
    elif isinstance(reference, Path) or (
        isinstance(reference, str) and Path(reference).exists()
    ):
        ref_doc = load_brf(reference)
    else:
        ref_doc = parse_brf_text(str(reference))

    gen_segs = segment_lines(document_to_line_views(gen_doc))
    ref_segs = segment_lines(document_to_line_views(ref_doc))

    gen_map = {s.key: s for s in gen_segs if s.kind in {"passage_group", "question"}}
    ref_map = {s.key: s for s in ref_segs if s.kind in {"passage_group", "question"}}

    content_mismatches: list[SegmentDiff] = []
    expected: list[SegmentDiff] = []
    missing_gen: list[SegmentDiff] = []
    missing_ref: list[SegmentDiff] = []
    aligned_ok = 0
    aligned = 0

    # 참고 preamble/guidance → 예상 차이
    for seg in ref_segs:
        if seg.kind in {"guidance", "preamble"} or seg.key.startswith("guidance:"):
            if _looks_like_guidance_block(seg) or seg.kind == "guidance":
                expected.append(
                    SegmentDiff(
                        classification="expected_guidance",
                        key=seg.key,
                        score=0.0,
                        generated_ink="",
                        reference_ink=seg.ink_text,
                        detail="참고본 안내·머리말 등으로 보임",
                    )
                )

    keys = sorted(set(gen_map) | set(ref_map), key=_key_sort)
    for key in keys:
        g = gen_map.get(key)
        r = ref_map.get(key)
        if g and r:
            aligned += 1
            score = _similarity(g.ink_text, r.ink_text)
            if score >= match_threshold:
                aligned_ok += 1
            else:
                content_mismatches.append(
                    SegmentDiff(
                        classification="content_mismatch",
                        key=key,
                        score=score,
                        generated_ink=g.ink_text,
                        reference_ink=r.ink_text,
                        detail="정렬된 구간 내용 불일치",
                    )
                )
        elif r and not g:
            # 참고에만 있는 문항/지문 — 오류 가능성 높음
            missing_gen.append(
                SegmentDiff(
                    classification="missing_in_generated",
                    key=key,
                    score=0.0,
                    generated_ink="",
                    reference_ink=r.ink_text,
                    detail="생성본에 해당 구간 없음",
                )
            )
        elif g and not r:
            missing_ref.append(
                SegmentDiff(
                    classification="missing_in_reference",
                    key=key,
                    score=0.0,
                    generated_ink=g.ink_text,
                    reference_ink="",
                    detail="참고본에 해당 구간 없음(또는 앵커 인식 실패)",
                )
            )

    return ExamDiffReport(
        generated_segments=len(gen_segs),
        reference_segments=len(ref_segs),
        aligned=aligned,
        aligned_ok=aligned_ok,
        content_mismatches=sorted(
            content_mismatches, key=lambda d: d.score
        ),
        expected_diffs=expected,
        missing_in_generated=missing_gen,
        missing_in_reference=missing_ref,
        metadata={
            "match_threshold": match_threshold,
            "gen_keys": list(gen_map),
            "ref_keys": list(ref_map),
        },
    )


def _key_sort(key: str) -> tuple:
    if key.startswith("passage:"):
        rest = key.split(":", 1)[1]
        try:
            a, b = rest.split("-")
            return (0, int(a), int(b))
        except ValueError:
            return (0, 0, 0)
    if key.startswith("question:"):
        try:
            return (1, int(key.split(":")[1]), 0)
        except ValueError:
            return (1, 0, 0)
    return (2, 0, 0)


def compare_pdf_to_reference_brf(
    pdf_path: str | Path,
    reference_brf: str | Path,
    *,
    page_numbers: list[int] | None = None,
    match_threshold: float = 0.72,
) -> ExamDiffReport:
    """PDF를 파이프라인으로 변환한 뒤 참고 BRF와 내용 비교."""
    from korean_exam_braille.app.pipeline import default_pipeline

    result = default_pipeline().run(pdf_path, page_numbers=page_numbers)
    report = compare_exam_content(
        result.brf_text,
        reference_brf,
        match_threshold=match_threshold,
    )
    report.metadata["pdf_path"] = str(pdf_path)
    report.metadata["pipeline_warnings"] = list(result.warnings)
    report.metadata["stages"] = result.metadata.get("stages")
    return report
