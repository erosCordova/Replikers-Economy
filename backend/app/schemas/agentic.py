from datetime import datetime

from pydantic import (
    BaseModel,
    Field,
)


class AgenticToolPublic(BaseModel):
    name: str

    label: str

    pack: str

    description: str

    risk: str

    permission_level: str


class AgenticToolUpdate(BaseModel):
    tool_names: list[str] = Field(
        min_length=1,
        max_length=50,
    )


class AgentToolProfilePublic(BaseModel):
    repliker_id: int

    repliker_name: str

    owner_id: int

    specialty: str

    explicit_configuration: bool

    tools: list[
        AgenticToolPublic
    ]


class AgenticRuntimePublic(BaseModel):
    framework: str

    langchain_version: str

    langgraph_version: str

    provider: str

    model: str

    tool_count: int

    default_tools: list[str]

    graph_nodes: list[str]


class AgenticGraphNodePublic(BaseModel):
    name: str

    label: str

    status: str


class AgenticActivityPublic(BaseModel):
    id: int

    project_id: int | None

    task_id: int | None

    repliker_id: int | None

    actor_type: str

    event_type: str

    title: str

    description: str

    created_at: datetime


class AgenticProjectSnapshot(BaseModel):
    project_id: int

    project_title: str

    project_status: str

    payment_status: str

    framework: str

    langchain_version: str

    langgraph_version: str

    provider: str

    model: str

    current_node: str

    next_action: str

    has_delegations: bool

    nodes: list[
        AgenticGraphNodePublic
    ]

    agents: list[
        AgentToolProfilePublic
    ]

    recent_activity: list[
        AgenticActivityPublic
    ]
