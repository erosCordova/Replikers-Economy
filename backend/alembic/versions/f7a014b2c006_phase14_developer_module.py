"""phase14 developer module

Revision ID: f7a014b2c006
Revises: e6f913a2b005
"""

from alembic import op
import sqlalchemy as sa


revision = "f7a014b2c006"
down_revision = "e6f913a2b005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repliker_developer_modules",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "repliker_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "language",
            sa.String(length=30),
            nullable=False,
            server_default="python",
        ),
        sa.Column(
            "filename",
            sa.String(length=120),
            nullable=False,
            server_default=
                "repliker_extension.py",
        ),
        sa.Column(
            "entrypoint",
            sa.String(length=80),
            nullable=False,
            server_default="run",
        ),
        sa.Column(
            "source_code",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "checksum",
            sa.String(length=64),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "validated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "version >= 1",
            name=(
                "ck_repliker_developer_version"
            ),
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
            "repliker_id",
            name=(
                "uq_repliker_developer_module"
            ),
        ),
    )

    op.create_index(
        op.f(
            "ix_repliker_developer_modules_repliker_id"
        ),
        "repliker_developer_modules",
        ["repliker_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f(
            "ix_repliker_developer_modules_repliker_id"
        ),
        table_name=
            "repliker_developer_modules",
    )

    op.drop_table(
        "repliker_developer_modules"
    )
