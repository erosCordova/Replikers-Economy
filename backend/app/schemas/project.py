from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RequirementCreate(BaseModel):
    title: str = Field(
        min_length=2,
        max_length=180,
    )

    description: str = Field(
        default="",
        max_length=2000,
    )

    is_mandatory: bool = True


class RequirementPublic(BaseModel):
    id: int
    title: str
    description: str
    is_mandatory: bool
    verification_status: str

    model_config = ConfigDict(
        from_attributes=True
    )


class ProjectCreate(BaseModel):
    title: str = Field(
        min_length=3,
        max_length=180,
    )

    description: str = Field(
        min_length=10,
        max_length=5000,
    )

    budget_limit_cents: int | None = Field(
        default=None,
        ge=100,
    )

    currency: str = Field(
        default="PEN",
        min_length=3,
        max_length=10,
    )

    requirements: list[RequirementCreate] = Field(
        default_factory=list,
        max_length=100,
    )


class ProjectPublic(BaseModel):
    id: int
    client_id: int

    title: str
    description: str

    status: str

    currency: str
    budget_limit_cents: int | None
    quoted_amount_cents: int | None

    payment_status: str

    created_at: datetime

    requirements: list[RequirementPublic]

    model_config = ConfigDict(
        from_attributes=True
    )
