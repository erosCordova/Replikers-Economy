"""phase13a2 specialist requirements

Revision ID: f3a713a2b002
Revises: a6c913a2b001
"""

from alembic import op
import sqlalchemy as sa


revision = "f3a713a2b002"
down_revision = "a6c913a2b001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_specialist_requirements",
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
            "specialty",
            sa.String(
                length=120
            ),
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "is_mandatory",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "is_final_gate",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "coverage_status",
            sa.String(
                length=30
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "assigned_repliker_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=False,
            server_default=
                sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=False,
            server_default=
                sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            [
                "project_id"
            ],
            [
                "projects.id"
            ],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            [
                "assigned_repliker_id"
            ],
            [
                "replikers.id"
            ],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "id"
        ),
        sa.UniqueConstraint(
            "project_id",
            "specialty",
            name=(
                "uq_project_specialist_"
                "requirement"
            ),
        ),
    )

    op.create_index(
        op.f(
            "ix_project_specialist_"
            "requirements_id"
        ),
        "project_specialist_requirements",
        [
            "id"
        ],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_project_specialist_"
            "requirements_project_id"
        ),
        "project_specialist_requirements",
        [
            "project_id"
        ],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_project_specialist_"
            "requirements_assigned_"
            "repliker_id"
        ),
        "project_specialist_requirements",
        [
            "assigned_repliker_id"
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f(
            "ix_project_specialist_"
            "requirements_assigned_"
            "repliker_id"
        ),
        table_name=(
            "project_specialist_requirements"
        ),
    )

    op.drop_index(
        op.f(
            "ix_project_specialist_"
            "requirements_project_id"
        ),
        table_name=(
            "project_specialist_requirements"
        ),
    )

    op.drop_index(
        op.f(
            "ix_project_specialist_"
            "requirements_id"
        ),
        table_name=(
            "project_specialist_requirements"
        ),
    )

    op.drop_table(
        "project_specialist_requirements"
    )
