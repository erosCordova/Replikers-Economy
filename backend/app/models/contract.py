from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import Base


ACTIVE_CONTRACT_STATUSES = (
    "awarded",
    "active",
)


class TaskContract(Base):
    __tablename__ = "task_contracts"

    __table_args__ = (
        Index(
            "uq_task_contract_active",
            "task_id",
            unique=True,
            sqlite_where=text(
                "status IN ('awarded', 'active')"
            ),
            postgresql_where=text(
                "status IN ('awarded', 'active')"
            ),
        ),
        Index(
            "ix_task_contract_project_status",
            "project_id",
            "status",
        ),
        CheckConstraint(
            "amount_cents > 0",
            name="ck_task_contract_amount_positive",
        ),
        CheckConstraint(
            "reserved_cents >= 0",
            name="ck_task_contract_reserved_nonnegative",
        ),
        CheckConstraint(
            "selection_score BETWEEN 0 AND 100",
            name="ck_task_contract_selection_score",
        ),
        CheckConstraint(
            "skill_score BETWEEN 0 AND 100",
            name="ck_task_contract_skill_score",
        ),
        CheckConstraint(
            "reputation_score BETWEEN 0 AND 100",
            name="ck_task_contract_reputation_score",
        ),
        CheckConstraint(
            "confidence_score BETWEEN 0 AND 100",
            name="ck_task_contract_confidence_score",
        ),
        CheckConstraint(
            "price_score BETWEEN 0 AND 100",
            name="ck_task_contract_price_score",
        ),
        CheckConstraint(
            "time_score BETWEEN 0 AND 100",
            name="ck_task_contract_time_score",
        ),
        CheckConstraint(
            "risk_score BETWEEN 0 AND 100",
            name="ck_task_contract_risk_score",
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

    task_id: Mapped[int] = mapped_column(
        ForeignKey(
            "tasks.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    bid_id: Mapped[int] = mapped_column(
        ForeignKey(
            "task_bids.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        unique=True,
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

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="awarded",
        index=True,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="PEN",
    )

    amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    reserved_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    skill_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    reputation_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    confidence_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    price_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    time_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    risk_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    selection_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    selected_by: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="r00",
    )

    selection_policy_version: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="r00-selection-v1",
    )

    selection_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
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

    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    project = relationship(
        "Project",
    )

    task = relationship(
        "Task",
    )

    bid = relationship(
        "TaskBid",
    )

    repliker = relationship(
        "Repliker",
    )
