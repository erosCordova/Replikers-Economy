from datetime import datetime

from pydantic import BaseModel, Field


class AppearancePublic(BaseModel):
    avatar_style: str
    primary_color: str
    secondary_color: str
    face_type: str
    eye_style: str
    accessory: str
    background_style: str
    avatar_url: str | None = None


class AppearanceUpdate(BaseModel):
    avatar_style: str = Field(
        default="synthetic",
        max_length=50,
    )

    primary_color: str = Field(
        default="#2563eb",
        pattern=r"^#[0-9A-Fa-f]{6}$",
    )

    secondary_color: str = Field(
        default="#06b6d4",
        pattern=r"^#[0-9A-Fa-f]{6}$",
    )

    face_type: str = Field(
        default="core",
        max_length=50,
    )

    eye_style: str = Field(
        default="glow",
        max_length=50,
    )

    accessory: str = Field(
        default="none",
        max_length=80,
    )

    background_style: str = Field(
        default="grid",
        max_length=50,
    )

    avatar_url: str | None = Field(
        default=None,
        max_length=2000,
    )


class EcosystemSkill(BaseModel):
    name: str
    level: int


class EcosystemAgent(BaseModel):
    id: int
    owner_id: int

    name: str
    specialty: str
    description: str

    status: str
    reputation_score: int
    jobs_completed: int

    is_active: bool

    skills: list[EcosystemSkill]

    appearance: AppearancePublic

    current_project_id: int | None = None
    current_task_id: int | None = None

    current_activity: str | None = None


class ActivityEventPublic(BaseModel):
    id: int

    project_id: int | None
    task_id: int | None
    repliker_id: int | None

    actor_type: str
    event_type: str

    title: str
    description: str

    created_at: datetime


class AgentMessagePublic(BaseModel):
    id: int

    project_id: int
    task_id: int | None

    sender_type: str
    sender_repliker_id: int | None

    receiver_type: str
    receiver_repliker_id: int | None

    message_type: str
    content: str

    created_at: datetime


class EcosystemProject(BaseModel):
    id: int
    title: str
    status: str

    task_count: int
    agents_involved: int


class EcosystemSnapshot(BaseModel):
    agents: list[EcosystemAgent]

    projects: list[EcosystemProject]

    events: list[ActivityEventPublic]

    messages: list[AgentMessagePublic]
