from pydantic import (
    BaseModel,
    Field,
)


class ReplikerDeveloperUpdate(BaseModel):
    enabled: bool = False

    source_code: str = Field(
        default="",
        max_length=40_000,
    )


class ReplikerDeveloperPublic(BaseModel):
    repliker_id: int

    enabled: bool

    language: str

    filename: str

    entrypoint: str

    source_code: str

    checksum: str

    version: int
