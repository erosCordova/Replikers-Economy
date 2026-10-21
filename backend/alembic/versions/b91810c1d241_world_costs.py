
"""Gastos contractuales vinculados al ledger RCR."""

from alembic import op
import sqlalchemy as sa

revision = "b91810c1d241"
down_revision = "a91810c1d240"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "world_contract_expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "contract_id",
            sa.Integer(),
            sa.ForeignKey(
                "world_contracts.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "seller_repliker_id",
            sa.Integer(),
            sa.ForeignKey(
                "replikers.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "provider_repliker_id",
            sa.Integer(),
            sa.ForeignKey(
                "replikers.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "ledger_transaction_id",
            sa.Integer(),
            sa.ForeignKey(
                "ledger_transactions.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "expense_key",
            sa.String(48),
            nullable=False,
        ),
        sa.Column(
            "amount_cents",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "note",
            sa.String(240),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "contract_id",
            "expense_key",
            name="uq_world_cost_contract_key",
        ),
        sa.CheckConstraint(
            "amount_cents > 0",
            name="ck_world_cost_positive",
        ),
        sa.CheckConstraint(
            "seller_repliker_id <> provider_repliker_id",
            name="ck_world_cost_parties",
        ),
    )

    op.create_index(
        "ix_world_cost_contract",
        "world_contract_expenses",
        ["contract_id"],
    )


def downgrade():
    connection = op.get_bind()

    count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM world_contract_expenses"
        )
    ).scalar_one()

    if count:
        raise RuntimeError(
            "No se permite eliminar gastos existentes."
        )

    op.drop_index(
        "ix_world_cost_contract",
        table_name="world_contract_expenses",
    )
    op.drop_table("world_contract_expenses")
