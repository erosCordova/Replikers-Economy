
"""Estrategias publicas y procedencia de ideas."""

from alembic import op
import sqlalchemy as sa

revision = "a91810c1d240"
down_revision = "f81710c1d239"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "world_public_strategies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "source_negotiation_id",
            sa.Integer(),
            sa.ForeignKey(
                "world_negotiations.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
            unique=True,
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
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("insight", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column(
            "quoted_price_cents",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "outcome IN ('accepted','rejected')",
            name="ck_world_strategy_outcome",
        ),
        sa.CheckConstraint(
            "quoted_price_cents > 0",
            name="ck_world_strategy_price",
        ),
    )

    op.create_table(
        "world_strategy_adoptions",
        sa.Column("id", sa.Integer(), primary_key=True),
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
            "repliker_id",
            sa.Integer(),
            sa.ForeignKey(
                "replikers.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "source_ids_json",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "origin",
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "origin IN ('original','adapted','combined')",
            name="ck_world_strategy_origin",
        ),
    )


def downgrade():
    connection = op.get_bind()

    for table in (
        "world_strategy_adoptions",
        "world_public_strategies",
    ):
        count = connection.execute(
            sa.text(
                f"SELECT COUNT(*) FROM {table}"
            )
        ).scalar_one()

        if count:
            raise RuntimeError(
                "Hay estrategias registradas. "
                "No se permite eliminarlas."
            )

    op.drop_table("world_strategy_adoptions")
    op.drop_table("world_public_strategies")
