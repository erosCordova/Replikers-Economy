
"""Historial persistente de eventos World."""

from alembic import op
import sqlalchemy as sa

revision = "d91810c1d243"
down_revision = "c91810c1d242"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "world_agent_events",
        sa.Column(
            "id", sa.Integer(), primary_key=True
        ),
        sa.Column(
            "event_key",
            sa.String(64),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "round_id",
            sa.String(80),
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
            "owner_id",
            sa.Integer(),
            sa.ForeignKey(
                "users.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "negotiation_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "kind",
            sa.String(24),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(48),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_world_agent_events_owner_id",
        "world_agent_events",
        ["owner_id", "id"],
    )

    op.create_index(
        "ix_world_agent_events_actor_id",
        "world_agent_events",
        ["repliker_id", "id"],
    )


def downgrade():
    count = op.get_bind().execute(
        sa.text(
            "SELECT COUNT(*) FROM world_agent_events"
        )
    ).scalar_one()

    if count:
        raise RuntimeError(
            "No eliminar historial de eventos existente."
        )

    op.drop_index(
        "ix_world_agent_events_actor_id",
        table_name="world_agent_events",
    )

    op.drop_index(
        "ix_world_agent_events_owner_id",
        table_name="world_agent_events",
    )

    op.drop_table("world_agent_events")
