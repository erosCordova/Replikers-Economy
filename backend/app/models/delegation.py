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
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import Base


ACTIVE_DELEGATION_STATUSES = (
    "requested",
    "awarded",
    "active",
)

ACTIVE_SUBCONTRACT_STATUSES = (
    "awarded",
    "active",
)


class DelegationRequest(Base):
    __tablename__ = "delegation_requests"

    __table_args__ = (
        CheckConstraint(
            "depth >= 1",
            name="ck_delegation_depth_positive",
        ),
        CheckConstraint(
            "max_budget_cents > 0",
            name="ck_delegation_budget_positive",
        ),
        CheckConstraint(
            (
                "status IN ("
                "'requested', "
                "'awarded', "
                "'active', "
                "'rejected', "
                "'cancelled', "
                "'completed'"
                ")"
            ),
            name="ck_delegation_status",
        ),
        CheckConstraint(
            (
                "decision IN ("
                "'delegate', "
                "'do_self'"
                ")"
            ),
            name="ck_delegation_decision",
        ),
        Index(
            "ix_delegation_project_status",
            "project_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    dedup_key: Mapped[str] = mapped_column(
        String(240),
        nullable=False,
        unique=True,
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

    root_contract_id: Mapped[int] = mapped_column(
        ForeignKey(
            "task_contracts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    parent_task_id: Mapped[int] = mapped_column(
        ForeignKey(
            "tasks.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    parent_request_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "delegation_requests.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    delegator_repliker_id: Mapped[int] = mapped_column(
        ForeignKey(
            "replikers.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    collaboration_thread_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "collaboration_threads.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    depth: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="requested",
        index=True,
    )

    decision: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="delegate",
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    required_skill_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    minimum_skill_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    max_budget_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
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

    parent_request = relationship(
        "DelegationRequest",
        remote_side=[id],
    )


class DelegatedTask(Base):
    __tablename__ = "delegated_tasks"

    __table_args__ = (
        CheckConstraint(
            (
                "status IN ("
                "'open', "
                "'assigned', "
                "'active', "
                "'completed', "
                "'failed', "
                "'cancelled'"
                ")"
            ),
            name="ck_delegated_task_status",
        ),
        CheckConstraint(
            "max_budget_cents > 0",
            name="ck_delegated_task_budget",
        ),
        CheckConstraint(
            "complexity BETWEEN 1 AND 100",
            name="ck_delegated_task_complexity",
        ),
        Index(
            "ix_delegated_task_project_status",
            "project_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    delegation_request_id: Mapped[int] = mapped_column(
        ForeignKey(
            "delegation_requests.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
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

    parent_task_id: Mapped[int] = mapped_column(
        ForeignKey(
            "tasks.id",
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
        default="open",
        index=True,
    )

    complexity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
    )

    required_skill_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    minimum_skill_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    max_budget_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # pylint: disable=not-callable
    )


class DelegationOffer(Base):
    __tablename__ = "delegation_offers"

    __table_args__ = (
        UniqueConstraint(
            "delegated_task_id",
            "repliker_id",
            name="uq_delegation_offer_task_repliker",
        ),
        CheckConstraint(
            "amount_cents > 0",
            name="ck_delegation_offer_amount",
        ),
        CheckConstraint(
            "selection_score BETWEEN 0 AND 100",
            name="ck_delegation_offer_score",
        ),
        Index(
            "ix_delegation_offer_task_status",
            "delegated_task_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    delegated_task_id: Mapped[int] = mapped_column(
        ForeignKey(
            "delegated_tasks.id",
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

    skill_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    reputation_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    price_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    experience_score: Mapped[int] = mapped_column(
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

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
    )

    pricing_policy_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="delegation-sim-v1",
    )

    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # pylint: disable=not-callable
    )


class Subcontract(Base):
    __tablename__ = "subcontracts"

    __table_args__ = (
        CheckConstraint(
            "amount_cents > 0",
            name="ck_subcontract_amount_positive",
        ),
        CheckConstraint(
            "reserved_cents >= 0",
            name="ck_subcontract_reserved_nonnegative",
        ),
        CheckConstraint(
            "depth >= 1",
            name="ck_subcontract_depth",
        ),
        CheckConstraint(
            (
                "status IN ("
                "'awarded', "
                "'active', "
                "'completed', "
                "'failed', "
                "'cancelled'"
                ")"
            ),
            name="ck_subcontract_status",
        ),
        Index(
            "ix_subcontract_project_status",
            "project_id",
            "status",
        ),
        Index(
            "ix_subcontract_root_contract",
            "root_contract_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    delegation_request_id: Mapped[int] = mapped_column(
        ForeignKey(
            "delegation_requests.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    delegated_task_id: Mapped[int] = mapped_column(
        ForeignKey(
            "delegated_tasks.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
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

    root_contract_id: Mapped[int] = mapped_column(
        ForeignKey(
            "task_contracts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    parent_task_id: Mapped[int] = mapped_column(
        ForeignKey(
            "tasks.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    delegator_repliker_id: Mapped[int] = mapped_column(
        ForeignKey(
            "replikers.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    subcontractor_repliker_id: Mapped[int] = mapped_column(
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
    )

    amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    reserved_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    depth: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    selection_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    pricing_policy_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="delegation-sim-v1",
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

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
