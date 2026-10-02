from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.database.base import Base


class QAReview(Base):
    __tablename__ = "qa_reviews"

    __table_args__ = (
        UniqueConstraint(
            "contract_id",
            "attempt_number",
            name="uq_qa_review_contract_attempt",
        ),
        CheckConstraint(
            "attempt_number >= 1",
            name="ck_qa_review_attempt_positive",
        ),
        CheckConstraint(
            (
                "status IN ("
                "'prepared', "
                "'running', "
                "'passed', "
                "'failed', "
                "'needs_review'"
                ")"
            ),
            name="ck_qa_review_status",
        ),
        CheckConstraint(
            (
                "score IS NULL "
                "OR (score >= 0 AND score <= 100)"
            ),
            name="ck_qa_review_score",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    contract_id: Mapped[int] = mapped_column(
        ForeignKey(
            "task_contracts.id",
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

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey(
            "execution_workspaces.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    execution_repliker_id: Mapped[int] = mapped_column(
        ForeignKey(
            "replikers.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    reviewer_repliker_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "replikers.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="prepared",
        index=True,
    )

    score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    reviewer_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="system_precheck",
    )

    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class QACriterionResult(Base):
    __tablename__ = "qa_criterion_results"

    __table_args__ = (
        UniqueConstraint(
            "review_id",
            "criterion_id",
            name="uq_qa_result_review_criterion",
        ),
        CheckConstraint(
            (
                "status IN ("
                "'pending', "
                "'passed', "
                "'failed', "
                "'needs_review'"
                ")"
            ),
            name="ck_qa_criterion_status",
        ),
        CheckConstraint(
            (
                "score IS NULL "
                "OR (score >= 0 AND score <= 100)"
            ),
            name="ck_qa_criterion_score",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    review_id: Mapped[int] = mapped_column(
        ForeignKey(
            "qa_reviews.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    criterion_id: Mapped[int] = mapped_column(
        ForeignKey(
            "task_acceptance_criteria.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        index=True,
    )

    score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    evidence_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class QAEvidence(Base):
    __tablename__ = "qa_evidence"

    __table_args__ = (
        CheckConstraint(
            (
                "evidence_type IN ("
                "'artifact', "
                "'tool_execution', "
                "'system'"
                ")"
            ),
            name="ck_qa_evidence_type",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    review_id: Mapped[int] = mapped_column(
        ForeignKey(
            "qa_reviews.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    criterion_result_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "qa_criterion_results.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    evidence_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
    )

    artifact_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "execution_artifacts.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    tool_execution_log_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "tool_execution_logs.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    reference: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        default="",
    )

    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
    )

    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
