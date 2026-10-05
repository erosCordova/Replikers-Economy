from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class RequirementCreate(BaseModel):
    title: str = Field(
        min_length=2,
        max_length=180,
    )

    description: str = Field(
        default="",
        max_length=2000,
    )

    is_mandatory: bool = True


class RequirementPublic(BaseModel):
    id: int
    title: str
    description: str
    is_mandatory: bool
    verification_status: str

    model_config = ConfigDict(
        from_attributes=True
    )


class ProjectCreate(BaseModel):
    title: str = Field(
        min_length=3,
        max_length=180,
    )

    description: str = Field(
        min_length=10,
        max_length=5000,
    )

    budget_limit_cents: int | None = Field(
        default=None,
        ge=100,
    )

    currency: str = Field(
        default="PEN",
        min_length=3,
        max_length=10,
    )

    requirements: list[RequirementCreate] = Field(
        default_factory=list,
        max_length=100,
    )


class ProjectPublic(BaseModel):
    id: int
    client_id: int

    title: str
    description: str
    status: str

    currency: str
    budget_limit_cents: int | None
    quoted_amount_cents: int | None
    payment_status: str

    created_at: datetime

    requirements: list[RequirementPublic]

    model_config = ConfigDict(
        from_attributes=True
    )


class ProjectTrackingTaskPublic(BaseModel):
    id: int
    title: str
    status: str
    required_specialty: str
    max_budget_cents: int | None


class ProjectTrackingTasksPublic(BaseModel):
    total: int
    completed: int
    active: int
    pending: int

    items: list[ProjectTrackingTaskPublic]


class ProjectTrackingQAPublic(BaseModel):
    reviews_total: int
    latest_reviews: int
    passed: int
    failed: int
    pending: int


class ProjectTrackingTeamMemberPublic(BaseModel):
    repliker_id: int
    name: str
    specialty: str
    status: str
    active_contracts: int
    is_final_reviewer: bool


class ProjectTrackingTeamPublic(BaseModel):
    total: int
    members: list[
        ProjectTrackingTeamMemberPublic
    ]


class ProjectTrackingBudgetPublic(BaseModel):
    currency: str

    budget_limit_cents: int | None
    quoted_amount_cents: int | None

    contracted_cents: int
    funded_cents: int
    earnings_cents: int
    commission_cents: int

    remaining_budget_cents: int | None

    payment_status: str


class ProjectTrackingFinalReviewPublic(BaseModel):
    id: int
    attempt_number: int

    status: str
    score: int | None
    summary: str

    corrections_count: int

    reviewer_repliker_id: int | None
    reviewer_name: str | None

    completed_at: datetime | None


class ProjectTrackingActivityPublic(BaseModel):
    id: int

    task_id: int | None
    repliker_id: int | None

    actor_type: str
    event_type: str

    title: str
    description: str

    created_at: datetime


class ProjectTrackingPublic(BaseModel):
    project_id: int
    project_title: str
    project_status: str

    stage: str
    stage_label: str
    next_action: str

    progress_percent: int
    progress_basis: dict[str, float]

    tasks: ProjectTrackingTasksPublic
    qa: ProjectTrackingQAPublic
    team: ProjectTrackingTeamPublic
    budget: ProjectTrackingBudgetPublic

    final_review: (
        ProjectTrackingFinalReviewPublic
        | None
    )

    report: ProjectTrackingReportPublic

    delivery: ProjectTrackingDeliveryPublic

    recent_activity: list[
        ProjectTrackingActivityPublic
    ]


class ProjectTrackingIncidentPublic(
    BaseModel
):
    kind: str
    severity: str
    title: str
    detail: str

    task_id: int | None
    task_title: str | None


class ProjectTrackingReportPublic(
    BaseModel
):
    status: str
    summary: str
    progress_percent: int

    tasks_total: int
    tasks_completed: int

    qa_passed: int
    qa_failed: int

    incidents_total: int

    incidents: list[
        ProjectTrackingIncidentPublic
    ]


class ProjectTrackingDeliveryFilePublic(
    BaseModel
):
    artifact_id: int
    workspace_id: int
    task_id: int | None

    relative_path: str
    media_type: str

    size_bytes: int
    sha256: str


class ProjectTrackingDeliveryVersionPublic(
    BaseModel
):
    version: str

    review_id: int
    review_attempt: int

    score: int | None
    summary: str

    vera_completed_at: datetime | None

    client_decision: str
    client_comment: str
    client_decided_at: datetime | None

    status: str
    is_current: bool


class ProjectTrackingDeliveryPublic(
    BaseModel
):
    version: str
    review_attempt: int | None

    versions_total: int

    history: list[
        ProjectTrackingDeliveryVersionPublic
    ]

    ready: bool
    technical_ready: bool
    status: str

    client_decision: str
    client_comment: str
    client_decision_review_attempt: int | None
    client_decided_at: datetime | None
    client_action_required: bool

    vera_approved: bool
    vera_status: str

    corrections_requested: int

    files_count: int
    total_size_bytes: int

    files: list[
        ProjectTrackingDeliveryFilePublic
    ]

    message: str



class ProjectDeliveryDecisionCreate(
    BaseModel
):
    decision: Literal[
        "accepted",
        "corrections_requested",
    ]

    comment: str = Field(
        default="",
        max_length=4000,
    )


class ProjectDeliveryDecisionPublic(
    BaseModel
):
    project_id: int

    decision: str
    comment: str

    review_attempt: int

    created_at: datetime
