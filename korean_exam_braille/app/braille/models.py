"""점자 번역 중간 표현."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BrailleToken:
    """원문 토큰 → 점자 셀 배열."""

    source_text: str
    token_type: str
    cells: list[int]
    rule_id: str = ""
    breakable_before: bool = True
    breakable_after: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_text": self.source_text,
            "token_type": self.token_type,
            "cells": list(self.cells),
            "rule_id": self.rule_id,
            "breakable_before": self.breakable_before,
            "breakable_after": self.breakable_after,
            "metadata": dict(self.metadata),
        }


@dataclass
class BrailleSequence:
    """한 의미 노드(또는 블록)의 점자 토큰열."""

    source_node_id: str
    tokens: list[BrailleToken] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def cells(self) -> list[int]:
        out: list[int] = []
        for token in self.tokens:
            out.extend(token.cells)
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_node_id": self.source_node_id,
            "tokens": [t.to_dict() for t in self.tokens],
            "metadata": dict(self.metadata),
        }
