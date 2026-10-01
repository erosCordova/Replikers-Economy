from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)


MessagePriority = Literal[
    "low",
    "normal",
    "high",
    "urgent",
]


class CollaborationParticipantPublic(
    BaseModel
):
    participant_key: str
    participant_type: str
    repliker_id: int | None
    role: str


class CollaborationThreadPublic(
    BaseModel
):
    id: int

    project_id: int
    task_id: int | None
    contract_id: int | None

    kind: str
    subject: str
    status: str

    created_by_type: str

    participants: list[
        CollaborationParticipantPublic
    ]

    message_count: int

    created_at: datetime
    updated_at: datetime


class CollaborationMessagePublic(
    BaseModel
):
    id: int

    project_id: int
    task_id: int | None

    thread_id: int | None
    thread_subject: str | None

    contract_id: int | None
    reply_to_message_id: int | None

    sender_type: str
    sender_repliker_id: int | None

    receiver_type: str
    receiver_repliker_id: int | None

    message_type: str
    content: str

    priority: str
    delivery_status: str

    requires_ack: bool

    acknowledged_at: datetime | None
    resolved_at: datetime | None

    legacy: bool

    created_at: datetime


class ClientMessageCreate(BaseModel):
    task_id: int | None = Field(
        default=None,
        ge=1,
    )

    content: str = Field(
        min_length=1,
        max_length=4000,
    )

    priority: MessagePriority = "normal"


class ClientReplyCreate(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=4000,
    )

    priority: MessagePriority = "normal"

    reply_to_message_id: int | None = Field(
        default=None,
        ge=1,
    )


class CollaborationProjectSnapshot(
    BaseModel
):
    project_id: int

    threads: list[
        CollaborationThreadPublic
    ]

    messages: list[
        CollaborationMessagePublic
    ]


class CollaborationActionResponse(
    BaseModel
):
    success: bool
    message: str
