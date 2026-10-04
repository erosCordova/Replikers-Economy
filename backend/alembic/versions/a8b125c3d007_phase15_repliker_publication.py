"""phase15 repliker publication

Revision ID: a8b125c3d007
Revises: f7a014b2c006
"""

from alembic import op
import sqlalchemy as sa


revision = "a8b125c3d007"
down_revision = "f7a014b2c006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "replikers",
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.add_column(
        "replikers",
        sa.Column(
            "is_published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.add_column(
        "replikers",
        sa.Column(
            "published_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_replikers_is_system",
        "replikers",
        ["is_system"],
        unique=False,
    )

    op.create_index(
        "ix_replikers_is_published",
        "replikers",
        ["is_published"],
        unique=False,
    )

    # Los Replikers previos pertenecientes a
    # usuarios pasan a borrador. Nada se publica
    # automáticamente en nombre de un usuario.
    op.execute(
        """
        UPDATE replikers
        SET
            is_system = FALSE,
            is_published = FALSE,
            published_at = NULL
        """
    )

    # Los 15 Replikers oficiales permanecen
    # publicados y quedan marcados como sistema.
    op.execute(
        """
        UPDATE replikers
        SET
            is_system = TRUE,
            is_published = TRUE,
            published_at = CURRENT_TIMESTAMP
        WHERE owner_id IN (
            SELECT id
            FROM users
            WHERE email = 'ecosystem@replikers.internal'
        )
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_replikers_is_published",
        table_name="replikers",
    )

    op.drop_index(
        "ix_replikers_is_system",
        table_name="replikers",
    )

    op.drop_column(
        "replikers",
        "published_at",
    )

    op.drop_column(
        "replikers",
        "is_published",
    )

    op.drop_column(
        "replikers",
        "is_system",
    )
