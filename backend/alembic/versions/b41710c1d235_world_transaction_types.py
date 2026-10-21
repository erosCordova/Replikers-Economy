"""Tipos economicos de Replikers World."""

from alembic import op
import sqlalchemy as sa

revision = "b41710c1d235"
down_revision = "a91710c1d234"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "ledger_transactions"
    ) as batch:
        batch.drop_constraint(
            'ck_ledger_transaction_type',
            type_="check",
        )
        batch.create_check_constraint(
            'ck_ledger_transaction_type',
            "transaction_type IN ('funding', 'allocation', 'earning', 'commission', 'refund', 'withdrawal', 'reversal', 'adjustment', 'world_initial_grant', 'world_agent_transfer')",
        )


def downgrade():
    connection = op.get_bind()

    count = connection.execute(
        sa.text(
            "SELECT COUNT(*) "
            "FROM ledger_transactions "
            "WHERE transaction_type IN "
            "('world_initial_grant', "
            "'world_agent_transfer')"
        )
    ).scalar_one()

    if count:
        raise RuntimeError(
            "Existen transacciones de Replikers World. "
            "No se permite revertir esta migracion."
        )

    with op.batch_alter_table(
        "ledger_transactions"
    ) as batch:
        batch.drop_constraint(
            'ck_ledger_transaction_type',
            type_="check",
        )
        batch.create_check_constraint(
            'ck_ledger_transaction_type',
            "transaction_type IN ('funding', 'allocation', 'earning', 'commission', 'refund', 'withdrawal', 'reversal', 'adjustment')",
        )
