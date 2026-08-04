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
    lines = doc.pages[0].lines
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
    # usable = 4 lines
    seqs = [_seq(f"line{i}", "Passage", node_id=f"p{i}") for i in range(9)]
    doc = engine.layout(seqs, profile=profile)
    assert len(doc.pages) >= 2
    text = AsciiBrfSerializer().serialize(doc)
    assert "\x0c" in text


def test_separator_before_example_box():
    engine = RuleBrailleLayoutEngine()
    doc = engine.layout(
        [
            _seq("passage", "Passage"),
            _seq("<보기>", "ExampleBox"),
        ]
    )
    ascii_lines = [ln.ascii_text for ln in doc.pages[0].lines]
    assert any(
        ("g" in s.lower() or set(s.replace(" ", "")) <= {"="}) and len(s) >= 6
        for s in ascii_lines
    )
