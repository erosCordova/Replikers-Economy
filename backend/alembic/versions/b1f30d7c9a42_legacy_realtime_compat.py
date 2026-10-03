"""legacy realtime compatibility

Revision ID: b1f30d7c9a42
Revises: 7940ce23d545
Create Date: 2026-10-03

Esta revision normaliza bases heredadas creadas antes de
Phase 11, cuando realtime_events aun no existia.

Una base nueva ya recibe realtime_events desde la baseline,
por lo que esta revision no realiza cambios en ese caso.
"""

from typing import (
    Sequence,
    Union,
)

from alembic import op
import sqlalchemy as sa


revision: str = (
    "b1f30d7c9a42"
)

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "7940ce23d545"

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


def realtime_table_exists() -> bool:
    bind = op.get_bind()

    inspector = sa.inspect(
        bind
    )

    return inspector.has_table(
        "realtime_events"
    )


def upgrade() -> None:
    if realtime_table_exists():
        return

    op.create_table(
        "realtime_events",

        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "project_id",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "task_id",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "repliker_id",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "kind",
            sa.String(
                length=30
            ),
            nullable=False,
        ),

        sa.Column(
            "event_type",
            sa.String(
                length=80
            ),
            nullable=False,
        ),

        sa.Column(
            "actor_type",
            sa.String(
                length=30
            ),
            nullable=False,
        ),

        sa.Column(
            "title",
            sa.String(
                length=180
            ),
            nullable=False,
        ),

        sa.Column(
            "payload_json",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(
                timezone=True
            ),
            server_default=
                sa.text(
                    "(CURRENT_TIMESTAMP)"
                ),
            nullable=False,
        ),

        sa.CheckConstraint(
            (
                "kind IN ("
                "'activity', "
                "'message', "
                "'workflow', "
                "'economy', "
                "'system'"
                ")"
            ),
            name=
                "ck_realtime_event_kind",
        ),

        sa.ForeignKeyConstraint(
            [
                "project_id",
            ],
            [
                "projects.id",
            ],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            [
                "repliker_id",
            ],
            [
                "replikers.id",
            ],
            ondelete="SET NULL",
        ),

        sa.ForeignKeyConstraint(
            [
                "task_id",
            ],
            [
                "tasks.id",
            ],
            ondelete="SET NULL",
        ),

        sa.PrimaryKeyConstraint(
            "id"
        ),
    )

    op.create_index(
        op.f(
            "ix_realtime_events_event_type"
        ),
        "realtime_events",
        [
            "event_type",
        ],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_realtime_events_id"
        ),
        "realtime_events",
        [
            "id",
        ],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_realtime_events_kind"
        ),
        "realtime_events",
        [
            "kind",
        ],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_realtime_events_project_id"
        ),
        "realtime_events",
        [
            "project_id",
        ],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_realtime_events_repliker_id"
        ),
        "realtime_events",
        [
            "repliker_id",
        ],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_realtime_events_task_id"
        ),
        "realtime_events",
        [
            "task_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_realtime_project_cursor",
        "realtime_events",
        [
            "project_id",
            "id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_realtime_repliker_cursor",
        "realtime_events",
        [
            "repliker_id",
            "id",
        ],
        unique=False,
    )


def downgrade() -> None:
    # Intencionalmente no-op.
    #
    # La revision anterior (baseline)
    # ya define realtime_events.
    # Eliminarla aqui dejaria la BD
    # incompatible con el esquema de
    # 7940ce23d545.
    pass
