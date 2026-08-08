# -*- coding: utf-8 -*-
"""벡터 박스 검출: 중복 선 병합·낮은 [가] 박스·짧은 세로선 이어붙이기."""

from __future__ import annotations

from pathlib import Path

import fitz

from korean_exam_braille.app.pdf.boxes import (
    _dedupe_segments,
    _merge_collinear,
    iter_box_rects,
    iter_long_horizontal_rules,
)
from korean_exam_braille.app.pdf.emphasis import iter_horizontal_underline_segments


def _draw_line(page: fitz.Page, x0: float, y0: float, x1: float, y1: float) -> None:
    page.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y1), width=0.6)


def test_dedupe_near_identical_segments():
    segs = [
        (136.65, 398.92, 923.84),
        (136.70, 398.90, 923.90),  # <0.5pt 차이 → 중복
        (136.65, 398.92, 938.11),
    ]
    out = _dedupe_segments(segs)
    assert len(out) == 2


def test_merge_short_vertical_stubs():
    # 큰 제시문 좌측: 짧은 세로선이 이어진 형태
    stubs = [
        (800.0, 814.0, 87.7),
        (814.5, 828.0, 87.65),
        (828.2, 900.0, 87.72),
        (900.5, 960.3, 87.68),
    ]
    merged = _merge_collinear(stubs)
    assert len(merged) == 1
    y0, y1, x = merged[0]
    assert abs(x - 87.7) < 1.0
    assert y0 <= 800.5 and y1 >= 960.0


def test_small_blank_box_and_passage_bottom(tmp_path: Path):
    """실측 패턴: [가] 낮은 4변 박스(중복 선) + 제시문 긴 하단선 + 짧은 세로 조각."""
    path = tmp_path / "talk_boxes.pdf"
    doc = fitz.open()
    page = doc.new_page(width=500, height=1100)

    # 큰 제시문: 좌우 짧은 세로 + 긴 상·하단
    left_x, right_x = 87.7, 412.0
    top_y, bottom_y = 700.0, 960.30
    for y0, y1 in ((700.0, 760.0), (760.5, 860.0), (860.5, 960.30)):
        _draw_line(page, left_x, y0, left_x, y1)
        _draw_line(page, right_x, y0, right_x, y1)
    _draw_line(page, left_x, top_y, right_x, top_y)
    _draw_line(page, 87.62, bottom_y, 412.23, bottom_y)

    # [가] 빈칸 박스 (~14pt 높이), 각 변 2번씩 중복
    gx0, gx1, gy0, gy1 = 136.65, 398.92, 923.84, 938.11
    for _ in range(2):
        _draw_line(page, gx0, gy0, gx1, gy0)
        _draw_line(page, gx0, gy1, gx1, gy1)
        _draw_line(page, gx0, gy0, gx0, gy1)
        _draw_line(page, gx1, gy0, gx1, gy1)

    doc.save(path)
    doc.close()

    page = fitz.open(path)[0]
    boxes = iter_box_rects(page)
    rules = iter_long_horizontal_rules(page)

    small = [
        b
        for b in boxes
        if abs(b[0] - gx0) < 3
        and abs(b[2] - gx1) < 3
        and abs(b[1] - gy0) < 3
        and abs(b[3] - gy1) < 3
    ]
    assert small, f"[가] box missing in {boxes!r}"
    assert (small[0][3] - small[0][1]) < 28.0

    large = [
        b
        for b in boxes
        if abs(b[0] - left_x) < 5
        and abs(b[2] - right_x) < 5
        and abs(b[3] - bottom_y) < 5
    ]
    assert large, f"passage box missing in {boxes!r}"

    bottoms = [r for r in rules if abs(r[2] - bottom_y) < 1.0 and r[1] - r[0] > 200]
    assert bottoms, f"passage bottom rule missing in {rules!r}"


def test_box_edges_are_not_underlines():
    """낮은 [가] 박스와 큰 제시문 하단을 밑줄 후보에서 제외한다."""
    doc = fitz.open()
    page = doc.new_page(width=850, height=1100)

    # [가] 박스: 페이지 폭의 42%보다 짧아 기존 폭 필터만으로는 제외되지 않음.
    gx0, gx1, gy0, gy1 = 136.65, 398.92, 923.84, 938.11
    _draw_line(page, gx0, gy0, gx1, gy0)
    _draw_line(page, gx0, gy1, gx1, gy1)
    _draw_line(page, gx0, gy0, gx0, gy1)
    _draw_line(page, gx1, gy0, gx1, gy1)

    # 큰 제시문 박스 하단도 같은 폭 필터를 통과할 수 있음.
    _draw_line(page, 87.62, 960.30, 412.23, 960.30)
    _draw_line(page, 87.62, 700.0, 87.62, 960.30)
    _draw_line(page, 412.23, 700.0, 412.23, 960.30)
    _draw_line(page, 87.62, 700.0, 412.23, 700.0)

    # 실제 밑줄은 보존되어야 함.
    _draw_line(page, 500.0, 900.0, 570.0, 900.0)

    segs = iter_horizontal_underline_segments(page)
    assert any(abs(x0 - 500.0) < 1 and abs(x1 - 570.0) < 1 for x0, x1, _y in segs)
    assert not any(abs(y - gy0) < 1 or abs(y - gy1) < 1 for _x0, _x1, y in segs)
    assert not any(abs(y - 960.30) < 1 for _x0, _x1, y in segs)
    doc.close()
