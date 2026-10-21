"""Memoria economica por Repliker."""

from alembic import op
import sqlalchemy as sa

revision = "f81710c1d239"
down_revision = "e71710c1d238"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "world_agent_memories",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),

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
            "repliker_id",
            sa.Integer(),
            sa.ForeignKey(
                "replikers.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),

        sa.Column(
            "peer_repliker_id",
            sa.Integer(),
            sa.ForeignKey(
                "replikers.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),

        sa.Column(
            "round_id",
            sa.String(50),
            nullable=False,
        ),

        sa.Column(
            "role",
            sa.String(20),
            nullable=False,
        ),

        sa.Column(
            "outcome",
            sa.String(20),
            nullable=False,
        ),

        sa.Column(
            "price_cents",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),

        sa.UniqueConstraint(
            "negotiation_id",
            "repliker_id",
            name="uq_world_memory_negotiation_agent",
        ),

        sa.CheckConstraint(
            "role IN ('proposer','counterparty')",
            name="ck_world_memory_role",
        ),

        sa.CheckConstraint(
            "outcome IN ('accepted','rejected')",
            name="ck_world_memory_outcome",
        ),

        sa.CheckConstraint(
            "price_cents > 0",
            name="ck_world_memory_price",
        ),

        sa.CheckConstraint(
            "repliker_id <> peer_repliker_id",
            name="ck_world_memory_participants",
        ),
    )

    op.create_index(
        "ix_world_agent_memory_history",
        "world_agent_memories",
        ["repliker_id", "id"],
    )


def downgrade():
    connection = op.get_bind()

    count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM world_agent_memories"
        )
    ).scalar_one()

    if count:
        raise RuntimeError(
            "No se permite borrar memorias existentes."
        )

    op.drop_index(
        "ix_world_agent_memory_history",
        table_name="world_agent_memories",
    )

    op.drop_table("world_agent_memories")
