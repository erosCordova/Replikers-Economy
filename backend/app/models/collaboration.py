from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import Base


ACTIVE_THREAD_STATUSES = (
    "open",
    "blocked",
    "waiting",
)


class CollaborationThread(Base):
    __tablename__ = "collaboration_threads"

    __table_args__ = (
        UniqueConstraint(
            "contract_id",
            "kind",
            name="uq_collaboration_contract_kind",
        ),
        CheckConstraint(
            (
                "kind IN ("
                "'task_execution', "
                "'client_coordination', "
                "'delegation', "
                "'qa', "
                "'handoff', "
                "'incident'"
                ")"
            ),
            name="ck_collaboration_thread_kind",
        ),
        CheckConstraint(
            (
                "status IN ("
                "'open', "
                "'blocked', "
                "'waiting', "
                "'resolved', "
                "'closed'"
                ")"
            ),
            name="ck_collaboration_thread_status",
        ),
        Index(
            "ix_collaboration_thread_project_status",
            "project_id",
            "status",
        ),
        Index(
            "ix_collaboration_thread_task",
            "task_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    task_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "tasks.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    contract_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "task_contracts.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    kind: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
    )

    subject: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="open",
        index=True,
    )

    created_by_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="r00",
    )

    created_by_repliker_id: Mapped[int | None] = (
        mapped_column(
            ForeignKey(
                "replikers.id",
                ondelete="SET NULL",
            ),
            nullable=True,
        )
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # pylint: disable=not-callable
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # pylint: disable=not-callable
        onupdate=func.now(),  # pylint: disable=not-callable
    )

    participants = relationship(
        "CollaborationParticipant",
        back_populates="thread",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CollaborationParticipant(Base):
    __tablename__ = "collaboration_participants"

    __table_args__ = (
        UniqueConstraint(
            "thread_id",
            "participant_key",
            name="uq_collaboration_participant",
        ),
        Index(
            "ix_collaboration_participant_repliker",
            "repliker_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    thread_id: Mapped[int] = mapped_column(
        ForeignKey(
            "collaboration_threads.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    participant_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    participant_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    repliker_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "replikers.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="participant",
    )

    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # pylint: disable=not-callable
    )

    thread = relationship(
        "CollaborationThread",
        back_populates="participants",
    )


class CollaborationMessageState(Base):
    __tablename__ = "collaboration_message_states"

    __table_args__ = (
        CheckConstraint(
            (
                "priority IN ("
                "'low', "
                "'normal', "
                "'high', "
                "'urgent'"
                ")"
            ),
            name="ck_collaboration_message_priority",
        ),
        CheckConstraint(
            (
                "delivery_status IN ("
                "'sent', "
                "'acknowledged', "
                "'resolved'"
                ")"
            ),
            name="ck_collaboration_delivery_status",
        ),
        Index(
            "ix_collaboration_state_thread_status",
            "thread_id",
            "delivery_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    message_id: Mapped[int] = mapped_column(
        ForeignKey(
            "agent_messages.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    thread_id: Mapped[int] = mapped_column(
        ForeignKey(
            "collaboration_threads.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    contract_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "task_contracts.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    reply_to_message_id: Mapped[int | None] = (
        mapped_column(
            ForeignKey(
                "agent_messages.id",
                ondelete="SET NULL",
            ),
            nullable=True,
            index=True,
        )
    )

    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="normal",
    )

    delivery_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="sent",
    )

    requires_ack: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    acknowledged_at: Mapped[datetime | None] = (
        mapped_column(
            DateTime(timezone=True),
            nullable=True,
        )
    )

    resolved_at: Mapped[datetime | None] = (
        mapped_column(
            DateTime(timezone=True),
            nullable=True,
        )
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # pylint: disable=not-callable
    )
