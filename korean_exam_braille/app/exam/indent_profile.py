"""Passage 행 들여쓰기(R)/내어쓰기(L) 런길이 요약·장르 라벨."""

from __future__ import annotations

from dataclasses import dataclass

from korean_exam_braille.app.exam.models import ExamNode
from korean_exam_braille.app.exam.passage_indent_config import (
    DEFAULT_PASSAGE_INDENT_GENRE_CONFIG,
    PassageIndentGenreConfig,
)
from korean_exam_braille.app.pdf.models import PdfDocumentStructure


@dataclass(frozen=True)
class PassageIndentAnalysis:
    """PassageGroup 들여쓰기 분석 결과 (Mode B 디버그용)."""

    profile: str
    genre: str
    sum_r: int
    sum_l: int
    non_r1_runs: int
    line_count: int

    def mode_b_label_suffix(self) -> str:
        """트리 라벨용: 장르 · R합/L합 · nonR1=n · 프로필."""
        parts = [
            self.genre,
            f"R{self.sum_r}/L{self.sum_l}",
            f"nonR1={self.non_r1_runs}",
        ]
        if self.profile:
            parts.append(self.profile)
        return " · ".join(parts)


def classify_indent_levels(
    x0s: list[float],
    *,
    config: PassageIndentGenreConfig = DEFAULT_PASSAGE_INDENT_GENRE_CONFIG,
) -> list[str]:
    """그룹 최좌측(마진) 대비: 더 오른쪽이면 R(들여쓰기), 아니면 L(공백없는 본문)."""
    if not x0s:
        return []
    base = min(x0s)
    eps = config.x0_epsilon
    return ["R" if x0 > base + eps else "L" for x0 in x0s]


def indent_runs(levels: list[str]) -> list[tuple[str, int]]:
    """예: ['L','L','R'] → [('L', 2), ('R', 1)]"""
    if not levels:
        return []
    runs: list[tuple[str, int]] = []
    cur = levels[0]
    count = 1
    for ch in levels[1:]:
        if ch == cur:
            count += 1
        else:
            runs.append((cur, count))
            cur = ch
            count = 1
    runs.append((cur, count))
    return runs


def run_length_indent_string(levels: list[str]) -> str:
    """동일 문자가 이어지면 Ln / Rn 으로 묶는다. 예: L,L,L,R,L → L3R1L1"""
    return "".join(f"{ch}{n}" for ch, n in indent_runs(levels))


def indent_profile_string(
    x0s: list[float],
    *,
    config: PassageIndentGenreConfig = DEFAULT_PASSAGE_INDENT_GENRE_CONFIG,
) -> str:
    return run_length_indent_string(classify_indent_levels(x0s, config=config))


def filter_indent_runs(
    runs: list[tuple[str, int]],
    *,
    config: PassageIndentGenreConfig = DEFAULT_PASSAGE_INDENT_GENRE_CONFIG,
) -> list[tuple[str, int]]:
    """R 런 길이가 ignore_r_run_at_least 이상이면 제외하고, 인접 동일 문자를 다시 합친다."""
    threshold = config.ignore_r_run_at_least
    kept = [(ch, n) for ch, n in runs if not (ch == "R" and n >= threshold)]
    if not kept:
        return []
    merged: list[tuple[str, int]] = [kept[0]]
    for ch, n in kept[1:]:
        prev_ch, prev_n = merged[-1]
        if ch == prev_ch:
            merged[-1] = (ch, prev_n + n)
        else:
            merged.append((ch, n))
    return merged


def analyze_passage_indent(
    x0s: list[float],
    *,
    config: PassageIndentGenreConfig = DEFAULT_PASSAGE_INDENT_GENRE_CONFIG,
) -> PassageIndentAnalysis:
    """L/R 합·R 런 패턴으로 장르·디버그 수치를 함께 반환."""
    levels = classify_indent_levels(x0s, config=config)
    if not levels:
        return PassageIndentAnalysis(
            profile="",
            genre=config.label_nonfiction,
            sum_r=0,
            sum_l=0,
            non_r1_runs=0,
            line_count=0,
        )
    runs = filter_indent_runs(indent_runs(levels), config=config)
    sum_r = sum(n for ch, n in runs if ch == "R")
    sum_l = sum(n for ch, n in runs if ch == "L")
    non_r1 = sum(1 for ch, n in runs if ch == "R" and n != 1)
    # 순서 고정: 시 → 대화문 → 소설 → 비문학
    if sum_l < config.poetry_max_l_sum:
        genre = config.label_si
    elif sum_r > sum_l and sum_r < sum_l * config.dialogue_r_lt_l_factor:
        genre = config.label_dialogue
    elif non_r1 >= config.novel_min_non_r1_runs:
        genre = config.label_novel
    else:
        genre = config.label_nonfiction
    return PassageIndentAnalysis(
        profile="".join(f"{ch}{n}" for ch, n in runs),
        genre=genre,
        sum_r=sum_r,
        sum_l=sum_l,
        non_r1_runs=non_r1,
        line_count=sum(n for _, n in runs),
    )


def classify_passage_genre(
    x0s: list[float],
    *,
    config: PassageIndentGenreConfig = DEFAULT_PASSAGE_INDENT_GENRE_CONFIG,
) -> str:
    return analyze_passage_indent(x0s, config=config).genre


def build_line_x0_index(pdf: PdfDocumentStructure) -> dict[str, float]:
    """line_id → bbox x0."""
    out: dict[str, float] = {}
    for page in pdf.pages:
        for line in page.lines:
            out[line.id] = line.bbox[0]
    return out


def build_block_line_ids_index(pdf: PdfDocumentStructure) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for page in pdf.pages:
        for block in page.blocks:
            out[block.id] = list(block.line_ids)
    return out


def _passage_group_x0s(
    group: ExamNode,
    *,
    line_x0: dict[str, float],
    block_line_ids: dict[str, list[str]],
) -> list[float]:
    x0s: list[float] = []
    for child in group.children:
        if child.node_type != "Passage":
            continue
        for bid in child.source_range.block_ids:
            for lid in block_line_ids.get(bid, []):
                x0 = line_x0.get(lid)
                if x0 is None:
                    continue
                x0s.append(x0)
    return x0s


def analyze_passage_group_indent(
    group: ExamNode,
    *,
    line_x0: dict[str, float],
    block_line_ids: dict[str, list[str]],
    config: PassageIndentGenreConfig = DEFAULT_PASSAGE_INDENT_GENRE_CONFIG,
) -> PassageIndentAnalysis | None:
    if group.node_type != "PassageGroup":
        return None
    return analyze_passage_indent(
        _passage_group_x0s(group, line_x0=line_x0, block_line_ids=block_line_ids),
        config=config,
    )


def passage_group_indent_string(
    group: ExamNode,
    *,
    line_x0: dict[str, float],
    block_line_ids: dict[str, list[str]],
    config: PassageIndentGenreConfig = DEFAULT_PASSAGE_INDENT_GENRE_CONFIG,
) -> str:
    analysis = analyze_passage_group_indent(
        group, line_x0=line_x0, block_line_ids=block_line_ids, config=config
    )
    return analysis.profile if analysis else ""


def passage_group_genre_label(
    group: ExamNode,
    *,
    line_x0: dict[str, float],
    block_line_ids: dict[str, list[str]],
    config: PassageIndentGenreConfig = DEFAULT_PASSAGE_INDENT_GENRE_CONFIG,
) -> str:
    analysis = analyze_passage_group_indent(
        group, line_x0=line_x0, block_line_ids=block_line_ids, config=config
    )
    return analysis.genre if analysis else ""
