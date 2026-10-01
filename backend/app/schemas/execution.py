from datetime import datetime

from pydantic import (
    BaseModel,
    Field,
)


class ExecutionRuntimePublic(
    BaseModel
):
    workspace_driver: str

    isolation_mode: str

    docker_available: bool

    command_execution_enabled: bool

    allowed_operations: list[str]


class WorkspacePublic(
    BaseModel
):
    id: int

    contract_id: int

    project_id: int

    task_id: int

    repliker_id: int

    status: str

    storage_driver: str

    root_ref: str

    max_files: int

    max_file_bytes: int

    max_total_bytes: int

    created_at: datetime


class WorkspaceWriteRequest(
    BaseModel
):
    path: str = Field(
        min_length=1,
        max_length=900,
    )

    content: str = Field(
        max_length=2_000_000,
    )


class WorkspaceReadPublic(
    BaseModel
):
    path: str

    content: str


class ArtifactPublic(
    BaseModel
):
    id: int

    workspace_id: int

    relative_path: str

    media_type: str

    size_bytes: int

    sha256: str

    created_at: datetime

    updated_at: datetime


class WorkspaceFilesPublic(
    BaseModel
):
    workspace_id: int

    files: list[str]


class ToolExecutionLogPublic(
    BaseModel
):
    id: int

    workspace_id: int

    contract_id: int

    repliker_id: int

    tool_name: str

    status: str

    target_path: str | None

    input_summary: str

    output_summary: str

    error_summary: str

    created_at: datetime
