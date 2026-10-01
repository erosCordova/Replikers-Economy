from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ReplikerTaskDecision(Base):
    __tablename__ = "repliker_task_decisions"

    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "repliker_id",
            name="uq_repliker_task_decision",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    task_id: Mapped[int] = mapped_column(
        ForeignKey(
            "tasks.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    repliker_id: Mapped[int] = mapped_column(
        ForeignKey(
            "replikers.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    decision: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    amount_cents: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    confidence_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    estimated_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    reasoning: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # pylint: disable=not-callable
    )

    task = relationship(
        "Task",
    )

    repliker = relationship(
        "Repliker",
    )
