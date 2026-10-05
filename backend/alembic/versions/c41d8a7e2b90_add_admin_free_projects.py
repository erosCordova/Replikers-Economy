"""add admin free projects

Revision ID: c41d8a7e2b90
Revises: b6e4a9021c57
"""

from alembic import op
import sqlalchemy as sa


revision = "c41d8a7e2b90"
down_revision = "b6e4a9021c57"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "is_admin_free",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "projects",
        "is_admin_free",
    )
