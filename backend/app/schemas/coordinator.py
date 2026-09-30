from pydantic import BaseModel, ConfigDict, Field

from app.schemas.task import TaskPublic


class PlannedSkill(BaseModel):
    skill_name: str

    minimum_level: int = Field(
        ge=0,
        le=100,
    )

    model_config = ConfigDict(
        extra="forbid"
    )


class PlannedTask(BaseModel):
    title: str
    description: str

    complexity: int = Field(
        ge=1,
        le=100,
    )

    max_budget_cents: int = Field(
        ge=100,
    )

    required_skills: list[PlannedSkill]

    acceptance_criteria: list[str]

    model_config = ConfigDict(
        extra="forbid"
    )


class AIProjectPlan(BaseModel):
    summary: str
    strategy: str

    market_gaps: list[str]

    tasks: list[PlannedTask]

    model_config = ConfigDict(
        extra="forbid"
    )


class PlannedTaskResponse(BaseModel):
    task: TaskPublic

    acceptance_criteria: list[str]


class CoordinatorPlanResponse(BaseModel):
    project_id: int
    coordinator: str

    summary: str
    strategy: str

    planned_budget_cents: int
    client_budget_cents: int | None

    market_gaps: list[str]

    tasks: list[PlannedTaskResponse]
