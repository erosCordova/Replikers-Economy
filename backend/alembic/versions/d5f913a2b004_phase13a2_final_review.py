"""phase13a2 final project review

Revision ID: d5f913a2b004
Revises: c4e813a2b003
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d5f913a2b004"

down_revision: str | None = (
    "c4e813a2b003"
)

branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_specialist_offer_one_accepted_per_requirement",
        "project_specialist_offers",
        ["requirement_id"],
        unique=True,
        sqlite_where=sa.text(
            "status = 'accepted'"
        ),
        postgresql_where=sa.text(
            "status = 'accepted'"
        ),
    )

    op.create_table(
        "project_final_reviews",
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
            "requirement_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "reviewer_repliker_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "attempt_number",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "score",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "summary",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "corrections_json",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "reasoning",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "attempt_number >= 1",
            name=(
                "ck_project_final_review_"
                "attempt_positive"
            ),
        ),
        sa.CheckConstraint(
            (
                "status IN ("
                "'pending', "
                "'running', "
                "'approved', "
                "'corrections_requested', "
                "'failed'"
                ")"
            ),
            name=(
                "ck_project_final_review_status"
            ),
        ),
        sa.CheckConstraint(
            (
                "score IS NULL "
                "OR (score >= 0 "
                "AND score <= 100)"
            ),
            name=(
                "ck_project_final_review_score"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            [
                "project_specialist_requirements.id"
            ],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_repliker_id"],
            ["replikers.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id"
        ),
        sa.UniqueConstraint(
            "project_id",
            "attempt_number",
            name=(
                "uq_project_final_review_attempt"
            ),
        ),
    )

    op.create_index(
        op.f(
            "ix_project_final_reviews_id"
        ),
        "project_final_reviews",
        ["id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_project_final_reviews_project_id"
        ),
        "project_final_reviews",
        ["project_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_project_final_reviews_requirement_id"
        ),
        "project_final_reviews",
        ["requirement_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_project_final_reviews_reviewer_repliker_id"
        ),
        "project_final_reviews",
        ["reviewer_repliker_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_project_final_reviews_status"
        ),
        "project_final_reviews",
        ["status"],
        unique=False,
    )


    op.create_table(
        "project_final_correction_runs",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "final_review_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "contract_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "repliker_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "instruction",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "execution_status",
            sa.String(length=30),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "qa_review_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "error_summary",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            (
                "status IN ("
                "'pending', "
                "'running', "
                "'qa_running', "
                "'completed', "
                "'failed'"
                ")"
            ),
            name=(
                "ck_project_final_correction_status"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["final_review_id"],
            ["project_final_reviews.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["task_contracts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["repliker_id"],
            ["replikers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["qa_review_id"],
            ["qa_reviews.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "id"
        ),
        sa.UniqueConstraint(
            "final_review_id",
            "task_id",
            name=(
                "uq_project_final_correction_"
                "review_task"
            ),
        ),
    )

    op.create_index(
        op.f(
            "ix_project_final_correction_runs_id"
        ),
        "project_final_correction_runs",
        ["id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_project_final_correction_runs_final_review_id"
        ),
        "project_final_correction_runs",
        ["final_review_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_project_final_correction_runs_project_id"
        ),
        "project_final_correction_runs",
        ["project_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_project_final_correction_runs_task_id"
        ),
        "project_final_correction_runs",
        ["task_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_project_final_correction_runs_contract_id"
        ),
        "project_final_correction_runs",
        ["contract_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_project_final_correction_runs_repliker_id"
        ),
        "project_final_correction_runs",
        ["repliker_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_project_final_correction_runs_qa_review_id"
        ),
        "project_final_correction_runs",
        ["qa_review_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_project_final_correction_runs_status"
        ),
        "project_final_correction_runs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_specialist_offer_one_accepted_per_requirement",
        table_name="project_specialist_offers",
    )

    op.drop_index(
        op.f(
            "ix_project_final_correction_runs_status"
        ),
        table_name=(
            "project_final_correction_runs"
        ),
    )

    op.drop_index(
        op.f(
            "ix_project_final_correction_runs_qa_review_id"
        ),
        table_name=(
            "project_final_correction_runs"
        ),
    )

    op.drop_index(
        op.f(
            "ix_project_final_correction_runs_repliker_id"
        ),
        table_name=(
            "project_final_correction_runs"
        ),
    )

    op.drop_index(
        op.f(
            "ix_project_final_correction_runs_contract_id"
        ),
        table_name=(
            "project_final_correction_runs"
        ),
    )

    op.drop_index(
        op.f(
            "ix_project_final_correction_runs_task_id"
        ),
        table_name=(
            "project_final_correction_runs"
        ),
    )

    op.drop_index(
        op.f(
            "ix_project_final_correction_runs_project_id"
        ),
        table_name=(
            "project_final_correction_runs"
        ),
    )

    op.drop_index(
        op.f(
            "ix_project_final_correction_runs_final_review_id"
        ),
        table_name=(
            "project_final_correction_runs"
        ),
    )

    op.drop_index(
        op.f(
            "ix_project_final_correction_runs_id"
        ),
        table_name=(
            "project_final_correction_runs"
        ),
    )

    op.drop_table(
        "project_final_correction_runs"
    )

    op.drop_index(
        op.f(
            "ix_project_final_reviews_status"
        ),
        table_name="project_final_reviews",
    )

    op.drop_index(
        op.f(
            "ix_project_final_reviews_reviewer_repliker_id"
        ),
        table_name="project_final_reviews",
    )

    op.drop_index(
        op.f(
            "ix_project_final_reviews_requirement_id"
        ),
        table_name="project_final_reviews",
    )

    op.drop_index(
        op.f(
            "ix_project_final_reviews_project_id"
        ),
        table_name="project_final_reviews",
    )

    op.drop_index(
        op.f(
            "ix_project_final_reviews_id"
        ),
        table_name="project_final_reviews",
    )

    op.drop_table(
        "project_final_reviews"
    )
