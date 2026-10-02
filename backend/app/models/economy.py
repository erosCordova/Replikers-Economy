from datetime import datetime

from sqlalchemy import (
    Boolean,
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


LEDGER_ACCOUNT_KINDS = (
    "user_available",
    "user_pending",
    "project_custody",
    "platform_revenue",
    "system_clearing",
)


LEDGER_TRANSACTION_TYPES = (
    "funding",
    "allocation",
    "earning",
    "commission",
    "refund",
    "withdrawal",
    "reversal",
    "adjustment",
)


class LedgerAccount(Base):
    """
    Cuenta monetaria del ledger.

    No guarda un balance mutable.
    El balance siempre se deriva
    de las transacciones registradas.
    """

    __tablename__ = "ledger_accounts"

    __table_args__ = (
        UniqueConstraint(
            "account_key",
            name="uq_ledger_account_key",
        ),
        CheckConstraint(
            (
                "kind IN ("
                "'user_available', "
                "'user_pending', "
                "'project_custody', "
                "'platform_revenue', "
                "'system_clearing'"
                ")"
            ),
            name="ck_ledger_account_kind",
        ),
        CheckConstraint(
            (
                "("
                "kind IN "
                "('user_available', 'user_pending') "
                "AND user_id IS NOT NULL "
                "AND project_id IS NULL"
                ") OR ("
                "kind = 'project_custody' "
                "AND project_id IS NOT NULL "
                "AND user_id IS NULL"
                ") OR ("
                "kind IN "
                "('platform_revenue', 'system_clearing') "
                "AND user_id IS NULL "
                "AND project_id IS NULL"
                ")"
            ),
            name="ck_ledger_account_owner",
        ),
        Index(
            "ix_ledger_account_user_kind_currency",
            "user_id",
            "kind",
            "currency",
        ),
        Index(
            "ix_ledger_account_project_kind_currency",
            "project_id",
            "kind",
            "currency",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    account_key: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
        unique=True,
        index=True,
    )

    kind: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    project_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class LedgerTransaction(Base):
    """
    Movimiento monetario inmutable.

    Cada registro mueve un importe
    desde una cuenta hacia otra.
    """

    __tablename__ = "ledger_transactions"

    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_ledger_transaction_idempotency",
        ),
        CheckConstraint(
            "amount_cents > 0",
            name="ck_ledger_transaction_positive",
        ),
        CheckConstraint(
            "from_account_id <> to_account_id",
            name="ck_ledger_transaction_distinct_accounts",
        ),
        CheckConstraint(
            (
                "transaction_type IN ("
                "'funding', "
                "'allocation', "
                "'earning', "
                "'commission', "
                "'refund', "
                "'withdrawal', "
                "'reversal', "
                "'adjustment'"
                ")"
            ),
            name="ck_ledger_transaction_type",
        ),
        Index(
            "ix_ledger_transaction_project_created",
            "project_id",
            "created_at",
        ),
        Index(
            "ix_ledger_transaction_contract",
            "contract_id",
        ),
        Index(
            "ix_ledger_transaction_repliker",
            "repliker_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
        unique=True,
        index=True,
    )

    transaction_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
    )

    amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    from_account_id: Mapped[int] = mapped_column(
        ForeignKey(
            "ledger_accounts.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    to_account_id: Mapped[int] = mapped_column(
        ForeignKey(
            "ledger_accounts.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    project_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    contract_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "task_contracts.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    repliker_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "replikers.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    initiated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    external_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    from_account = relationship(
        "LedgerAccount",
        foreign_keys=[
            from_account_id,
        ],
    )

    to_account = relationship(
        "LedgerAccount",
        foreign_keys=[
            to_account_id,
        ],
    )
