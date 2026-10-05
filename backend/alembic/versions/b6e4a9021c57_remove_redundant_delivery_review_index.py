"""remove redundant delivery review index

Revision ID: b6e4a9021c57
Revises: f7a9c31d8e42
"""

from alembic import op


revision = "b6e4a9021c57"
down_revision = "f7a9c31d8e42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(
        "ix_project_delivery_snapshots_final_review_id",
        table_name="project_delivery_snapshots",
    )


def downgrade() -> None:
    op.create_index(
        "ix_project_delivery_snapshots_final_review_id",
        "project_delivery_snapshots",
        ["final_review_id"],
        unique=True,
    )
