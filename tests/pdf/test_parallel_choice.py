# -*- coding: utf-8 -*-
"""병렬 선택지(①×㉠/㉡) 감지·재조합."""

from pathlib import Path

import pytest

from korean_exam_braille.app.pdf.extractor import extract_pdf
from korean_exam_braille.app.pdf.models import PdfLine, PdfSpan
from korean_exam_braille.app.pdf.parallel_choice import (
    apply_parallel_choices,
    detect_parallel_choices,
    format_parallel_choice_line,
    promote_parallel_choices_in_lines,
)

MARCH_PDF = Path(r"c:\Users\Seongman Hwang\Downloads\2026고2-3월국어.pdf")


def _span(
    sid: str,
    text: str,
    bbox: tuple[float, float, float, float],
    *,
    idx: int = 0,
    size: float = 10.0,
) -> PdfSpan:
    return PdfSpan(
        id=sid,
        text=text,
        bbox=bbox,
        font="Test",
        font_size=size,
        is_bold=False,
        page_number=1,
        extraction_index=idx,
    )


def _q30_spans() -> list[PdfSpan]:
    """30번형: 헤더 ㉠/㉡ + ①~⑤ 각 행에 두 본문 열."""
    spans: list[PdfSpan] = []
    idx = 0

    def add(text: str, x0: float, y0: float, w: float = 80.0, h: float = 12.0) -> None:
        nonlocal idx
        spans.append(
            _span(
                f"s{idx}",
                text,
                (x0, y0, x0 + w, y0 + h),
                idx=idx,
            )
        )
        idx += 1

    add("㉠", 80, 40, 20)
    add("㉡", 220, 40, 20)
    rows = [
        ("①", "주제에서 벗어난", "경험의 다른 사례"),
        ("②", "문맥에 맞지 않는", "경험이 주는 의미"),
        ("③", "문맥에 맞지 않는", "경험으로 인한 감정의 변화"),
        ("④", "앞 문단과 중복되는", "경험의 다른 사례"),
        ("⑤", "앞 문단과 중복되는", "경험으로 인한 감정의 변화"),
    ]
    y = 60.0
    for marker, a, b in rows:
        add(marker, 40, y, 16)
        add(a, 70, y, 120)
        add(b, 210, y, 140)
        y += 18.0
    return spans


def test_format_parallel_choice_line():
    assert (
        format_parallel_choice_line(
            "①",
            ["주제에서 벗어난", "경험의 다른 사례"],
            headers=["㉠", "㉡"],
        )
        == "① ㉠ 주제에서 벗어난 / ㉡ 경험의 다른 사례"
    )
    assert format_parallel_choice_line("①", ["가", "나"]) == "① 가 / 나"


def test_detect_q30_style_parallel_choices():
    hits = detect_parallel_choices(_q30_spans())
    assert len(hits) == 1
    hit = hits[0]
    assert hit.confidence >= 0.78
    assert hit.headers == ["㉠", "㉡"]
    assert len(hit.rows) == 5
    assert hit.rows[0][0] == "①"
    assert hit.rows[0][1][0] == "주제에서 벗어난"
    assert hit.rows[0][1][1] == "경험의 다른 사례"
    assert hit.rows[4][0] == "⑤"


def test_apply_recombines_choice_lines():
    spans = _q30_spans()
    bad_lines = [
        PdfLine(
            id="bad0",
            text="㉠ ㉡",
            bbox=(80, 40, 240, 52),
            span_ids=["s0", "s1"],
            page_number=1,
        ),
        PdfLine(
            id="bad1",
            text="① 주제에서 벗어난 경험의 다른 사례",
            bbox=(40, 60, 350, 72),
            span_ids=["s2", "s3", "s4"],
            page_number=1,
        ),
    ]
    hits = detect_parallel_choices(spans)
    out = apply_parallel_choices(bad_lines, hits, page_number=1)
    texts = [ln.text for ln in out]
    assert "㉠ / ㉡" in texts
    assert any(t.startswith("① ㉠ ") and " / ㉡ " in t for t in texts)
    assert any(t.startswith("⑤ ㉠ ") for t in texts)
    one = next(t for t in texts if t.startswith("① "))
    assert "주제에서 벗어난" in one
    assert "경험의 다른 사례" in one
    assert one.index("주제") < one.index("/")


def test_promote_end_to_end():
    spans = _q30_spans()
    lines = [
        PdfLine(
            id="l0",
            text="noise",
            bbox=(40, 10, 100, 22),
            span_ids=[],
            page_number=1,
        )
    ]
    for s in spans:
        lines.append(
            PdfLine(
                id=f"ln-{s.id}",
                text=s.text,
                bbox=s.bbox,
                span_ids=[s.id],
                page_number=1,
            )
        )
    out = promote_parallel_choices_in_lines(spans, lines, page_number=1)
    assert any(ln.text.startswith("① ㉠ ") for ln in out)
    assert any(ln.text == "㉠ / ㉡" for ln in out)
    assert any(ln.text == "noise" for ln in out)


def test_no_false_positive_on_plain_choices():
    """일반 ① 본문 한 덩어리 선택지는 승격하지 않는다."""
    spans: list[PdfSpan] = []
    y = 50.0
    idx = 0
    for marker, body in [
        ("①", "주제에서 벗어난 내용이다."),
        ("②", "문맥에 맞지 않는 표현이다."),
        ("③", "앞 문단과 중복된다."),
        ("④", "경험의 다른 사례이다."),
        ("⑤", "감정의 변화를 보인다."),
    ]:
        spans.append(_span(f"m{idx}", marker, (40, y, 56, y + 12), idx=idx))
        idx += 1
        spans.append(_span(f"b{idx}", body, (60, y, 280, y + 12), idx=idx))
        idx += 1
        y += 18.0
    assert detect_parallel_choices(spans) == []


def test_no_false_positive_side_markers():
    """질문 본문 + 오른쪽 ①~⑤만 있는 형태는 병렬 선택지가 아니다."""
    spans: list[PdfSpan] = []
    idx = 0
    y = 100.0
    for marker, q in [
        ("①", "경제 활동을 설명하기 위해 가정하는 인간은?"),
        ("②", "제한된 합리성이 의사 결정을 막는 이유는?"),
        ("③", "감정은 어떻게 의사 결정에 영향을 미치는가?"),
        ("④", "추가 질문 네 번째"),
        ("⑤", "추가 질문 다섯 번째"),
    ]:
        spans.append(_span(f"q{idx}", q, (50, y, 320, y + 12), idx=idx))
        idx += 1
        spans.append(_span(f"m{idx}", marker, (360, y, 380, y + 12), idx=idx))
        idx += 1
        y += 40.0
    assert detect_parallel_choices(spans) == []


def test_no_false_positive_page_two_column_choices():
    """선택지(왼쪽)와 본문(오른쪽)이 같은 y에 나란한 페이지 2단은 승격하지 않는다.

    31·35번형: 헤더 ㉠/㉡ 없이 선택지 문장과 지문 조각이 가로로 붙던 오탐.
    """
    spans: list[PdfSpan] = []
    idx = 0
    y = 80.0
    left = [
        "색채어를 활용하여 시적 상황을 부각하고 있다.",
        "반어법을 활용하여 시적 의미를 강조하고 있다.",
        "연쇄법을 사용하여 고조된 감정을 드러내고 있다.",
        "감탄사를 사용하여 대상에 대한 태도를 강조하고 있다.",
        "경어체를 사용하여 대상에 대한 경외감을 드러내고 있다.",
    ]
    right = [
        "자는 ‘태평성세’의 ‘자취’만 남은 현실에서 ‘시름’하는 존재로",
        "자신의 처지를 인식하고 있군.",
        "⑤(나)에서 ‘어쩔 수 없다’는 화자의 말은 나이 든 모습을 담담",
        "하게 수용하는 심리를, (다)에서 ‘돌아갈 날 헤아리’는 화자",
        "의 행동은 궁궐로의 복귀를 바라는 마음을 드러내고 있군.",
    ]
    for i, marker in enumerate("①②③④⑤"):
        spans.append(_span(f"m{idx}", marker, (40, y, 56, y + 12), idx=idx))
        idx += 1
        spans.append(_span(f"l{idx}", left[i], (60, y, 280, y + 12), idx=idx))
        idx += 1
        spans.append(_span(f"r{idx}", right[i], (320, y, 540, y + 12), idx=idx))
        idx += 1
        y += 18.0
    assert detect_parallel_choices(spans) == []


def test_detect_q30_with_left_column_pollution():
    """고1 PDF 실제 오탐 기하: 좌단 지문·우단 ㉠/㉡ 병렬선택지가 같은 y에 섞임."""
    spans: list[PdfSpan] = []
    idx = 0

    def add(text: str, x0: float, y0: float, w: float, h: float = 11.0) -> None:
        nonlocal idx
        spans.append(_span(f"p{idx}", text, (x0, y0, x0 + w, y0 + h), idx=idx, size=11.2))
        idx += 1

    # 헤더 행: 좌단 지문 + ㉠/㉡
    add("았다. 그러자 초라했던 일상이 전보다 특별하게 느껴졌다.", 98, 414, 280)
    add("㉠", 506, 414, 11)
    add("㉡", 650, 414, 11)

    rows = [
        ("①", "주제에서 벗어난", "경험의 다른 사례", "휴대폰을 내려놓고 그림을 그리는 동안, 오늘의 나 역시 조"),
        ("②", "문맥에 맞지 않는", "경험이 주는 의미", "금씩 자라나는 중이라는 깨달음을 얻었다. 앞으로도 자주 그림"),
        ("③", "문맥에 맞지 않는", "경험으로 인한 감정의 변화", "을 그려야겠다고 생각했다."),
        ("④", "앞 문단과 중복되는", "경험의 다른 사례", None),
        ("⑤", "앞 문단과 중복되는", "경험으로 인한 감정의 변화", "28.초고의 글쓰기 방식으로 적절하지 않은 것은?"),
    ]
    y = 436.0
    for marker, a, b, left in rows:
        if left:
            add(left, 98, y, 300)
        add(marker, 439, y, 11)
        add(a, 464, y, 80)
        add(b, 588, y, 85 if len(b) < 12 else 130)
        y += 17.5

    hits = detect_parallel_choices(spans)
    assert len(hits) == 1
    hit = hits[0]
    assert hit.headers == ["㉠", "㉡"]
    assert hit.rows[0][1] == ["주제에서 벗어난", "경험의 다른 사례"]
    assert hit.rows[4][0] == "⑤"
    # 좌단 지문 span이 hit에 섞이면 bbox가 좌로 크게 펼쳐짐 → 금함
    assert hit.bbox[0] >= 400.0
    assert all("휴대폰" not in c and "초고" not in c for _, cols in hit.rows for c in cols)


def test_detect_with_other_column_choice_row_between():
    """좌단 ① 행이 우단 ③·④ 사이 y에 끼어도 ㉠/㉡ 표를 잇는다 (3면 8번형)."""
    spans: list[PdfSpan] = []
    idx = 0

    def add(text: str, x0: float, y0: float, w: float, h: float = 11.0) -> None:
        nonlocal idx
        spans.append(_span(f"q{idx}", text, (x0, y0, x0 + w, y0 + h), idx=idx, size=11.2))
        idx += 1

    add("㉠", 477, 656, 20)
    add("㉡", 585, 656, 20)
    rows = [
        (674, "①", "나모와", "남기"),
        (691, "②", "나모와", "나뫼"),
        (708, "③", "남과", "나뫼"),
        (725, "④", "남과", "남기"),
        (743, "⑤", "남와", "나뫼"),
    ]
    for y, marker, a, b in rows:
        add(marker, 439, y, 11)
        add(a, 472, y, 32)
        add(b, 584, y, 22)
    # 좌단 7번 ①이 ③(708)과 ④(725) 사이에 끼움
    add("①ㄱ:", 98, 718, 40)
    add("‘형이 시키는’이 꾸며 주는 역할을 하는 것으로 보아", 140, 718, 260)

    hits = detect_parallel_choices(spans)
    assert len(hits) == 1
    hit = hits[0]
    assert hit.headers == ["㉠", "㉡"]
    assert [m for m, _ in hit.rows] == ["①", "②", "③", "④", "⑤"]
    assert hit.rows[0][1] == ["나모와", "남기"]
    assert hit.rows[4][1] == ["남와", "나뫼"]
    assert all("형이 시키는" not in c for _, cols in hit.rows for c in cols)

    cut_hits = detect_parallel_choices(spans, column_cut_x=422.6)
    assert len(cut_hits) == 1
    assert cut_hits[0].rows[3][1] == ["남과", "남기"]


def test_promote_interleaved_columns_formats_slash_line():
    spans: list[PdfSpan] = []
    idx = 0

    def add(text: str, x0: float, y0: float, w: float, h: float = 11.0) -> None:
        nonlocal idx
        spans.append(_span(f"r{idx}", text, (x0, y0, x0 + w, y0 + h), idx=idx, size=11.2))
        idx += 1

    add("㉠", 477, 656, 20)
    add("㉡", 585, 656, 20)
    add("①", 439, 674, 11)
    add("나모와", 472, 674, 32)
    add("남기", 584, 674, 22)
    add("②", 439, 691, 11)
    add("나모와", 472, 691, 32)
    add("나뫼", 584, 691, 22)
    add("③", 439, 708, 11)
    add("남과", 477, 708, 22)
    add("나뫼", 584, 708, 22)
    add("④", 439, 725, 11)
    add("남과", 477, 725, 22)
    add("남기", 584, 725, 22)
    add("⑤", 439, 743, 11)
    add("남와", 477, 743, 22)
    add("나뫼", 584, 743, 22)
    add("①ㄱ:", 98, 718, 40)

    glued = [
        PdfLine(
            id="g0",
            text="①나모와남기",
            bbox=(439, 674, 606, 685),
            span_ids=["r2", "r3", "r4"],
            page_number=1,
        )
    ]
    out = promote_parallel_choices_in_lines(spans, glued, page_number=1)
    assert any(ln.text == "① ㉠ 나모와 / ㉡ 남기" for ln in out)
    assert any(ln.text == "⑤ ㉠ 남와 / ㉡ 나뫼" for ln in out)


@pytest.mark.skipif(not MARCH_PDF.exists(), reason="2026고2-3월 PDF not found")
def test_exam_page3_q8_parallel_ganada_columns():
    extracted = extract_pdf(MARCH_PDF, page_numbers=[3])
    page = extracted.pages[0]
    texts = [ln.text or "" for ln in page.lines]
    joined = "\n".join(texts)
    assert "① ㉠ 나모와 / ㉡ 남기" in joined
    assert "⑤ ㉠ 남와 / ㉡ 나뫼" in joined
    assert "①나모와남기" not in joined
