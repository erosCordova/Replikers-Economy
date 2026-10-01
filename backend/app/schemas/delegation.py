from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class DelegatedTaskPublic(BaseModel):
    id: int

    parent_task_id: int

    title: str
    description: str

    status: str

    complexity: int

    required_skill_name: str
    minimum_skill_level: int

    max_budget_cents: int


class DelegationOfferPublic(BaseModel):
    id: int

    repliker_id: int
    repliker_name: str

    amount_cents: int

    skill_score: int
    reputation_score: int
    price_score: int
    experience_score: int
    risk_score: int
    selection_score: int

    status: str

    pricing_policy_version: str

    summary: str


class SubcontractPublic(BaseModel):
    id: int

    delegation_request_id: int
    delegated_task_id: int

    project_id: int
    root_contract_id: int
    parent_task_id: int

    delegator_repliker_id: int
    delegator_name: str

    subcontractor_repliker_id: int
    subcontractor_name: str

    status: str
    currency: str

    amount_cents: int
    reserved_cents: int

    depth: int

    selection_score: int

    pricing_policy_version: str
    selection_summary: str

    created_at: datetime


class DelegationRequestPublic(BaseModel):
    id: int

    project_id: int
    root_contract_id: int
    parent_task_id: int

    parent_request_id: int | None

    delegator_repliker_id: int
    delegator_name: str

    collaboration_thread_id: int | None

    depth: int

    status: str
    decision: str

    reason: str

    required_skill_name: str
    minimum_skill_level: int

    max_budget_cents: int

    delegated_task: DelegatedTaskPublic | None

    offers: list[
        DelegationOfferPublic
    ]

    subcontract: SubcontractPublic | None

    created_at: datetime


class DelegationRunResponse(BaseModel):
    decision: Literal[
        "do_self",
        "delegate",
        "delegate_unavailable",
    ]

    reason: str

    request: DelegationRequestPublic | None


class DelegationProjectSnapshot(BaseModel):
    project_id: int

    requests: list[
        DelegationRequestPublic
    ]
