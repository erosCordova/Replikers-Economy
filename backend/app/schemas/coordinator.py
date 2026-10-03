from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

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


class PlannedSpecialist(BaseModel):
    specialty: str = Field(
        min_length=2,
        max_length=120,
    )

    reason: str = Field(
        default="Necesario para el proyecto.",
        max_length=1000,
    )

    mandatory: bool = True
    final_gate: bool = False

    model_config = ConfigDict(
        extra="forbid"
    )


class PlannedTask(BaseModel):
    title: str
    description: str

    required_specialty: str = Field(
        default="Generalist",
        min_length=2,
        max_length=120,
    )

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

    required_specialists: list[
        PlannedSpecialist
    ] = Field(
        default_factory=list
    )

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

    required_specialists: list[
        PlannedSpecialist
    ] = Field(
        default_factory=list
    )

    market_gaps: list[str]

    tasks: list[PlannedTaskResponse]
