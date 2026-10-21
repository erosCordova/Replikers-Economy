"""Liquidaciones de contratos de Replikers World."""

from alembic import op
import sqlalchemy as sa

revision = "e71710c1d238"
down_revision = "d61710c1d237"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "world_contract_settlements",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),
        sa.Column(
            "contract_id",
            sa.Integer(),
            sa.ForeignKey(
                "world_contracts.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
            unique=True,
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
            "artifact_sha256",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
    )


def downgrade():
    connection = op.get_bind()

    count = connection.execute(
        sa.text(
            "SELECT COUNT(*) "
            "FROM world_contract_settlements"
        )
    ).scalar_one()

    if count:
        raise RuntimeError(
            "Existen liquidaciones registradas. "
            "No se permite eliminarlas."
        )

    op.drop_table("world_contract_settlements")
