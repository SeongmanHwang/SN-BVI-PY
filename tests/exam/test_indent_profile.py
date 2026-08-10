"""들여쓰기/내어쓰기 L·R 런길이 요약·장르."""

from korean_exam_braille.app.exam.indent_profile import (
    analyze_passage_indent,
    classify_indent_levels,
    classify_passage_genre,
    indent_profile_string,
    run_length_indent_string,
)
from korean_exam_braille.app.exam.passage_indent_config import PassageIndentGenreConfig


def test_run_length_five_body_lines():
    assert indent_profile_string([100.0] * 5) == "L5"


def test_first_line_indent_then_body():
    x0s = [110.0] + [100.0] * 5
    assert classify_indent_levels(x0s) == ["R", "L", "L", "L", "L", "L"]
    assert indent_profile_string(x0s) == "R1L5"


def test_run_length_encode():
    assert run_length_indent_string(["L", "L", "L", "R", "L"]) == "L3R1L1"
    assert run_length_indent_string([]) == ""


def test_genre_switch_order():
    # 1) 시: L < 10
    assert classify_passage_genre([110.0] * 20 + [100.0] * 3) == "시"
    assert classify_passage_genre([100.0] * 9) == "시"
    # 2) 대화문: L≥10, R>L, R < L*1.5
    assert classify_passage_genre([110.0] * 12 + [100.0] * 10) == "대화문"
    # 3) 소설: L≥10, 대화문 아님, nonR1≥3
    novel = (
        [100.0] * 10
        + [110.0] * 2
        + [100.0]
        + [110.0] * 3
        + [100.0]
        + [110.0] * 2
        + [100.0] * 5
    )
    assert classify_passage_genre(novel) == "소설"
    # 4) 비문학
    assert classify_passage_genre([110.0] + [100.0] * 15) == "비문학"


def test_ignore_large_r_runs():
    x0s = [100.0] * 2 + [110.0] * 50
    analysis = analyze_passage_indent(x0s)
    assert analysis.profile == "L2"
    assert analysis.sum_r == 0 and analysis.sum_l == 2
    assert analysis.genre == "시"  # L=2 < 10
    x0s44 = [100.0] * 2 + [110.0] * 44
    a44 = analyze_passage_indent(x0s44)
    assert a44.sum_r == 44
    assert "R44" in a44.profile


def test_config_override_poetry_l():
    cfg = PassageIndentGenreConfig(poetry_max_l_sum=5)
    x0s = [100.0] * 8  # L=8: 기본 시, 임계 5면 비문학(대화문·소설 조건 미충족)
    assert classify_passage_genre(x0s) == "시"
    assert classify_passage_genre(x0s, config=cfg) == "비문학"


def test_mode_b_label_suffix():
    analysis = analyze_passage_indent([110.0] + [100.0] * 15)
    assert analysis.genre == "비문학"
    assert analysis.sum_r == 1 and analysis.sum_l == 15
    assert analysis.mode_b_label_suffix().startswith("비문학 · R1/L15 · nonR1=0")
