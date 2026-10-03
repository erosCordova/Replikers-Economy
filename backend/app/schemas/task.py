from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class TaskSkillCreate(BaseModel):
    skill_name: str = Field(
        min_length=1,
        max_length=100,
    )

    minimum_level: int = Field(
        ge=0,
        le=100,
    )


class TaskSkillPublic(BaseModel):
    id: int
    skill_name: str
    minimum_level: int

    model_config = ConfigDict(
        from_attributes=True
    )


class TaskCreate(BaseModel):
    title: str = Field(
        min_length=2,
        max_length=180,
    )

    description: str = Field(
        min_length=5,
        max_length=5000,
    )

    required_specialty: str = Field(
        default="Generalist",
        min_length=2,
        max_length=120,
    )

    complexity: int = Field(
        default=50,
        ge=1,
        le=100,
    )

    max_budget_cents: int | None = Field(
        default=None,
        ge=100,
    )

    required_skills: list[TaskSkillCreate] = Field(
        default_factory=list,
        max_length=30,
    )


class BidCreate(BaseModel):
    repliker_id: int

    amount_cents: int = Field(
        ge=100,
    )

    confidence_score: int = Field(
        ge=0,
        le=100,
    )

    estimated_minutes: int | None = Field(
        default=None,
        ge=1,
    )

    message: str = Field(
        default="",
        max_length=2000,
    )


class BidPublic(BaseModel):
    id: int
    task_id: int
    repliker_id: int
    amount_cents: int
    confidence_score: int
    estimated_minutes: int | None
    message: str
    status: str
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class TaskPublic(BaseModel):
    id: int
    project_id: int

    title: str
    description: str

    required_specialty: str = "Generalist"

    status: str
    complexity: int

    max_budget_cents: int | None

    created_at: datetime

    required_skills: list[TaskSkillPublic]

    model_config = ConfigDict(
        from_attributes=True
    )
