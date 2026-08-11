"""들여쓰기/내어쓰기 L·R 런길이 요약·장르."""

from korean_exam_braille.app.exam.indent_profile import (
    analyze_passage_indent,
    classify_indent_levels,
    classify_passage_genre,
    column_relative_x0s,
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
    # 1) 대화문: 쌍점(:) 5개 이상 — 최우선 (시 L 조건보다 앞)
    assert (
        classify_passage_genre(
            [100.0] * 3,
            text="사회자: a: b: c: d:",
        )
        == "대화문"
    )
    assert (
        classify_passage_genre(
            [110.0] * 20 + [100.0] * 3,
            text="A：B：C：D：E：",
        )
        == "대화문"
    )
    # 2) 시: L < 10 (쌍점 부족)
    assert classify_passage_genre([110.0] * 20 + [100.0] * 3) == "시"
    assert classify_passage_genre([100.0] * 9) == "시"
    # 예전 R/L 대화문 패턴은 쌍점 없으면 비문학(또는 소설 조건)
    assert classify_passage_genre([110.0] * 12 + [100.0] * 10) == "비문학"
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


def test_dialogue_min_colons_override():
    cfg = PassageIndentGenreConfig(dialogue_min_colons=3)
    x0s = [100.0] * 12
    text = "a: b: c:"
    assert classify_passage_genre(x0s, text=text) == "비문학"
    assert classify_passage_genre(x0s, text=text, config=cfg) == "대화문"


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
    assert analysis.colon_count == 0
    assert analysis.mode_b_label_suffix().startswith(
        "비문학 · R1/L15 · nonR1=0 · colon=0"
    )


def test_column_relative_x0s_mixed_columns_not_all_r():
    """좌(~96) + 우(~437) 혼입 시 오른쪽 본문이 전부 R이 되면 안 된다."""
    items = [
        ("p1-c0-l0", 96.0),
        ("p1-c0-l1", 106.0),  # 좌 들여쓰기
        ("p1-c0-l2", 96.0),
        ("p1-c1-l0", 437.0),
        ("p1-c1-l1", 447.0),  # 우 들여쓰기
        ("p1-c1-l2", 437.0),
        ("p1-c1-l3", 437.0),
    ]
    rel = column_relative_x0s(items)
    levels = classify_indent_levels(rel)
    # 단별 정규화 후: L R L | L R L L
    assert levels == ["L", "R", "L", "L", "R", "L", "L"]
    right_levels = levels[3:]
    assert right_levels.count("R") == 1
    assert right_levels.count("L") == 3


def test_column_relative_x0s_right_only_matches_global():
    items = [
        ("p7-c1-l0", 447.0),
        ("p7-c1-l1", 437.0),
        ("p7-c1-l2", 437.0),
    ]
    abs_x0s = [x for _lid, x in items]
    rel = column_relative_x0s(items)
    assert classify_indent_levels(rel) == classify_indent_levels(abs_x0s)
