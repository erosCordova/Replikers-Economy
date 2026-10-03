from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)


class FinalReviewCorrectionAI(
    BaseModel
):
    task_id: int = Field(
        ge=1,
    )

    instruction: str = Field(
        min_length=1,
        max_length=3000,
    )

    severity: Literal[
        "low",
        "medium",
        "high",
    ] = "medium"


class FinalReviewDecisionAI(
    BaseModel
):
    decision: Literal[
        "approve",
        "request_corrections",
    ]

    score: int = Field(
        ge=0,
        le=100,
    )

    summary: str = Field(
        min_length=1,
        max_length=5000,
    )

    corrections: list[
        FinalReviewCorrectionAI
    ] = Field(
        default_factory=list,
        max_length=30,
    )

    # Uso interno. No se muestra al cliente.
    reasoning: str = Field(
        default="",
        max_length=4000,
    )
