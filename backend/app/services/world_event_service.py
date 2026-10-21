
"""Registro idempotente de eventos economicos simulados."""

import hashlib
import re

from sqlalchemy import (
    Column, DateTime, ForeignKey,
    Integer, MetaData, String, Table, func,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.orm import Session

from app.models.repliker import Repliker
from app.services.economy_service import ensure_simulation_mode


metadata = MetaData()

world_events = Table(
    "world_agent_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("event_key", String(64), nullable=False, unique=True),
    Column("round_id", String(80), nullable=False),
    Column(
        "repliker_id",
        Integer,
        ForeignKey("replikers.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "owner_id",
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("negotiation_id", Integer, nullable=True),
    Column("kind", String(24), nullable=False),
    Column("status", String(48), nullable=False),
    Column(
        "created_at",
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    ),
)


class WorldEventError(ValueError):
    pass


def record_round_events(
    db: Session,
    *,
    round_id: str,
    results: list[dict],
) -> int:
    """Guardar un evento por agente y ronda, sin pagos."""

    ensure_simulation_mode()

    if (
        not isinstance(round_id, str)
        or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9:_-]{7,79}",
            round_id,
        )
    ):
        raise WorldEventError(
            "Identificador de ronda invalido."
        )

    if not isinstance(results, list):
        raise WorldEventError(
            "Resultados invalidos."
        )

    dialect = db.get_bind().dialect.name

    if dialect not in ("sqlite", "postgresql"):
        raise WorldEventError(
            "Motor SQL sin insercion idempotente verificada."
        )

    inserted = 0
    seen = set()

    for item in results:
        if not isinstance(item, dict):
            raise WorldEventError(
                "Registro de resultado invalido."
            )

        actor_id = item.get("repliker_id")

        if (
            type(actor_id) is not int
            or actor_id <= 0
            or actor_id in seen
        ):
            raise WorldEventError(
                "Identidad duplicada o invalida."
            )

        seen.add(actor_id)

        actor = db.get(Repliker, actor_id)

        if (
            actor is None
            or type(actor.owner_id) is not int
        ):
            raise WorldEventError(
                "Propietario del agente no encontrado."
            )

        status = item.get("status")

        if (
            not isinstance(status, str)
            or not re.fullmatch(
                r"[a-z][a-z0-9_]{0,47}",
                status,
            )
        ):
            raise WorldEventError(
                "Estado de ronda invalido."
            )

        negotiation_id = item.get("negotiation_id")

        if (
            negotiation_id is not None
            and (
                type(negotiation_id) is not int
                or negotiation_id <= 0
            )
        ):
            raise WorldEventError(
                "Referencia de negociacion invalida."
            )

        if item.get("governance_blocked") is True:
            kind = "governance"
        elif status in (
            "accepted",
            "rejected",
            "already_recorded",
        ):
            kind = "negotiation"
        else:
            kind = "runtime"

        event_key = hashlib.sha256(
            f"{round_id}:{actor_id}".encode("utf-8")
        ).hexdigest()

        values = {
            "event_key": event_key,
            "round_id": round_id,
            "repliker_id": actor_id,
            "owner_id": actor.owner_id,
            "negotiation_id": negotiation_id,
            "kind": kind,
            "status": status,
        }

        if dialect == "sqlite":
            statement = sqlite_insert(world_events)
        else:
            statement = postgres_insert(world_events)

        statement = statement.values(
            **values
        ).on_conflict_do_nothing(
            index_elements=[world_events.c.event_key]
        )

        result = db.execute(statement)
        inserted += max(result.rowcount or 0, 0)

    return inserted
