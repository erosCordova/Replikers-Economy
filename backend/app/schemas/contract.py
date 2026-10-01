from datetime import datetime

from pydantic import BaseModel


class ContractPublic(BaseModel):
    id: int

    project_id: int
    task_id: int
    task_title: str

    bid_id: int

    repliker_id: int
    repliker_name: str

    status: str
    currency: str

    amount_cents: int
    reserved_cents: int

    skill_score: int
    reputation_score: int
    confidence_score: int
    price_score: int
    time_score: int
    risk_score: int
    selection_score: int

    selected_by: str
    selection_policy_version: str
    selection_summary: str

    created_at: datetime


class SelectionTaskResult(BaseModel):
    task_id: int
    task_title: str

    selected: bool

    contract: ContractPublic | None = None
    reason: str | None = None


class SelectionRunResponse(BaseModel):
    project_id: int
    project_status: str

    contracts_created: int

    reserved_budget_cents: int
    remaining_budget_cents: int

    tasks: list[SelectionTaskResult]


class ContractProjectSnapshot(BaseModel):
    project_id: int
    project_status: str

    reserved_budget_cents: int
    remaining_budget_cents: int

    contracts: list[ContractPublic]
