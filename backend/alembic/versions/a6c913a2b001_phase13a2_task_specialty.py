"""phase13a2 task specialty

Revision ID: a6c913a2b001
Revises: 9f2c6a7e4d10
Create Date: 2026-10-03
"""

from typing import (
    Sequence,
    Union,
)

from alembic import op
import sqlalchemy as sa


revision: str = "a6c913a2b001"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "9f2c6a7e4d10"

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
    with op.batch_alter_table(
        "tasks",
        schema=None,
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "required_specialty",
                sa.String(length=120),
                nullable=False,
                server_default="Generalist",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table(
        "tasks",
        schema=None,
    ) as batch_op:
        batch_op.drop_column(
            "required_specialty"
        )
