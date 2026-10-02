from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)


class QACriterionDecisionAI(
    BaseModel
):
    criterion_id: int = Field(
        ge=1,
    )

    status: Literal[
        "passed",
        "failed",
        "needs_review",
    ]

    score: int = Field(
        ge=0,
        le=100,
    )

    reason: str = Field(
        min_length=1,
        max_length=3000,
    )

    evidence_ids: list[int] = Field(
        default_factory=list,
        max_length=50,
    )

    evidence_summary: str = Field(
        default="",
        max_length=3000,
    )


class QAReviewDecisionAI(
    BaseModel
):
    criteria: list[
        QACriterionDecisionAI
    ] = Field(
        min_length=1,
        max_length=100,
    )

    summary: str = Field(
        min_length=1,
        max_length=5000,
    )
