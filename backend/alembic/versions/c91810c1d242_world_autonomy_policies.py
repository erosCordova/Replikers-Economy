
"""Politicas y eventos de autonomia World."""

from alembic import op
import sqlalchemy as sa

revision = "c91810c1d242"
down_revision = "b91810c1d241"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "world_agent_autonomy_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "repliker_id", sa.Integer(),
            sa.ForeignKey(
                "replikers.id", ondelete="RESTRICT"
            ),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "owner_id", sa.Integer(),
            sa.ForeignKey(
                "users.id", ondelete="RESTRICT"
            ),
            nullable=False,
        ),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False
        ),
        sa.Column(
            "max_price_cents", sa.Integer(), nullable=False
        ),
        sa.Column(
            "max_cost_cents", sa.Integer(), nullable=False
        ),
        sa.Column(
            "max_proposals_per_round",
            sa.Integer(), nullable=False,
        ),
        sa.Column(
            "version", sa.Integer(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("max_price_cents >= 0"),
        sa.CheckConstraint("max_cost_cents >= 0"),
        sa.CheckConstraint(
            "max_proposals_per_round BETWEEN 1 AND 5"
        ),
        sa.CheckConstraint("version >= 1"),
    )

    op.create_table(
        "world_agent_autonomy_policy_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "repliker_id", sa.Integer(),
            sa.ForeignKey(
                "replikers.id", ondelete="RESTRICT"
            ),
            nullable=False,
        ),
        sa.Column(
            "owner_id", sa.Integer(),
            sa.ForeignKey(
                "users.id", ondelete="RESTRICT"
            ),
            nullable=False,
        ),
        sa.Column(
            "version", sa.Integer(), nullable=False
        ),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False
        ),
        sa.Column(
            "max_price_cents", sa.Integer(), nullable=False
        ),
        sa.Column(
            "max_cost_cents", sa.Integer(), nullable=False
        ),
        sa.Column(
            "max_proposals_per_round",
            sa.Integer(), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.UniqueConstraint("repliker_id", "version"),
    )

    op.create_index(
        "ix_world_policy_events_actor",
        "world_agent_autonomy_policy_events",
        ["repliker_id", "version"],
    )


def downgrade():
    connection = op.get_bind()

    for table in (
        "world_agent_autonomy_policy_events",
        "world_agent_autonomy_policies",
    ):
        count = connection.execute(
            sa.text("SELECT COUNT(*) FROM " + table)
        ).scalar_one()

        if count:
            raise RuntimeError(
                "No eliminar politicas de autonomia existentes."
            )

    op.drop_index(
        "ix_world_policy_events_actor",
        table_name="world_agent_autonomy_policy_events",
    )
    op.drop_table("world_agent_autonomy_policy_events")
    op.drop_table("world_agent_autonomy_policies")
