"""phase14 repliker studio

Revision ID: e6f913a2b005
Revises: d5f913a2b004
"""

from alembic import op
import sqlalchemy as sa


revision = "e6f913a2b005"
down_revision = "d5f913a2b004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repliker_studio_profiles",
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
            "purpose",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "personality",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "communication_style",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "instructions",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "config_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
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
            "config_version >= 1",
            name=(
                "ck_repliker_studio_"
                "config_version"
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
                "uq_repliker_studio_profile"
            ),
        ),
    )

    op.create_index(
        op.f(
            "ix_repliker_studio_profiles_repliker_id"
        ),
        "repliker_studio_profiles",
        ["repliker_id"],
        unique=False,
    )

    op.create_table(
        "repliker_knowledge_items",
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
            "title",
            sa.String(length=160),
            nullable=False,
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "source_type",
            sa.String(length=40),
            nullable=False,
            server_default="manual",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
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
            "title",
            name=(
                "uq_repliker_knowledge_title"
            ),
        ),
    )

    op.create_index(
        op.f(
            "ix_repliker_knowledge_items_repliker_id"
        ),
        "repliker_knowledge_items",
        ["repliker_id"],
        unique=False,
    )

    op.create_table(
        "repliker_rules",
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
            "title",
            sa.String(length=160),
            nullable=False,
        ),
        sa.Column(
            "instruction",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default="50",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
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
            (
                "priority >= 0 "
                "AND priority <= 100"
            ),
            name=(
                "ck_repliker_rule_priority"
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
            "title",
            name=(
                "uq_repliker_rule_title"
            ),
        ),
    )

    op.create_index(
        op.f(
            "ix_repliker_rules_repliker_id"
        ),
        "repliker_rules",
        ["repliker_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f(
            "ix_repliker_rules_repliker_id"
        ),
        table_name="repliker_rules",
    )

    op.drop_table(
        "repliker_rules"
    )

    op.drop_index(
        op.f(
            "ix_repliker_knowledge_items_repliker_id"
        ),
        table_name="repliker_knowledge_items",
    )

    op.drop_table(
        "repliker_knowledge_items"
    )

    op.drop_index(
        op.f(
            "ix_repliker_studio_profiles_repliker_id"
        ),
        table_name="repliker_studio_profiles",
    )

    op.drop_table(
        "repliker_studio_profiles"
    )
