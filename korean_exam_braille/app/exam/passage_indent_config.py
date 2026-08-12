"""Passage 들여쓰기 장르 판정 설정 — 디버그 시 여기만 조정."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PassageIndentGenreConfig:
    """L/R 런길이·쌍점 개수 기반 시·대화문·소설·비문학 판정 임계값.

    판정 순서(스위치): 대화문 → (발문 초고) 비문학 → 시 → 소설 → 비문학.
    """

    # 그룹 최좌측(마진)보다 이만큼 오른쪽이면 R(들여쓰기)
    x0_epsilon: float = 8.0

    # 1) 대화문: 본문 쌍점(:)·전각 쌍점(：) 합이 이 값 이상
    #    각주 표지(* / ※)와 함께 있는 쌍점은 세지 않음
    dialogue_min_colons: int = 5

    # 2) 대화문이 아니면: 제시문 첫 발문(PassageGroup 안내)에 이 단어가
    #    있으면 시·소설을 건너뛰고 비문학 (작문 초고)
    nonfiction_prompt_token: str = "초고"

    # 3) 시: L합 < 이 값
    poetry_max_l_sum: int = 15

    # 이 길이 이상인 R 런(R45 …)은 합계·장르·프로필에서 무시
    ignore_r_run_at_least: int = 45

    # 4) 소설: R1이 아닌 R 런 개수가 이 값 이상
    novel_min_non_r1_runs: int = 3

    # 표제 줄: 숫자/로마/대괄호로 시작하는 짧은 줄을 단독 문단
    heading_max_chars: int = 28
    # 이 시험지 표제는 볼드 플래그가 없는 경우가 많음. True면 is_bold 필수.
    heading_require_bold: bool = False

    # 5) 그외 비문학

    label_si: str = "시"
    label_dialogue: str = "대화문"
    label_novel: str = "소설"
    label_nonfiction: str = "비문학"


DEFAULT_PASSAGE_INDENT_GENRE_CONFIG = PassageIndentGenreConfig()
