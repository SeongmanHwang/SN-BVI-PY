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

