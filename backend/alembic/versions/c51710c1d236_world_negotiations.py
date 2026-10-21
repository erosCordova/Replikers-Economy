
"""Negociaciones persistentes para Replikers World."""

from alembic import op
import sqlalchemy as sa

revision = "c51710c1d236"
down_revision = "b41710c1d235"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "world_negotiations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "idempotency_key",
            sa.String(140),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "proposal_hash",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "proposer_repliker_id",
            sa.Integer(),
            sa.ForeignKey(
                "replikers.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "target_repliker_id",
            sa.Integer(),
            sa.ForeignKey(
                "replikers.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column(
            "estimated_cost_cents",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "response_message",
            sa.String(500),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('accepted', 'rejected')",
            name="ck_world_negotiation_status",
        ),
        sa.CheckConstraint(
            "price_cents > 0 AND estimated_cost_cents >= 0",
            name="ck_world_negotiation_amounts",
        ),
        sa.CheckConstraint(
            "proposer_repliker_id <> target_repliker_id",
            name="ck_world_negotiation_parties",
        ),
        sa.CheckConstraint(
            "currency = 'RCR'",
            name="ck_world_negotiation_currency",
        ),
    )

    op.create_index(
        "ix_world_negotiation_proposer",
        "world_negotiations",
        ["proposer_repliker_id"],
    )

    op.create_index(
        "ix_world_negotiation_target",
        "world_negotiations",
        ["target_repliker_id"],
    )

    op.create_table(
        "world_negotiation_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "negotiation_id",
            sa.Integer(),
            sa.ForeignKey(
                "world_negotiations.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "author_repliker_id",
            sa.Integer(),
            sa.ForeignKey(
                "replikers.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(20),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('proposal', 'accept', 'reject')",
            name="ck_world_negotiation_event_type",
        ),
    )

    op.create_index(
        "ix_world_negotiation_event",
        "world_negotiation_events",
        ["negotiation_id"],
    )


def downgrade():
    connection = op.get_bind()

    count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM world_negotiations"
        )
    ).scalar_one()

    if count:
        raise RuntimeError(
            "Existen negociaciones guardadas. "
            "No se permite eliminarlas."
        )

    op.drop_index(
        "ix_world_negotiation_event",
        table_name="world_negotiation_events",
    )
    op.drop_table("world_negotiation_events")

    op.drop_index(
        "ix_world_negotiation_target",
        table_name="world_negotiations",
    )
    op.drop_index(
        "ix_world_negotiation_proposer",
        table_name="world_negotiations",
    )
    op.drop_table("world_negotiations")
