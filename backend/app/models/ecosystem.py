from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ReplikerAppearance(Base):
    __tablename__ = "repliker_appearances"

    __table_args__ = (
        UniqueConstraint(
            "repliker_id",
            name="uq_repliker_appearance",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    repliker_id: Mapped[int] = mapped_column(
        ForeignKey(
            "replikers.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    avatar_style: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="synthetic",
    )

    primary_color: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="#2563eb",
    )

    secondary_color: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="#06b6d4",
    )

    face_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="core",
    )

    eye_style: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="glow",
    )

    accessory: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="none",
    )

    background_style: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="grid",
    )

    avatar_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # pylint: disable=not-callable
        onupdate=func.now(),  # pylint: disable=not-callable
    )


class AgentActivityEvent(Base):
    __tablename__ = "agent_activity_events"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    project_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    task_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "tasks.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    repliker_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "replikers.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    actor_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="system",
    )

    event_type: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # pylint: disable=not-callable
    )


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(
        primary_key=True,
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

    sender_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="repliker",
    )

    sender_repliker_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "replikers.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    receiver_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="project",
    )

    receiver_repliker_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "replikers.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    message_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="coordination",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # pylint: disable=not-callable
    )
