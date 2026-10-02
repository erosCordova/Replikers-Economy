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


class QARetryRun(Base):
    __tablename__ = "qa_retry_runs"

    __table_args__ = (
        UniqueConstraint(
            "source_review_id",
            name="uq_qa_retry_source_review",
        ),
        CheckConstraint(
            "attempt_number >= 2",
            name="ck_qa_retry_attempt",
        ),
        CheckConstraint(
            "artifact_count >= 0",
            name="ck_qa_retry_artifact_count",
        ),
        CheckConstraint(
            (
                "status IN "
                "('running', 'completed', "
                "'execution_failed', 'exhausted')"
            ),
            name="ck_qa_retry_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    contract_id: Mapped[int] = mapped_column(
        ForeignKey(
            "task_contracts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    source_review_id: Mapped[int] = mapped_column(
        ForeignKey(
            "qa_reviews.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    next_review_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "qa_reviews.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        unique=True,
        index=True,
    )

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="running",
        index=True,
    )

    execution_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="pending",
    )

    artifact_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    feedback: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    error_summary: Mapped[str] = mapped_column(
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


class QAReputationEvent(Base):
    __tablename__ = "qa_reputation_events"

    __table_args__ = (
        UniqueConstraint(
            "review_id",
            name="uq_qa_reputation_review",
        ),
        CheckConstraint(
            (
                "outcome IN "
                "('passed', 'failed', 'needs_review')"
            ),
            name="ck_qa_reputation_outcome",
        ),
        CheckConstraint(
            "delta BETWEEN -10 AND 10",
            name="ck_qa_reputation_delta",
        ),
        CheckConstraint(
            "score_before BETWEEN 0 AND 100",
            name="ck_qa_reputation_before",
        ),
        CheckConstraint(
            "score_after BETWEEN 0 AND 100",
            name="ck_qa_reputation_after",
        ),
        CheckConstraint(
            "jobs_completed_before >= 0",
            name="ck_qa_reputation_jobs_before",
        ),
        CheckConstraint(
            "jobs_completed_after >= 0",
            name="ck_qa_reputation_jobs_after",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    review_id: Mapped[int] = mapped_column(
        ForeignKey(
            "qa_reviews.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
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

    repliker_id: Mapped[int] = mapped_column(
        ForeignKey(
            "replikers.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    outcome: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    delta: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    score_before: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    score_after: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    jobs_completed_before: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    jobs_completed_after: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
