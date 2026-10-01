from __future__ import annotations

from pydantic import (
    BaseModel,
    Field,
)


class ExecutionAgentRunRequest(
    BaseModel
):
    instruction: str = Field(
        default="",
        max_length=12000,
    )


class ExecutionGraphArtifactPublic(
    BaseModel
):
    id: int

    relative_path: str

    media_type: str

    size_bytes: int

    sha256: str


class ExecutionAgentRunResponse(
    BaseModel
):
    contract_id: int

    project_id: int

    task_id: int

    repliker_id: int

    workspace_id: int

    current_node: str

    status: str

    response_text: str

    error: str

    artifact_count: int

    artifacts: list[
        ExecutionGraphArtifactPublic
    ]

    trace: list[str]
