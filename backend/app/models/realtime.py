from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.database.base import Base


REALTIME_EVENT_KINDS = (
    "activity",
    "message",
    "workflow",
    "economy",
    "system",
)


class RealtimeEvent(Base):
    """
    Outbox durable para eventos en tiempo real.

    Cada evento queda dentro de la misma
    transaccion que genero la actividad
    original.

    En 11B este outbox sera consumido por SSE.
    """

    __tablename__ = "realtime_events"

    __table_args__ = (
        CheckConstraint(
            (
                "kind IN ("
                "'activity', "
                "'message', "
                "'workflow', "
                "'economy', "
                "'system'"
                ")"
            ),
            name="ck_realtime_event_kind",
        ),
        Index(
            "ix_realtime_project_cursor",
            "project_id",
            "id",
        ),
        Index(
            "ix_realtime_repliker_cursor",
            "repliker_id",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    project_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    task_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "tasks.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    repliker_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "replikers.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    kind: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        index=True,
    )

    actor_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="system",
    )

    title: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
        default="",
    )

    payload_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
