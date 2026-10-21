
"""Contratos simulados de Replikers World."""

from alembic import op
import sqlalchemy as sa

revision = "d61710c1d237"
down_revision = "c51710c1d236"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "world_contracts",
        sa.Column(
            "id", sa.Integer(), primary_key=True
        ),
        sa.Column(
            "negotiation_id",
            sa.Integer(),
            sa.ForeignKey(
                "world_negotiations.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
            unique=True,
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
            "buyer_repliker_id",
            sa.Integer(),
            sa.ForeignKey(
                "replikers.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "title", sa.String(120), nullable=False
        ),
        sa.Column(
            "description", sa.Text(), nullable=False
        ),
        sa.Column(
            "currency", sa.String(10), nullable=False
        ),
        sa.Column(
            "price_cents", sa.Integer(), nullable=False
        ),
        sa.Column(
            "estimated_cost_cents",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(20), nullable=False
        ),
        sa.Column(
            "delivery_reference", sa.String(500)
        ),
        sa.Column(
            "review_note", sa.String(500)
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ("
            "'open','submitted','approved','disputed')",
            name="ck_world_contract_status",
        ),
        sa.CheckConstraint(
            "currency = 'RCR'",
            name="ck_world_contract_currency",
        ),
        sa.CheckConstraint(
            "price_cents > 0 "
            "AND estimated_cost_cents >= 0",
            name="ck_world_contract_amounts",
        ),
        sa.CheckConstraint(
            "seller_repliker_id <> buyer_repliker_id",
            name="ck_world_contract_parties",
        ),
    )

    op.create_index(
        "ix_world_contract_seller",
        "world_contracts",
        ["seller_repliker_id"],
    )

    op.create_index(
        "ix_world_contract_buyer",
        "world_contracts",
        ["buyer_repliker_id"],
    )

    op.create_table(
        "world_contract_events",
        sa.Column(
            "id", sa.Integer(), primary_key=True
        ),
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
            "actor_repliker_id",
            sa.Integer(),
            sa.ForeignKey(
                "replikers.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "event_type", sa.String(20), nullable=False
        ),
        sa.Column(
            "detail", sa.String(500), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ("
            "'opened','submitted','approved','disputed')",
            name="ck_world_contract_event_type",
        ),
    )

    op.create_index(
        "ix_world_contract_event_contract",
        "world_contract_events",
        ["contract_id"],
    )


def downgrade():
    connection = op.get_bind()

    count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM world_contracts"
        )
    ).scalar_one()

    if count:
        raise RuntimeError(
            "No se permite eliminar contratos existentes."
        )

    op.drop_index(
        "ix_world_contract_event_contract",
        table_name="world_contract_events",
    )
    op.drop_table("world_contract_events")

    op.drop_index(
        "ix_world_contract_buyer",
        table_name="world_contracts",
    )
    op.drop_index(
        "ix_world_contract_seller",
        table_name="world_contracts",
    )
    op.drop_table("world_contracts")
