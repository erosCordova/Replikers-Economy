"""auth refresh sessions

Revision ID: 4c7a9e2d1f6b
Revises: b1f30d7c9a42
Create Date: 2026-10-03
"""

from typing import (
    Sequence,
    Union,
)

from alembic import op
import sqlalchemy as sa


revision: str = (
    "4c7a9e2d1f6b"
)

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "b1f30d7c9a42"

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
        "auth_sessions",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "token_hash",
            sa.String(
                length=64
            ),
            nullable=False,
        ),
        sa.Column(
            "family_id",
            sa.String(
                length=32
            ),
            nullable=False,
        ),
        sa.Column(
            "rotated_from_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "replaced_by_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=False,
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
            "last_used_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=True,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            [
                "user_id",
            ],
            [
                "users.id",
            ],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            [
                "rotated_from_id",
            ],
            [
                "auth_sessions.id",
            ],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            [
                "replaced_by_id",
            ],
            [
                "auth_sessions.id",
            ],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "id"
        ),
    )

    op.create_index(
        "ix_auth_sessions_id",
        "auth_sessions",
        [
            "id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_auth_sessions_user_id",
        "auth_sessions",
        [
            "user_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_auth_sessions_token_hash",
        "auth_sessions",
        [
            "token_hash",
        ],
        unique=True,
    )

    op.create_index(
        "ix_auth_sessions_family_id",
        "auth_sessions",
        [
            "family_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_auth_sessions_rotated_from_id",
        "auth_sessions",
        [
            "rotated_from_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_auth_sessions_replaced_by_id",
        "auth_sessions",
        [
            "replaced_by_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_auth_sessions_expires_at",
        "auth_sessions",
        [
            "expires_at",
        ],
        unique=False,
    )

    op.create_index(
        "ix_auth_sessions_revoked_at",
        "auth_sessions",
        [
            "revoked_at",
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auth_sessions_revoked_at",
        table_name="auth_sessions",
    )

    op.drop_index(
        "ix_auth_sessions_expires_at",
        table_name="auth_sessions",
    )

    op.drop_index(
        "ix_auth_sessions_replaced_by_id",
        table_name="auth_sessions",
    )

    op.drop_index(
        "ix_auth_sessions_rotated_from_id",
        table_name="auth_sessions",
    )

    op.drop_index(
        "ix_auth_sessions_family_id",
        table_name="auth_sessions",
    )

    op.drop_index(
        "ix_auth_sessions_token_hash",
        table_name="auth_sessions",
    )

    op.drop_index(
        "ix_auth_sessions_user_id",
        table_name="auth_sessions",
    )

    op.drop_index(
        "ix_auth_sessions_id",
        table_name="auth_sessions",
    )

    op.drop_table(
        "auth_sessions"
    )
