from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class QAEvidencePublic(BaseModel):
    id: int

    evidence_type: str

    criterion_result_id: int | None

    artifact_id: int | None

    tool_execution_log_id: int | None

    reference: str

    sha256: str

    summary: str

    created_at: datetime


class QACriterionResultPublic(BaseModel):
    id: int

    criterion_id: int

    criterion_description: str

    is_mandatory: bool

    status: str

    score: int | None

    reason: str

    evidence_summary: str


class QAReviewPublic(BaseModel):
    id: int

    contract_id: int

    task_id: int

    workspace_id: int

    execution_repliker_id: int

    reviewer_repliker_id: int | None

    attempt_number: int

    status: str

    score: int | None

    reviewer_type: str

    summary: str

    criteria: list[
        QACriterionResultPublic
    ]

    evidence: list[
        QAEvidencePublic
    ]

    created_at: datetime

    completed_at: datetime | None
