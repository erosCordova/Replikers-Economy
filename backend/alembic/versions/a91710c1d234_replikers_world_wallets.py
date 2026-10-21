"""Billeteras individuales para Replikers World.

Moneda inicial: RCR, exclusivamente simulada.
"""

from alembic import op
import sqlalchemy as sa

revision = "a91710c1d234"
down_revision = 'c41d8a7e2b90'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ledger_accounts") as batch:
        batch.add_column(
            sa.Column(
                "repliker_id",
                sa.Integer(),
                nullable=True,
            )
        )

        batch.create_foreign_key(
            "fk_ledger_account_repliker",
            'replikers',
            ["repliker_id"],
            ["id"],
            ondelete="RESTRICT",
        )

        batch.drop_constraint(
            "ck_ledger_account_kind",
            type_="check",
        )

        batch.drop_constraint(
            "ck_ledger_account_owner",
            type_="check",
        )

        batch.create_check_constraint(
            "ck_ledger_account_kind",
            "kind IN ('user_available', 'user_pending', 'project_custody', 'platform_revenue', 'system_clearing', 'repliker_available')",
        )

        batch.create_check_constraint(
            "ck_ledger_account_owner",
            "\n(\nkind IN ('user_available', 'user_pending')\nAND user_id IS NOT NULL\nAND project_id IS NULL\nAND repliker_id IS NULL\n)\nOR (\nkind = 'project_custody'\nAND project_id IS NOT NULL\nAND user_id IS NULL\nAND repliker_id IS NULL\n)\nOR (\nkind IN ('platform_revenue', 'system_clearing')\nAND user_id IS NULL\nAND project_id IS NULL\nAND repliker_id IS NULL\n)\n\nOR (\nkind = 'repliker_available'\nAND repliker_id IS NOT NULL\nAND user_id IS NULL\nAND project_id IS NULL\n)\n",
        )

        batch.create_index(
            "ix_ledger_account_repliker_currency",
            ["repliker_id", "currency"],
        )


def downgrade():
    connection = op.get_bind()

    count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM ledger_accounts "
            "WHERE kind = 'repliker_available'"
        )
    ).scalar_one()

    if count:
        raise RuntimeError(
            "Existen billeteras de Replikers. "
            "No se permite eliminarlas."
        )

    with op.batch_alter_table("ledger_accounts") as batch:
        batch.drop_index(
            "ix_ledger_account_repliker_currency"
        )

        batch.drop_constraint(
            "ck_ledger_account_owner",
            type_="check",
        )

        batch.drop_constraint(
            "ck_ledger_account_kind",
            type_="check",
        )

        batch.create_check_constraint(
            "ck_ledger_account_kind",
            "kind IN ('user_available', 'user_pending', 'project_custody', 'platform_revenue', 'system_clearing')",
        )

        batch.create_check_constraint(
            "ck_ledger_account_owner",
            "\n(\nkind IN ('user_available', 'user_pending')\nAND user_id IS NOT NULL\nAND project_id IS NULL\n\n)\nOR (\nkind = 'project_custody'\nAND project_id IS NOT NULL\nAND user_id IS NULL\n\n)\nOR (\nkind IN ('platform_revenue', 'system_clearing')\nAND user_id IS NULL\nAND project_id IS NULL\n\n)\n",
        )

        batch.drop_constraint(
            "fk_ledger_account_repliker",
            type_="foreignkey",
        )

        batch.drop_column("repliker_id")
