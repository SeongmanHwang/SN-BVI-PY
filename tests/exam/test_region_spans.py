"""Mode B: RegionSpan 시작·끝을 괄호 도형으로 잡고 겹치는 Passage 전부에 [A]를 붙인다."""

from __future__ import annotations

from pathlib import Path

import pytest

from korean_exam_braille.app.exam.builder import RuleExamStructureBuilder
from korean_exam_braille.app.pdf.bracket_groups import build_region_spans
from korean_exam_braille.app.pdf.extractor import extract_pdf

MARCH_PDF = Path(r"c:\Users\Seongman Hwang\Downloads\2026고2-3월국어.pdf")


def _plain(text: str | None) -> str:
    raw = (text or "").replace("\n", " ")
    for tag in ("<u>", "</u>"):
        raw = raw.replace(tag, "")
    return raw.lstrip(" \"“”").strip()


@pytest.mark.skipif(not MARCH_PDF.exists(), reason="2026고2-3월 PDF not found")
def test_mode_b_projects_region_a_onto_all_overlapping_passages():
    pdf = extract_pdf(MARCH_PDF, page_numbers=[14, 15])
    layout = (pdf.metadata or {}).get("layout_profile")
    cut = float(layout["column_cut_x"]) if isinstance(layout, dict) else None
    regions = build_region_spans(pdf.pages, column_cut_x=cut)
    region = next(r for r in regions if r.label == "[A]")
    assert _plain(region.start_text).startswith("사람이 사람 구실을 하려면")
    assert _plain(region.end_text).endswith("할아버지가 발끈했다.")

    exam = RuleExamStructureBuilder().build(pdf)
    group = next(
        node
        for node in exam.root.children
        if node.node_type == "PassageGroup"
    )
    passages = [c for c in group.children if c.node_type == "Passage"]

    labeled = [
        p
        for p in passages
        if "[A]" in (p.metadata.get("bracket_labels") or [])
    ]
    assert labeled
    assert _plain(labeled[0].source_range.raw_text).startswith(
        "사람이 사람 구실을 하려면"
    )
    assert any(
        _plain(p.source_range.raw_text).endswith("할아버지가 발끈했다.")
        or "할아버지가 발끈했다" in _plain(p.source_range.raw_text)
        for p in labeled
    )
    starts = [
        p for p in labeled if "[A]" in (p.metadata.get("bracket_start_labels") or [])
    ]
    ends = [
        p for p in labeled if "[A]" in (p.metadata.get("bracket_end_labels") or [])
    ]
    assert len(starts) == 1
    assert len(ends) == 1

    outside = next(
        p
        for p in passages
        if _plain(p.source_range.raw_text).startswith("아니, 약혼식 날")
    )
    assert "[A]" not in (outside.metadata.get("bracket_labels") or [])

    before = next(
        p
        for p in passages
        if "아무 일도 없어" in _plain(p.source_range.raw_text)
        and "사람이 사람 구실을 하려면" not in _plain(p.source_range.raw_text)
    )
    assert "[A]" not in (before.metadata.get("bracket_labels") or [])
