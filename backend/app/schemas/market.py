from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AgentDecisionAI(BaseModel):
    decision: Literal[
        "bid",
        "pass",
    ]

    amount_cents: int | None = Field(
        default=None,
        ge=100,
    )

    confidence_score: int = Field(
        ge=0,
        le=100,
    )

    estimated_minutes: int | None = Field(
        default=None,
        ge=1,
    )

    message: str = Field(
        default="",
        max_length=1500,
    )

    reasoning: str = Field(
        default="",
        max_length=4000,
    )


class DecisionPublic(BaseModel):
    id: int

    task_id: int

    repliker_id: int
    repliker_name: str
    repliker_specialty: str

    decision: str

    amount_cents: int | None

    confidence_score: int

    estimated_minutes: int | None

    message: str
    reasoning: str

    created_at: datetime


class MarketTaskResult(BaseModel):
    task_id: int
    title: str
    status: str

    decisions: list[
        DecisionPublic
    ]


class MarketRunResponse(BaseModel):
    project_id: int

    project_status: str

    tasks_processed: int
    agents_considered: int

    new_decisions: int

    bid_count: int
    pass_count: int

    errors: list[str]

    tasks: list[
        MarketTaskResult
    ]


class MarketSnapshotResponse(BaseModel):
    project_id: int

    project_status: str

    bid_count: int
    pass_count: int

    tasks: list[
        MarketTaskResult
    ]
