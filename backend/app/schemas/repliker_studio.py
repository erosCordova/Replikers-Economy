from pydantic import (
    BaseModel,
    Field,
)

from app.schemas.agentic import (
    AgenticToolPublic,
)


class StudioSkillUpdate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )

    level: int = Field(
        ge=0,
        le=100,
    )


class StudioKnowledgeUpdate(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=160,
    )

    content: str = Field(
        min_length=1,
        max_length=20_000,
    )

    enabled: bool = True


class StudioKnowledgePublic(
    StudioKnowledgeUpdate
):
    id: int


class StudioRuleUpdate(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=160,
    )

    instruction: str = Field(
        min_length=1,
        max_length=5_000,
    )

    priority: int = Field(
        default=50,
        ge=0,
        le=100,
    )

    enabled: bool = True


class StudioRulePublic(
    StudioRuleUpdate
):
    id: int


class ReplikerStudioUpdate(BaseModel):
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
        max_length=2_000,
    )

    base_price_credits: int = Field(
        ge=1,
        le=1_000_000,
    )

    purpose: str = Field(
        default="",
        max_length=5_000,
    )

    personality: str = Field(
        default="",
        max_length=5_000,
    )

    communication_style: str = Field(
        default="",
        max_length=3_000,
    )

    instructions: str = Field(
        default="",
        max_length=12_000,
    )

    skills: list[
        StudioSkillUpdate
    ] = Field(
        default_factory=list,
        max_length=50,
    )

    knowledge: list[
        StudioKnowledgeUpdate
    ] = Field(
        default_factory=list,
        max_length=50,
    )

    rules: list[
        StudioRuleUpdate
    ] = Field(
        default_factory=list,
        max_length=50,
    )

    tool_names: list[str] = Field(
        min_length=1,
        max_length=50,
    )


class StudioSkillPublic(BaseModel):
    id: int
    name: str
    level: int


class ReplikerStudioPublic(BaseModel):
    repliker_id: int
    owner_id: int

    name: str
    specialty: str
    description: str

    base_price_credits: int

    purpose: str
    personality: str
    communication_style: str
    instructions: str

    config_version: int

    skills: list[
        StudioSkillPublic
    ]

    knowledge: list[
        StudioKnowledgePublic
    ]

    rules: list[
        StudioRulePublic
    ]

    tools: list[
        AgenticToolPublic
    ]

    explicit_tool_configuration: bool
