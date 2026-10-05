"""persist durable artifact blobs

Revision ID: d4c8b0217f23
Revises: a8b125c3d007
"""

from alembic import op
import sqlalchemy as sa


revision = "d4c8b0217f23"
down_revision = "a8b125c3d007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_artifact_blobs",

        sa.Column(
            "artifact_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "content",
            sa.LargeBinary(),
            nullable=False,
        ),

        sa.Column(
            "size_bytes",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "sha256",
            sa.String(
                length=64
            ),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(
                timezone=True
            ),
            server_default=
                sa.func.now(),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(
                timezone=True
            ),
            server_default=
                sa.func.now(),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["execution_artifacts.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint(
            "artifact_id"
        ),
    )

    op.create_index(
        "ix_execution_artifact_blobs_sha256",
        "execution_artifact_blobs",
        ["sha256"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_execution_artifact_blobs_sha256",
        table_name=
            "execution_artifact_blobs",
    )

    op.drop_table(
        "execution_artifact_blobs"
    )
