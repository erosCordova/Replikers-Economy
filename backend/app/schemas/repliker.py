from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class ReplikerSkillCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )

    level: int = Field(
        ge=0,
        le=100,
    )


class ReplikerSkillPublic(BaseModel):
    id: int
    name: str
    level: int

    model_config = ConfigDict(
        from_attributes=True
    )


class ReplikerCreate(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=120,
    )

    specialty: str = Field(
        min_length=2,
        max_length=120,
    )

    description: str = Field(
        default="",
        max_length=2000,
    )

    base_price_credits: int = Field(
        default=50,
        ge=1,
        le=1_000_000,
    )

    skills: list[
        ReplikerSkillCreate
    ] = Field(
        default_factory=list,
        max_length=50,
    )


class ReplikerPublicationUpdate(
    BaseModel
):
    published: bool


class ReplikerPublic(BaseModel):
    id: int
    owner_id: int

    name: str
    specialty: str
    description: str

    status: str
    reputation_score: int

    base_price_credits: int
    balance_credits: int
    total_earnings_credits: int

    jobs_completed: int
    is_active: bool

    is_system: bool = False
    is_published: bool = True

    published_at: (
        datetime | None
    ) = None

    created_at: datetime

    skills: list[
        ReplikerSkillPublic
    ]

    model_config = ConfigDict(
        from_attributes=True
    )
