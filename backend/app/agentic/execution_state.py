from __future__ import annotations

from typing import TypedDict


class ContractExecutionState(
    TypedDict,
    total=False,
):
    contract_id: int

    project_id: int
    task_id: int
    repliker_id: int
    workspace_id: int

    instruction: str

    current_node: str
    status: str

    response_text: str
    error: str

    artifact_count: int
    artifacts: list[dict]

    integration_verified: bool

    trace: list[str]
