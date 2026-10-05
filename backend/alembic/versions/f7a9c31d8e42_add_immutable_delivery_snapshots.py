"""add immutable delivery snapshots

Revision ID: f7a9c31d8e42
Revises: d4c8b0217f23
"""

from alembic import op
import sqlalchemy as sa


revision = "f7a9c31d8e42"
down_revision = "d4c8b0217f23"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_delivery_snapshots",

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
            "final_review_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "review_attempt",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "version_label",
            sa.String(length=30),
            nullable=False,
        ),

        sa.Column(
            "files_count",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "total_size_bytes",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "package_sha256",
            sa.String(length=64),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["final_review_id"],
            ["project_final_reviews.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint(
            "id"
        ),

        sa.UniqueConstraint(
            "final_review_id"
        ),

        sa.UniqueConstraint(
            "project_id",
            "version_label",
            name=(
                "uq_project_delivery_"
                "snapshot_version"
            ),
        ),
    )

    op.create_index(
        "ix_project_delivery_snapshots_id",
        "project_delivery_snapshots",
        ["id"],
        unique=False,
    )

    op.create_index(
        "ix_project_delivery_snapshots_project_id",
        "project_delivery_snapshots",
        ["project_id"],
        unique=False,
    )

    op.create_index(
        "ix_project_delivery_snapshots_final_review_id",
        "project_delivery_snapshots",
        ["final_review_id"],
        unique=True,
    )

    op.create_table(
        "project_delivery_snapshot_files",

        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "snapshot_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "artifact_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "workspace_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "task_id",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "relative_path",
            sa.String(length=1000),
            nullable=False,
        ),

        sa.Column(
            "archive_path",
            sa.String(length=1200),
            nullable=False,
        ),

        sa.Column(
            "media_type",
            sa.String(length=150),
            nullable=False,
        ),

        sa.Column(
            "size_bytes",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "sha256",
            sa.String(length=64),
            nullable=False,
        ),

        sa.Column(
            "content",
            sa.LargeBinary(),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["project_delivery_snapshots.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint(
            "id"
        ),

        sa.UniqueConstraint(
            "snapshot_id",
            "archive_path",
            name=(
                "uq_project_delivery_"
                "snapshot_file_path"
            ),
        ),
    )

    op.create_index(
        "ix_project_delivery_snapshot_files_id",
        "project_delivery_snapshot_files",
        ["id"],
        unique=False,
    )

    op.create_index(
        "ix_project_delivery_snapshot_files_snapshot_id",
        "project_delivery_snapshot_files",
        ["snapshot_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_project_delivery_snapshot_files_snapshot_id",
        table_name=
            "project_delivery_snapshot_files",
    )

    op.drop_index(
        "ix_project_delivery_snapshot_files_id",
        table_name=
            "project_delivery_snapshot_files",
    )

    op.drop_table(
        "project_delivery_snapshot_files"
    )

    op.drop_index(
        "ix_project_delivery_snapshots_final_review_id",
        table_name=
            "project_delivery_snapshots",
    )

    op.drop_index(
        "ix_project_delivery_snapshots_project_id",
        table_name=
            "project_delivery_snapshots",
    )

    op.drop_index(
        "ix_project_delivery_snapshots_id",
        table_name=
            "project_delivery_snapshots",
    )

    op.drop_table(
        "project_delivery_snapshots"
    )
