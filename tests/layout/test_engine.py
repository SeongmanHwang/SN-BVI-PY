"""레이아웃·직렬화 테스트."""

from korean_exam_braille.app.braille.models import BrailleSequence, BrailleToken
from korean_exam_braille.app.layout.engine import RuleBrailleLayoutEngine
from korean_exam_braille.app.layout.models import LayoutProfile
from korean_exam_braille.app.layout.serializer import AsciiBrfSerializer


def _seq(ascii_text: str, node_type: str, node_id: str = "n1") -> BrailleSequence:
    return BrailleSequence(
        source_node_id=node_id,
        tokens=[
            BrailleToken(
                source_text=ascii_text,
                token_type="text",
                cells=[],
                metadata={"ascii": ascii_text},
            )
        ],
        metadata={"ascii": ascii_text, "node_type": node_type},
    )


def test_wrap_and_choice_indent():
    engine = RuleBrailleLayoutEngine()
    profile = LayoutProfile(cells_per_line=10, choice_indent=2, lines_per_page=26)
    long = "abcdefghijKLMNOP"  # > 10
    doc = engine.layout(
        [_seq(long, "Choice")],
        profile=profile,
    )
    assert doc.pages
    lines = [ln for ln in doc.pages[0].lines if ln.ascii_text]
    assert lines
    assert lines[0].ascii_text.startswith("  ")
    assert all(len(ln.ascii_text) <= 10 for ln in lines)


def test_page_break_and_form_feed():
    engine = RuleBrailleLayoutEngine()
    profile = LayoutProfile(
        cells_per_line=32,
        lines_per_page=6,
        top_margin=1,
        bottom_margin=1,
    )
    seqs = [_seq(f"line{i}", "Passage", node_id=f"p{i}") for i in range(9)]
    doc = engine.layout(seqs, profile=profile)
    assert len(doc.pages) >= 2
    text = AsciiBrfSerializer().serialize(doc)
    assert "\x0c" in text


def test_continuation_page_does_not_drop_lines():
    """이어지는 면 앞 빈 줄 삽입이 본문 줄을 절단·유실하면 안 된다."""
    from korean_exam_braille.app.braille.translator import hangul_text_to_ascii
    from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line

    engine = RuleBrailleLayoutEngine()
    # 면당 5줄: 빈 줄 삽입 시 예전 코드는 마지막 줄을 버림
    profile = LayoutProfile(cells_per_line=32, lines_per_page=5, paragraph_indent=2)
    fill = hangul_text_to_ascii("줄")
    target = hangul_text_to_ascii(
        "으로 표기해야 일관성이 있겠지요? 하지만 당시에 ‘윽, 읃, 읏’으로 "
        "소리 나는 한자가 없었습니다. 그래서 ‘ㄱ’은 ‘윽’을 대"
    )
    seqs = [_seq(fill, "Passage", node_id=f"f{i}") for i in range(6)]
    seqs.append(_seq(target, "Passage", node_id="t"))
    doc = engine.layout(seqs, profile=profile)

    ascii_lines = [
        ln.ascii_text
        for page in doc.pages
        for ln in page.lines
        if ln.ascii_text is not None
    ]
    # 점역 ASCII에 있던 핵심 구간이 레이아웃 후에도 남아 있어야 한다
    joined = "\n".join(ascii_lines)
    assert "['0'[" in joined or "0'[" in joined
    rev = "\n".join(
        reverse_translate_line(s) for s in ascii_lines if s.strip()
    )
    assert "읏" in rev
    assert "으로 소리" in rev.replace("\n", "")
    # 모든 비어 있지 않은 입력 줄 수가 출력에서 유지되는지 (시작 빈 줄·면 빈 줄 제외한 하한)
    content_in = sum(1 for s in ascii_lines if s.strip())
    assert content_in >= 8


def test_separator_after_passage_group():
    engine = RuleBrailleLayoutEngine()
    doc = engine.layout(
        [
            _seq("[1~3] next", "PassageGroup"),
            _seq("passage body", "Passage"),
        ]
    )
    ascii_lines = [ln.ascii_text for ln in doc.pages[0].lines]
    sep_idx = next(
        i for i, s in enumerate(ascii_lines) if "g" in s.lower() and s.startswith("=")
    )
    assert any("82" in s or "1" in s or "[" in s or "next" in s for s in ascii_lines[:sep_idx])
    assert any("passage" in s for s in ascii_lines[sep_idx + 1 :])

