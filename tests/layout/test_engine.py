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


def test_wrap_reopens_roman_sign_on_continuation():
    """영문 줄바꿈 시 이어지는 줄에 로마자표(0)를 다시 넣는다."""
    from korean_exam_braille.app.braille.translator import (
        hangul_text_to_ascii_with_roman_mask,
    )
    from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line
    from korean_exam_braille.app.layout.engine import _wrap_ascii

    ascii_text, mask = hangul_text_to_ascii_with_roman_mask(
        "CIF(Cost, Insurance and Freight), DDP(Delivered Duty Paid)"
    )
    lines = _wrap_ascii(
        ascii_text, 32, first_indent=0, cont_indent=0, roman_mask=mask
    )
    assert len(lines) >= 2
    cont = next(ln.lstrip() for ln in lines[1:] if ln.strip())
    assert cont.startswith("0"), cont
    rev = " ".join(
        reverse_translate_line(ln) for ln in lines if ln.strip()
    ).replace(" ", "")
    assert "Freight" in rev or "freight" in rev.lower()
    assert "사캐마둔털" not in rev


def test_wrap_does_not_mark_hangul_after_exw_acronym():
    """EXW 같은 대문자 약어 뒤 한글(또는)에 로마자표를 붙이지 않는다."""
    from korean_exam_braille.app.braille.translator import (
        hangul_text_to_ascii_with_roman_mask,
    )
    from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line
    from korean_exam_braille.app.layout.engine import _wrap_ascii

    ascii_text, mask = hangul_text_to_ascii_with_roman_mask(
        "용된다. 어떤 물품을 EXW 또는 FOB 조건으로"
    )
    assert "0,e,x,w4" in ascii_text
    assert "0,f,o,b4" in ascii_text
    lines = _wrap_ascii(
        ascii_text, 28, first_indent=0, cont_indent=0, roman_mask=mask
    )
    cont = next(
        ln for ln in lines if "iucz" in ln or "또는" in reverse_translate_line(ln)
    )
    assert not cont.lstrip().startswith("0,iucz"), cont
    assert "또는" in reverse_translate_line(cont)
    assert "Iucz" not in reverse_translate_line(cont)


def test_wrap_reopens_roman_between_acronyms():
    """약어만 이어져도 줄바꿈 뒤에는 로마자표를 다시 넣는다."""
    from korean_exam_braille.app.braille.translator import (
        hangul_text_to_ascii_with_roman_mask,
    )
    from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line
    from korean_exam_braille.app.layout.engine import _wrap_ascii

    ascii_text, mask = hangul_text_to_ascii_with_roman_mask("EXW FOB CIF DDP")
    lines = _wrap_ascii(
        ascii_text, 8, first_indent=0, cont_indent=0, roman_mask=mask
    )
    assert len(lines) >= 2
    for ln in lines:
        s = ln.lstrip()
        if not s:
            continue
        # 각 약어 줄은 로마자표로 시작
        assert s.startswith("0"), (ln, reverse_translate_line(ln))
    rev = " ".join(reverse_translate_line(ln) for ln in lines if ln.strip())
    assert "EXW" in rev and "FOB" in rev and "CIF" in rev and "DDP" in rev


def test_wrap_keeps_arrow_pronunciation_cells_together():
    """→의 /화살표/ 점열은 줄 경계에서 둘로 갈라지지 않는다."""
    from korean_exam_braille.app.braille.translator import hangul_text_to_ascii
    from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line
    from korean_exam_braille.app.common.arrow_markup import ARROW_RIGHT_BRAILLE_ASCII
    from korean_exam_braille.app.layout.engine import _wrap_ascii

    ink = "㉠묘터→㉡백파강→㉢언덕"
    ascii_text = hangul_text_to_ascii(ink)
    lines = _wrap_ascii(ascii_text, 32, first_indent=2, cont_indent=0)

    assert sum(line.count(ARROW_RIGHT_BRAILLE_ASCII) for line in lines) == 2
    assert all(
        not (
            ARROW_RIGHT_BRAILLE_ASCII[:5] in line
            and ARROW_RIGHT_BRAILLE_ASCII not in line
        )
        for line in lines
    )
    reversed_text = "".join(
        reverse_translate_line(line.strip()) for line in lines if line.strip()
    )
    assert reversed_text == "‘ㄱ’묘터→‘ㄴ’백파강→‘ㄷ’언덕"


def test_wrap_flattens_soft_newlines_within_paragraph():
    """문단 안 개행은 하드 줄바꿈이 아니라 공백으로 접고, 들여쓰기는 첫 줄만."""
    from korean_exam_braille.app.layout.engine import _wrap_ascii

    # 각 PDF 시각 줄은 짧아서, 예전 splitlines면 3줄·각 줄 first_indent
    text = "one\ntwo\nthree"
    lines = _wrap_ascii(text, 32, first_indent=2, cont_indent=0)
    assert len(lines) == 1
    assert lines[0] == "  one two three"

    # 폭이 좁으면 셀 단위로만 이어 나누고, 이어지는 줄은 cont_indent(0)
    wrapped = _wrap_ascii(text, 10, first_indent=2, cont_indent=0)
    assert wrapped[0].startswith("  ")
    assert all(not ln.startswith("  ") for ln in wrapped[1:])
    assert " ".join(ln.strip() for ln in wrapped) == "one two three"


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

