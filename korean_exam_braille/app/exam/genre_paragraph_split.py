"""장르별 Passage 문단 나눔 (Exam 트리 후처리).

시: 장르 문단 나눔 없음 (자연 블록 유지). ``(가)``/``(나)`` 표지 줄은 예외.
비문학: 들여쓰기(R) 시작 줄에서 새 문단
대화문: 내어쓰기(직전보다 왼쪽) 또는 연속 L에서 새 문단
소설: 들여쓰기면 문단 시작 — 따옴표면 이어진 R까지, 아니면 이어진 L까지
지문 표지: 줄 전체가 ``(가)`` 또는 ``(나)``이면 단독 문단 + ``section_label``
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from korean_exam_braille.app.exam.indent_profile import (
    analyze_passage_indent,
    build_block_line_ids_index,
    build_line_x0_index,
    classify_indent_levels,
    column_relative_x0s,
    column_relative_x0s_from_lines,
)
from korean_exam_braille.app.exam.models import ExamDocument, ExamNode, SourceRange
from korean_exam_braille.app.exam.passage_indent_config import (
    DEFAULT_PASSAGE_INDENT_GENRE_CONFIG,
    PassageIndentGenreConfig,
)
from korean_exam_braille.app.pdf.models import PdfDocumentStructure, PdfLine

# 쌍따옴표만 (ASCII / 굽은 따옴표)
DOUBLE_QUOTE_START = re.compile(r'^["\u201c\u201d]')
# 지문 구간 표지 — 줄 전체가 (가) 또는 (나)일 때만 (발문「(가)와 관련하여」제외)
_SECTION_LABEL = re.compile(r"^\s*[\(（](가|나)[\)）]\s*$")


@dataclass
class _PassageLine:
    line: PdfLine
    block_id: str


def line_starts_with_double_quote(text: str | None) -> bool:
    """첫 글자(선행 공백 제거 후)가 쌍따옴표인지."""
    t = (text or "").lstrip()
    return bool(t and DOUBLE_QUOTE_START.match(t))


def line_section_label(text: str | None) -> str | None:
    """줄 전체가 지문 표지 ``(가)``/``(나)``이면 그 표지, 아니면 None."""
    m = _SECTION_LABEL.match(text or "")
    if not m:
        return None
    return f"({m.group(1)})"


def _gana_split_starts(texts: list[str]) -> list[int]:
    """표지 줄은 단독 문단, 바로 다음 줄은 본문 문단 시작."""
    starts: list[int] = []
    n = len(texts)
    for i, t in enumerate(texts):
        if line_section_label(t) is None:
            continue
        starts.append(i)
        if i + 1 < n:
            starts.append(i + 1)
    return starts


def _index_lines(pdf: PdfDocumentStructure) -> dict[str, PdfLine]:
    return {ln.id: ln for page in pdf.pages for ln in page.lines}


def _collect_passage_lines(
    passages: list[ExamNode],
    *,
    lines_by_id: dict[str, PdfLine],
    block_line_ids: dict[str, list[str]],
) -> list[_PassageLine]:
    out: list[_PassageLine] = []
    for node in passages:
        for bid in node.source_range.block_ids:
            for lid in block_line_ids.get(bid, []):
                ln = lines_by_id.get(lid)
                if ln is None:
                    continue
                out.append(_PassageLine(line=ln, block_id=bid))
    return out


def _split_starts_nonfiction(
    x0s: list[float],
    *,
    config: PassageIndentGenreConfig,
) -> list[int]:
    """들여쓰기(R) 줄에서 새 문단 시작."""
    if not x0s:
        return []
    levels = classify_indent_levels(x0s, config=config)
    starts = [0]
    for i, lv in enumerate(levels):
        if i > 0 and lv == "R":
            starts.append(i)
    return starts


def _split_starts_dialogue(
    x0s: list[float],
    *,
    config: PassageIndentGenreConfig,
) -> list[int]:
    """대화문 문단 시작.

    - 직전 행보다 epsilon 이상 왼쪽(내어쓰기)이면 새 문단
    - **같은 마진 L이 연속**이면(한 줄 대사 연속) 새 문단
      — 이전 규칙만으로는 L100→L100이 합쳐짐
    """
    if not x0s:
        return []
    eps = config.x0_epsilon
    levels = classify_indent_levels(x0s, config=config)
    starts = [0]
    for i in range(1, len(x0s)):
        if x0s[i] + eps < x0s[i - 1]:
            starts.append(i)
            continue
        if levels[i] == "L" and levels[i - 1] == "L":
            starts.append(i)
    return starts


def _segments_novel(
    x0s: list[float],
    texts: list[str],
    *,
    config: PassageIndentGenreConfig,
) -> list[tuple[int, int]]:
    """소설 문단 구간.

    - 들여쓰기(R)면 문단 시작
    - 시작이 따옴표: 이어지는 R을 같은 문단에 포함, L이 나오면 중단
    - 시작이 비따옴표: 이어지는 L을 같은 문단에 포함, R이 나오면 중단
    - 선행 L만 있는 구간: 다음 R 전까지 한 문단
    """
    if not x0s:
        return []
    levels = classify_indent_levels(x0s, config=config)
    n = len(levels)
    segs: list[tuple[int, int]] = []
    i = 0
    while i < n:
        start = i
        if levels[i] == "R" and line_starts_with_double_quote(texts[i]):
            i += 1
            while i < n and levels[i] == "R":
                i += 1
        elif levels[i] == "R":
            i += 1
            while i < n and levels[i] == "L":
                i += 1
        else:
            i += 1
            while i < n and levels[i] == "L":
                i += 1
        segs.append((start, i))
    return segs


def _segments_from_starts(n: int, starts: list[int]) -> list[tuple[int, int]]:
    if n <= 0:
        return []
    uniq = sorted({s for s in starts if 0 <= s < n})
    if not uniq or uniq[0] != 0:
        uniq = [0] + [s for s in uniq if s > 0]
    segs: list[tuple[int, int]] = []
    for i, s in enumerate(uniq):
        e = uniq[i + 1] if i + 1 < len(uniq) else n
        if e > s:
            segs.append((s, e))
    return segs


def _bracket_endpoint_index(
    pdf: PdfDocumentStructure,
) -> tuple[dict[str, str], dict[str, str]]:
    """bracket_group 첫/끝 line_id → label."""
    starts: dict[str, str] = {}
    ends: dict[str, str] = {}
    for page in pdf.pages:
        for group in page.bracket_groups or []:
            if not group.line_ids:
                continue
            starts[group.line_ids[0]] = group.label
            ends[group.line_ids[-1]] = group.label
    return starts, ends


def _passage_node_from_lines(
    rows: list[_PassageLine],
    *,
    node_id: str,
    bracket_starts: dict[str, str] | None = None,
    bracket_ends: dict[str, str] | None = None,
    indent_genre: str | None = None,
) -> ExamNode:
    text = "\n".join(r.line.text for r in rows if r.line.text is not None)
    block_ids = list(dict.fromkeys(r.block_id for r in rows))
    page = rows[0].line.page_number if rows else None
    labels: list[str] = []
    starts: list[str] = []
    ends: list[str] = []
    for r in rows:
        lab = r.line.bracket_label
        if lab and lab not in labels:
            labels.append(lab)
        if bracket_starts:
            s = bracket_starts.get(r.line.id)
            if s and s not in starts:
                starts.append(s)
        if bracket_ends:
            e = bracket_ends.get(r.line.id)
            if e and e not in ends:
                ends.append(e)
    meta: dict[str, object] = {
        "paragraph_split": True,
        "line_ids": [r.line.id for r in rows],
    }
    if indent_genre:
        meta["indent_genre"] = indent_genre
    tags: list[str] = []
    if labels:
        meta["bracket_labels"] = labels
        tags.append(f"bracket:{','.join(labels)}")
    if starts:
        meta["bracket_start_labels"] = starts
        tags.append(f"bracket-start:{','.join(starts)}")
    if ends:
        meta["bracket_end_labels"] = ends
        tags.append(f"bracket-end:{','.join(ends)}")
    if tags:
        meta["candidate_tags"] = tags
    if rows:
        section = line_section_label(rows[0].line.text)
        if section:
            meta["section_label"] = section
    return ExamNode(
        id=node_id,
        node_type="Passage",
        source_range=SourceRange(
            page_number=page,
            block_ids=block_ids,
            raw_text=text,
        ),
        confidence=0.85,
        metadata=meta,
    )

def count_indented_double_quote_lines(
    x0s: list[float],
    texts: list[str],
    *,
    config: PassageIndentGenreConfig = DEFAULT_PASSAGE_INDENT_GENRE_CONFIG,
) -> int:
    """R(들여쓰기) 줄 중 쌍따옴표로 시작하는 개수."""
    if not x0s:
        return 0
    levels = classify_indent_levels(x0s, config=config)
    n = 0
    for lv, t in zip(levels, texts):
        if lv == "R" and line_starts_with_double_quote(t):
            n += 1
    return n


def _layout_column_cut(pdf: PdfDocumentStructure) -> float | None:
    raw = (pdf.metadata or {}).get("layout_profile")
    if isinstance(raw, dict):
        cut = raw.get("column_cut_x")
        return float(cut) if cut is not None else None
    cut = getattr(raw, "column_cut_x", None)
    return float(cut) if cut is not None else None


def resplit_passage_run(
    passages: list[ExamNode],
    *,
    genre: str,
    lines_by_id: dict[str, PdfLine],
    block_line_ids: dict[str, list[str]],
    config: PassageIndentGenreConfig,
    id_prefix: str,
    column_cut_x: float | None = None,
    bracket_starts: dict[str, str] | None = None,
    bracket_ends: dict[str, str] | None = None,
) -> list[ExamNode]:
    """연속 Passage 노드들을 장르 규칙으로 재분할.

    시(indent)는 장르 문단 나눔 없음. 다만 단독 ``(가)``/``(나)`` 줄은
    모든 장르에서 표지 문단 + 본문 문단으로 가른다.
    """
    if not passages:
        return []

    rows = _collect_passage_lines(
        passages, lines_by_id=lines_by_id, block_line_ids=block_line_ids
    )
    if not rows:
        for p in passages:
            if p.node_type == "Passage":
                p.metadata["indent_genre"] = genre
        return list(passages)

    texts = [r.line.text or "" for r in rows]
    gana_starts = _gana_split_starts(texts)

    genre_starts: list[int] = [0]
    if len(rows) >= 2 and genre != config.label_si:
        x0s = column_relative_x0s_from_lines(
            [r.line for r in rows],
            column_cut_x=column_cut_x,
        )
        if genre == config.label_nonfiction:
            genre_starts = _split_starts_nonfiction(x0s, config=config)
        elif genre == config.label_dialogue:
            genre_starts = _split_starts_dialogue(x0s, config=config)
        elif genre == config.label_novel:
            segs = _segments_novel(x0s, texts, config=config)
            genre_starts = [a for a, _ in segs] or [0]
        else:
            genre_starts = [0]

    segs = _segments_from_starts(len(rows), genre_starts + gana_starts)
    if len(segs) <= 1:
        for p in passages:
            if p.node_type == "Passage":
                p.metadata["indent_genre"] = genre
                if not p.metadata.get("section_label"):
                    first = (p.source_range.raw_text or "").split("\n", 1)[0]
                    lab = line_section_label(first)
                    if lab:
                        p.metadata["section_label"] = lab
        return list(passages)

    out: list[ExamNode] = []
    for idx, (a, b) in enumerate(segs):
        out.append(
            _passage_node_from_lines(
                rows[a:b],
                node_id=f"{id_prefix}-p{idx}",
                bracket_starts=bracket_starts,
                bracket_ends=bracket_ends,
                indent_genre=genre,
            )
        )
    return out


def apply_genre_paragraph_splits(
    exam: ExamDocument,
    pdf: PdfDocumentStructure,
    *,
    config: PassageIndentGenreConfig = DEFAULT_PASSAGE_INDENT_GENRE_CONFIG,
) -> None:
    """PassageGroup마다 장르를 붙이고 Passage 문단을 장르별로 재분할 (in-place)."""
    line_x0 = build_line_x0_index(pdf)
    block_line_ids = build_block_line_ids_index(pdf)
    lines_by_id = _index_lines(pdf)
    column_cut_x = _layout_column_cut(pdf)
    bracket_starts, bracket_ends = _bracket_endpoint_index(pdf)

    def walk(node: ExamNode) -> None:
        if node.node_type == "PassageGroup":
            items = []
            seen: set[str] = set()
            for child in node.children:
                if child.node_type != "Passage":
                    continue
                meta_lines = child.metadata.get("line_ids")
                if isinstance(meta_lines, list) and meta_lines:
                    lids = [str(x) for x in meta_lines]
                else:
                    lids = [
                        lid
                        for bid in child.source_range.block_ids
                        for lid in block_line_ids.get(bid, [])
                    ]
                for lid in lids:
                    if lid in seen or lid not in line_x0:
                        continue
                    seen.add(lid)
                    items.append((lid, line_x0[lid]))
            analysis = analyze_passage_indent(
                column_relative_x0s(items, column_cut_x=column_cut_x),
                text="\n".join(
                    (c.source_range.raw_text or "")
                    for c in node.children
                    if c.node_type == "Passage"
                ),
                config=config,
            )
            node.metadata["indent_genre"] = analysis.genre
            node.metadata["indent_profile"] = analysis.profile
            node.metadata["indent_sum_r"] = analysis.sum_r
            node.metadata["indent_sum_l"] = analysis.sum_l
            node.metadata["indent_colon_count"] = analysis.colon_count

            new_children: list[ExamNode] = []
            i = 0
            children = node.children
            while i < len(children):
                if children[i].node_type != "Passage":
                    new_children.append(children[i])
                    i += 1
                    continue
                j = i
                while j < len(children) and children[j].node_type == "Passage":
                    j += 1
                run = children[i:j]
                new_children.extend(
                    resplit_passage_run(
                        run,
                        genre=analysis.genre,
                        lines_by_id=lines_by_id,
                        block_line_ids=block_line_ids,
                        config=config,
                        id_prefix=f"{node.id}-seg{i}",
                        column_cut_x=column_cut_x,
                        bracket_starts=bracket_starts,
                        bracket_ends=bracket_ends,
                    )
                )
                i = j
            node.children = new_children
            # 재분할·시 원본 모두 Passage에 장르를 남겨 점역이 개행 정책을 고르게 한다.
            for child in node.children:
                if child.node_type == "Passage":
                    child.metadata.setdefault("indent_genre", analysis.genre)
        for child in node.children:
            walk(child)

    walk(exam.root)
