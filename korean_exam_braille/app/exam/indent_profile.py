"""Passage 행 들여쓰기(R)/내어쓰기(L) 런길이 요약·장르 라벨."""

from __future__ import annotations

import re
from dataclasses import dataclass

from korean_exam_braille.app.exam.models import ExamNode
from korean_exam_braille.app.exam.passage_indent_config import (
    DEFAULT_PASSAGE_INDENT_GENRE_CONFIG,
    PassageIndentGenreConfig,
)
from korean_exam_braille.app.pdf.models import PdfDocumentStructure, PdfLine

_LINE_COLUMN_RE = re.compile(r"-c(\d+)-")


@dataclass(frozen=True)
class PassageIndentAnalysis:
    """PassageGroup 들여쓰기 분석 결과 (Mode B 디버그용)."""

    profile: str
    genre: str
    sum_r: int
    sum_l: int
    non_r1_runs: int
    line_count: int
    colon_count: int = 0

    def mode_b_label_suffix(self) -> str:
        """트리 라벨용: 장르 · R합/L합 · nonR1=n · 쌍점 · 프로필."""
        parts = [
            self.genre,
            f"R{self.sum_r}/L{self.sum_l}",
            f"nonR1={self.non_r1_runs}",
            f"colon={self.colon_count}",
        ]
        if self.profile:
            parts.append(self.profile)
        return " · ".join(parts)


def count_colons(text: str) -> int:
    """반각·전각 쌍점(:)·(：) 개수."""
    if not text:
        return 0
    return text.count(":") + text.count("：")


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


def column_key_for_line(
    line_id: str,
    x0: float,
    *,
    column_cut_x: float | None = None,
) -> int:
    """행의 단 키. line_id의 -cN- 우선, 없으면 cut 기준(0=좌, 1=우)."""
    m = _LINE_COLUMN_RE.search(line_id or "")
    if m:
        return int(m.group(1))
    if column_cut_x is not None:
        return 0 if x0 < column_cut_x else 1
    return 0


def column_relative_x0s(
    items: list[tuple[str, float]],
    *,
    column_cut_x: float | None = None,
) -> list[float]:
    """단별 min(x0)을 빼 상대 좌표로 만든다 (좌·우 혼입 PassageGroup용).

    같은 단에만 속하는 입력이면 전역 min 기준과 동일한 L/R가 나온다.
    """
    if not items:
        return []
    keys = [
        column_key_for_line(lid, x0, column_cut_x=column_cut_x) for lid, x0 in items
    ]
    bases: dict[int, float] = {}
    for key, (_lid, x0) in zip(keys, items):
        prev = bases.get(key)
        if prev is None or x0 < prev:
            bases[key] = x0
    return [x0 - bases[key] for key, (_lid, x0) in zip(keys, items)]


def column_relative_x0s_from_lines(
    lines: list[PdfLine],
    *,
    column_cut_x: float | None = None,
) -> list[float]:
    """PdfLine 목록 → 단별 상대 x0."""
    return column_relative_x0s(
        [(ln.id, ln.bbox[0]) for ln in lines],
        column_cut_x=column_cut_x,
    )


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
    text: str | None = None,
    config: PassageIndentGenreConfig = DEFAULT_PASSAGE_INDENT_GENRE_CONFIG,
) -> PassageIndentAnalysis:
    """쌍점 개수·L/R 런으로 장르·디버그 수치를 함께 반환."""
    colon_n = count_colons(text or "")
    levels = classify_indent_levels(x0s, config=config)
    if not levels:
        genre = (
            config.label_dialogue
            if colon_n >= config.dialogue_min_colons
            else config.label_nonfiction
        )
        return PassageIndentAnalysis(
            profile="",
            genre=genre,
            sum_r=0,
            sum_l=0,
            non_r1_runs=0,
            line_count=0,
            colon_count=colon_n,
        )
    runs = filter_indent_runs(indent_runs(levels), config=config)
    sum_r = sum(n for ch, n in runs if ch == "R")
    sum_l = sum(n for ch, n in runs if ch == "L")
    non_r1 = sum(1 for ch, n in runs if ch == "R" and n != 1)
    # 순서 고정: 대화문 → 시 → 소설 → 비문학
    if colon_n >= config.dialogue_min_colons:
        genre = config.label_dialogue
    elif sum_l < config.poetry_max_l_sum:
        genre = config.label_si
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
        colon_count=colon_n,
    )


def classify_passage_genre(
    x0s: list[float],
    *,
    text: str | None = None,
    config: PassageIndentGenreConfig = DEFAULT_PASSAGE_INDENT_GENRE_CONFIG,
) -> str:
    return analyze_passage_indent(x0s, text=text, config=config).genre


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
    column_cut_x: float | None = None,
) -> list[float]:
    """Passage 행 x0을 단별 상대 좌표로 모은다.

    문단 분할 후에는 metadata.line_ids를 우선해, 공유 block_ids로
    같은 줄이 여러 번 잡히지 않게 한다.
    """
    items: list[tuple[str, float]] = []
    seen: set[str] = set()
    for child in group.children:
        if child.node_type != "Passage":
            continue
        meta_lines = child.metadata.get("line_ids")
        if isinstance(meta_lines, list) and meta_lines:
            lids = [str(x) for x in meta_lines]
        else:
            lids = []
            for bid in child.source_range.block_ids:
                lids.extend(block_line_ids.get(bid, []))
        for lid in lids:
            if lid in seen:
                continue
            x0 = line_x0.get(lid)
            if x0 is None:
                continue
            seen.add(lid)
            items.append((lid, x0))
    return column_relative_x0s(items, column_cut_x=column_cut_x)


def _passage_group_text(group: ExamNode) -> str:
    parts: list[str] = []
    for child in group.children:
        if child.node_type != "Passage":
            continue
        raw = child.source_range.raw_text
        if raw:
            parts.append(raw)
    return "\n".join(parts)


def analyze_passage_group_indent(
    group: ExamNode,
    *,
    line_x0: dict[str, float],
    block_line_ids: dict[str, list[str]],
    config: PassageIndentGenreConfig = DEFAULT_PASSAGE_INDENT_GENRE_CONFIG,
    column_cut_x: float | None = None,
) -> PassageIndentAnalysis | None:
    if group.node_type != "PassageGroup":
        return None
    return analyze_passage_indent(
        _passage_group_x0s(
            group,
            line_x0=line_x0,
            block_line_ids=block_line_ids,
            column_cut_x=column_cut_x,
        ),
        text=_passage_group_text(group),
        config=config,
    )


def passage_group_indent_string(
    group: ExamNode,
    *,
    line_x0: dict[str, float],
    block_line_ids: dict[str, list[str]],
    config: PassageIndentGenreConfig = DEFAULT_PASSAGE_INDENT_GENRE_CONFIG,
    column_cut_x: float | None = None,
) -> str:
    analysis = analyze_passage_group_indent(
        group,
        line_x0=line_x0,
        block_line_ids=block_line_ids,
        config=config,
        column_cut_x=column_cut_x,
    )
    return analysis.profile if analysis else ""


def passage_group_genre_label(
    group: ExamNode,
    *,
    line_x0: dict[str, float],
    block_line_ids: dict[str, list[str]],
    config: PassageIndentGenreConfig = DEFAULT_PASSAGE_INDENT_GENRE_CONFIG,
    column_cut_x: float | None = None,
) -> str:
    analysis = analyze_passage_group_indent(
        group,
        line_x0=line_x0,
        block_line_ids=block_line_ids,
        config=config,
        column_cut_x=column_cut_x,
    )
    return analysis.genre if analysis else ""
