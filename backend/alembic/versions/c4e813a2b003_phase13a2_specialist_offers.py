"""phase13a2 specialist offers

Revision ID: c4e813a2b003
Revises: f3a713a2b002
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c4e813a2b003"

down_revision: str | None = (
    "f3a713a2b002"
)

branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_specialist_offers",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "requirement_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "repliker_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "confidence_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "message",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "reasoning",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "responded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            [
                "project_specialist_requirements.id"
            ],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repliker_id"],
            ["replikers.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id"
        ),
        sa.UniqueConstraint(
            "requirement_id",
            "repliker_id",
            name=(
                "uq_specialist_offer_"
                "requirement_repliker"
            ),
        ),
    )

    op.create_index(
        op.f(
            "ix_project_specialist_offers_id"
        ),
        "project_specialist_offers",
        ["id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_project_specialist_offers_project_id"
        ),
        "project_specialist_offers",
        ["project_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_project_specialist_offers_requirement_id"
        ),
        "project_specialist_offers",
        ["requirement_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_project_specialist_offers_repliker_id"
        ),
        "project_specialist_offers",
        ["repliker_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f(
            "ix_project_specialist_offers_repliker_id"
        ),
        table_name=
            "project_specialist_offers",
    )

    op.drop_index(
        op.f(
            "ix_project_specialist_offers_requirement_id"
        ),
        table_name=
            "project_specialist_offers",
    )

    op.drop_index(
        op.f(
            "ix_project_specialist_offers_project_id"
        ),
        table_name=
            "project_specialist_offers",
    )

    op.drop_index(
        op.f(
            "ix_project_specialist_offers_id"
        ),
        table_name=
            "project_specialist_offers",
    )

    op.drop_table(
        "project_specialist_offers"
    )
