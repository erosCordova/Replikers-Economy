from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
)


class QAReputationEventPublic(
    BaseModel
):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int
    review_id: int
    contract_id: int
    repliker_id: int

    outcome: str
    delta: int

    score_before: int
    score_after: int

    jobs_completed_before: int
    jobs_completed_after: int

    reason: str
    created_at: datetime


class QARetryRunPublic(
    BaseModel
):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int

    contract_id: int
    source_review_id: int
    next_review_id: int | None

    attempt_number: int

    status: str
    execution_status: str

    artifact_count: int

    feedback: str
    error_summary: str

    created_at: datetime
    completed_at: datetime | None


class QAFollowupPublic(
    BaseModel
):
    review_id: int
    review_status: str

    attempt_number: int
    max_attempts: int

    action: str

    retry: QARetryRunPublic | None = None

    reputation: (
        QAReputationEventPublic
        | None
    ) = None

    trace: list[str]
