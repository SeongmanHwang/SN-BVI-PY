"""Passage 들여쓰기 장르 판정 설정 — 디버그 시 여기만 조정."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PassageIndentGenreConfig:
    """L/R 런길이·쌍점 개수 기반 시·대화문·소설·비문학 판정 임계값.

    판정 순서(스위치): 대화문 → 시 → 소설 → 비문학.
    """

    # 그룹 최좌측(마진)보다 이만큼 오른쪽이면 R(들여쓰기)
    x0_epsilon: float = 8.0

    # 1) 대화문: 본문 쌍점(:)·전각 쌍점(：) 합이 이 값 이상
    dialogue_min_colons: int = 5

    # 2) 시: L합 < 이 값
    poetry_max_l_sum: int = 10

    # 이 길이 이상인 R 런(R45 …)은 합계·장르·프로필에서 무시
    ignore_r_run_at_least: int = 45

    # 3) 소설: R1이 아닌 R 런 개수가 이 값 이상
    novel_min_non_r1_runs: int = 3

    # 4) 그외 비문학

    label_si: str = "시"
    label_dialogue: str = "대화문"
    label_novel: str = "소설"
    label_nonfiction: str = "비문학"


DEFAULT_PASSAGE_INDENT_GENRE_CONFIG = PassageIndentGenreConfig()
