"""생성 BRF ↔ 참고 BRF 검토용 면·행·글자 불일치 마스크."""

from __future__ import annotations

from difflib import SequenceMatcher

from korean_exam_braille.app.brf.ascii_braille import ascii_to_unicode, normalize_brf_ascii
from korean_exam_braille.app.brf.compare import compare_brf_texts
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line


def brf_text_to_display_pages(brf_text: str) -> list[dict[str, object]]:
    """BRF 텍스트 → 면별 유니코드 점자·역점역 (줄 목록 포함)."""
    pages: list[dict[str, object]] = []
    for index, page in enumerate(brf_text.split("\x0c"), start=1):
        raw_lines = page.splitlines()
        if not any(line.strip() for line in raw_lines):
            continue
        ascii_lines: list[str] = []
        uni_lines: list[str] = []
        rev_lines: list[str] = []
        for line in raw_lines:
            if line.strip() == "":
                ascii_lines.append("")
                uni_lines.append("")
                rev_lines.append("")
            else:
                ascii_lines.append(normalize_brf_ascii(line))
                uni_lines.append(ascii_to_unicode(line))
                rev_lines.append(reverse_translate_line(line))
        pages.append(
            {
                "index": index,
                "ascii_lines": ascii_lines,
                "unicode_lines": uni_lines,
                "reverse_lines": rev_lines,
                "unicode": "\n".join(uni_lines),
                "reverse": "\n".join(rev_lines),
            }
        )
    return pages


def char_mismatch_masks(a: str, b: str) -> tuple[list[bool], list[bool]]:
    """SequenceMatcher 기준 — True면 해당 글자가 불일치 구간."""
    a_mask = [False] * len(a)
    b_mask = [False] * len(b)
    matcher = SequenceMatcher(a=a, b=b, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        for i in range(i1, i2):
            a_mask[i] = True
        for j in range(j1, j2):
            b_mask[j] = True
    return a_mask, b_mask


def _annotated_lines(
    gen_lines: list[str],
    ref_lines: list[str],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[bool]]:
    n = max(len(gen_lines), len(ref_lines))
    gen_out: list[dict[str, object]] = []
    ref_out: list[dict[str, object]] = []
    line_equal: list[bool] = []
    for i in range(n):
        g = gen_lines[i] if i < len(gen_lines) else ""
        r = ref_lines[i] if i < len(ref_lines) else ""
        g_mask, r_mask = char_mismatch_masks(g, r)
        equal = g == r
        line_equal.append(equal)
        gen_out.append({"text": g, "mismatch": g_mask, "line_equal": equal})
        ref_out.append({"text": r, "mismatch": r_mask, "line_equal": equal})
    return gen_out, ref_out, line_equal


def build_review_pages(
    generated_brf: str,
    reference_brf: str,
) -> dict[str, object]:
    """면·행 정렬 비교 + 점자/역점역 글자 불일치 마스크."""
    gen_pages = brf_text_to_display_pages(generated_brf)
    ref_pages = brf_text_to_display_pages(reference_brf)
    cmp = compare_brf_texts(generated_brf, reference_brf)
    n = max(len(gen_pages), len(ref_pages))
    review_pages: list[dict[str, object]] = []
    for i in range(n):
        g = gen_pages[i] if i < len(gen_pages) else None
        r = ref_pages[i] if i < len(ref_pages) else None
        g_uni = list(g["unicode_lines"]) if g else []
        r_uni = list(r["unicode_lines"]) if r else []
        g_rev = list(g["reverse_lines"]) if g else []
        r_rev = list(r["reverse_lines"]) if r else []
        gen_uni, ref_uni, uni_eq = _annotated_lines(g_uni, r_uni)
        gen_rev, ref_rev, rev_eq = _annotated_lines(g_rev, r_rev)
        review_pages.append(
            {
                "index": i + 1,
                "generated": {
                    "unicode_lines": gen_uni,
                    "reverse_lines": gen_rev,
                },
                "reference": {
                    "unicode_lines": ref_uni,
                    "reverse_lines": ref_rev,
                },
                "unicode_line_equal": uni_eq,
                "reverse_line_equal": rev_eq,
            }
        )
    return {
        "review_pages": review_pages,
        "compare": {
            "generated_pages": cmp.generated_pages,
            "reference_pages": cmp.reference_pages,
            "generated_lines": cmp.generated_lines,
            "reference_lines": cmp.reference_lines,
            "matched_lines": cmp.matched_lines,
            "line_match_ratio": cmp.line_match_ratio,
            "cell_equal": cmp.cell_equal,
            "cell_total": cmp.cell_total,
            "cell_match_ratio": cmp.cell_match_ratio,
            "diff_count": len(cmp.diffs),
        },
    }
