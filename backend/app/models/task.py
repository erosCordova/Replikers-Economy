from datetime import datetime

from sqlalchemy import (
    Boolean,
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


class Task(Base):
    __tablename__ = "tasks"

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

    title: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="planned",
    )

    complexity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
    )

    max_budget_cents: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # pylint: disable=not-callable
    )

    project = relationship(
        "Project",
        back_populates="tasks",
    )

    required_skills = relationship(
        "TaskSkillRequirement",
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    acceptance_criteria = relationship(
        "TaskAcceptanceCriterion",
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    bids = relationship(
        "TaskBid",
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class TaskSkillRequirement(Base):
    __tablename__ = "task_skill_requirements"

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

    skill_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    minimum_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
    )

    task = relationship(
        "Task",
        back_populates="required_skills",
    )


class TaskAcceptanceCriterion(Base):
    __tablename__ = "task_acceptance_criteria"

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

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
    )

    evidence: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    is_mandatory: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    task = relationship(
        "Task",
        back_populates="acceptance_criteria",
    )


class TaskBid(Base):
    __tablename__ = "task_bids"

    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "repliker_id",
            name="uq_task_repliker_bid",
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

    amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    confidence_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
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

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # pylint: disable=not-callable
    )

    task = relationship(
        "Task",
        back_populates="bids",
    )

    repliker = relationship(
        "Repliker",
        back_populates="bids",
    )
