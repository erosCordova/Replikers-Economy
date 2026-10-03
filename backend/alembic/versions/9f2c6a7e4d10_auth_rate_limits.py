"""auth rate limits

Revision ID: 9f2c6a7e4d10
Revises: 4c7a9e2d1f6b
Create Date: 2026-10-03
"""

from typing import (
    Sequence,
    Union,
)

from alembic import op
import sqlalchemy as sa


revision: str = (
    "9f2c6a7e4d10"
)

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "4c7a9e2d1f6b"

branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None

depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    op.create_table(
        "auth_rate_limits",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "action",
            sa.String(
                length=40
            ),
            nullable=False,
        ),
        sa.Column(
            "key_hash",
            sa.String(
                length=64
            ),
            nullable=False,
        ),
        sa.Column(
            "window_started_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=False,
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "blocked_until",
            sa.DateTime(
                timezone=True
            ),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(
                timezone=True
            ),
            server_default=
                sa.text(
                    "CURRENT_TIMESTAMP"
                ),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(
                timezone=True
            ),
            server_default=
                sa.text(
                    "CURRENT_TIMESTAMP"
                ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "id"
        ),
        sa.UniqueConstraint(
            "action",
            "key_hash",
            name=
                "uq_auth_rate_limit_action_key",
        ),
    )

    op.create_index(
        "ix_auth_rate_limits_id",
        "auth_rate_limits",
        [
            "id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_auth_rate_limits_action",
        "auth_rate_limits",
        [
            "action",
        ],
        unique=False,
    )

    op.create_index(
        "ix_auth_rate_limits_key_hash",
        "auth_rate_limits",
        [
            "key_hash",
        ],
        unique=False,
    )

    op.create_index(
        "ix_auth_rate_limits_blocked_until",
        "auth_rate_limits",
        [
            "blocked_until",
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auth_rate_limits_blocked_until",
        table_name="auth_rate_limits",
    )

    op.drop_index(
        "ix_auth_rate_limits_key_hash",
        table_name="auth_rate_limits",
    )

    op.drop_index(
        "ix_auth_rate_limits_action",
        table_name="auth_rate_limits",
    )

    op.drop_index(
        "ix_auth_rate_limits_id",
        table_name="auth_rate_limits",
    )

    op.drop_table(
        "auth_rate_limits"
    )
