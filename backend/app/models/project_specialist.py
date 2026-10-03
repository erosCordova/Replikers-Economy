from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import false, true
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import Base


class ProjectSpecialistRequirement(Base):
    __tablename__ = (
        "project_specialist_requirements"
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "specialty",
            name=(
                "uq_project_specialist_"
                "requirement"
            ),
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

    specialty: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )

    is_mandatory: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default=true(),
    )

    is_final_gate: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default=false(),
    )

    coverage_status: Mapped[str] = (
        mapped_column(
            String(30),
            nullable=False,
            default="pending",
            server_default="pending",
        )
    )

    assigned_repliker_id: Mapped[
        int | None
    ] = mapped_column(
        ForeignKey(
            "replikers.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = (
        mapped_column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )
    )

    updated_at: Mapped[datetime] = (
        mapped_column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        )
    )

    project = relationship(
        "Project",
    )

    assigned_repliker = relationship(
        "Repliker",
    )


class ProjectSpecialistOffer(Base):
    __tablename__ = (
        "project_specialist_offers"
    )

    __table_args__ = (
        UniqueConstraint(
            "requirement_id",
            "repliker_id",
            name=(
                "uq_specialist_offer_"
                "requirement_repliker"
            ),
        ),
        Index(
            "uq_specialist_offer_one_accepted_per_requirement",
            "requirement_id",
            unique=True,
            sqlite_where=text(
                "status = 'accepted'"
            ),
            postgresql_where=text(
                "status = 'accepted'"
            ),
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

    requirement_id: Mapped[int] = mapped_column(
        ForeignKey(
            "project_specialist_requirements.id",
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

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    confidence_score: Mapped[int] = (
        mapped_column(
            Integer,
            nullable=False,
            default=0,
            server_default="0",
        )
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )

    reasoning: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )

    created_at: Mapped[datetime] = (
        mapped_column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )
    )

    responded_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    project = relationship(
        "Project",
    )

    requirement = relationship(
        "ProjectSpecialistRequirement",
    )

    repliker = relationship(
        "Repliker",
    )


class ProjectFinalReview(Base):
    __tablename__ = (
        "project_final_reviews"
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "attempt_number",
            name=(
                "uq_project_final_review_attempt"
            ),
        ),
        CheckConstraint(
            "attempt_number >= 1",
            name=(
                "ck_project_final_review_"
                "attempt_positive"
            ),
        ),
        CheckConstraint(
            (
                "status IN ("
                "'pending', "
                "'running', "
                "'approved', "
                "'corrections_requested', "
                "'failed'"
                ")"
            ),
            name=(
                "ck_project_final_review_status"
            ),
        ),
        CheckConstraint(
            (
                "score IS NULL "
                "OR (score >= 0 AND score <= 100)"
            ),
            name=(
                "ck_project_final_review_score"
            ),
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

    requirement_id: Mapped[int] = mapped_column(
        ForeignKey(
            "project_specialist_requirements.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    reviewer_repliker_id: Mapped[int] = (
        mapped_column(
            ForeignKey(
                "replikers.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
            index=True,
        )
    )

    attempt_number: Mapped[int] = (
        mapped_column(
            Integer,
            nullable=False,
        )
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )

    score: Mapped[
        int | None
    ] = mapped_column(
        Integer,
        nullable=True,
    )

    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )

    corrections_json: Mapped[str] = (
        mapped_column(
            Text,
            nullable=False,
            default="[]",
            server_default="[]",
        )
    )

    reasoning: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )

    created_at: Mapped[datetime] = (
        mapped_column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )
    )

    completed_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    project = relationship(
        "Project",
    )

    requirement = relationship(
        "ProjectSpecialistRequirement",
    )

    reviewer_repliker = relationship(
        "Repliker",
    )


class ProjectFinalCorrectionRun(Base):
    __tablename__ = (
        "project_final_correction_runs"
    )

    __table_args__ = (
        UniqueConstraint(
            "final_review_id",
            "task_id",
            name=(
                "uq_project_final_correction_"
                "review_task"
            ),
        ),
        CheckConstraint(
            (
                "status IN ("
                "'pending', "
                "'running', "
                "'qa_running', "
                "'completed', "
                "'failed'"
                ")"
            ),
            name=(
                "ck_project_final_correction_"
                "status"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    final_review_id: Mapped[int] = (
        mapped_column(
            ForeignKey(
                "project_final_reviews.id",
                ondelete="CASCADE",
            ),
            nullable=False,
            index=True,
        )
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    task_id: Mapped[int] = mapped_column(
        ForeignKey(
            "tasks.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    contract_id: Mapped[int] = (
        mapped_column(
            ForeignKey(
                "task_contracts.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
            index=True,
        )
    )

    repliker_id: Mapped[int] = (
        mapped_column(
            ForeignKey(
                "replikers.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
            index=True,
        )
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )

    instruction: Mapped[str] = (
        mapped_column(
            Text,
            nullable=False,
            default="",
        server_default="",
        )
    )

    execution_status: Mapped[str] = (
        mapped_column(
            String(30),
            nullable=False,
            default="pending",
            server_default="pending",
        )
    )

    qa_review_id: Mapped[
        int | None
    ] = mapped_column(
        ForeignKey(
            "qa_reviews.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    error_summary: Mapped[str] = (
        mapped_column(
            Text,
            nullable=False,
            default="",
            server_default="",
        )
    )

    created_at: Mapped[datetime] = (
        mapped_column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )
    )

    completed_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    final_review = relationship(
        "ProjectFinalReview",
    )

    project = relationship(
        "Project",
    )

    task = relationship(
        "Task",
    )

    contract = relationship(
        "TaskContract",
    )

    repliker = relationship(
        "Repliker",
    )

    qa_review = relationship(
        "QAReview",
    )
