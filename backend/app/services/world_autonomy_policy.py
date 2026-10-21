
"""Politicas de autonomia de Replikers World.

Configuracion y verificacion preliminar de propuestas.

NO autoriza cobros, pagos ni ejecucion economica.
El motor autonomo tendra que integrar estos controles
antes de aceptar decisiones de gasto.

El usuario autenticado nunca se obtiene de un campo
proporcionado por el cliente.
"""

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime,
    ForeignKey, Integer, MetaData, String, Table,
    UniqueConstraint, func, insert, select, update,
)
from sqlalchemy.orm import Session

from app.models.repliker import Repliker
from app.services.economy_service import ensure_simulation_mode


class AutonomyPolicyError(ValueError):
    pass


class AutonomyPolicyConflict(AutonomyPolicyError):
    pass


class AutonomyPolicyDenied(AutonomyPolicyError):
    pass


metadata = MetaData()

policies = Table(
    "world_agent_autonomy_policies",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "repliker_id", Integer,
        ForeignKey("replikers.id", ondelete="RESTRICT"),
        nullable=False, unique=True,
    ),
    Column(
        "owner_id", Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("enabled", Boolean, nullable=False),
    Column("max_price_cents", Integer, nullable=False),
    Column("max_cost_cents", Integer, nullable=False),
    Column("max_proposals_per_round", Integer, nullable=False),
    Column("version", Integer, nullable=False),
    Column(
        "updated_at", DateTime,
        server_default=func.current_timestamp(),
        nullable=False,
    ),
    CheckConstraint("max_price_cents >= 0"),
    CheckConstraint("max_cost_cents >= 0"),
    CheckConstraint(
        "max_proposals_per_round BETWEEN 1 AND 5"
    ),
    CheckConstraint("version >= 1"),
)

events = Table(
    "world_agent_autonomy_policy_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "repliker_id", Integer,
        ForeignKey("replikers.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "owner_id", Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("version", Integer, nullable=False),
    Column("enabled", Boolean, nullable=False),
    Column("max_price_cents", Integer, nullable=False),
    Column("max_cost_cents", Integer, nullable=False),
    Column("max_proposals_per_round", Integer, nullable=False),
    Column(
        "created_at", DateTime,
        server_default=func.current_timestamp(),
        nullable=False,
    ),
    UniqueConstraint("repliker_id", "version"),
)


def _actor(db: Session, owner_id: int, repliker_id: int):
    if (
        type(owner_id) is not int or owner_id <= 0
        or type(repliker_id) is not int or repliker_id <= 0
    ):
        raise AutonomyPolicyDenied(
            "Identificador no autorizado."
        )

    actor = db.get(Repliker, repliker_id)

    if (
        actor is None
        or actor.owner_id != owner_id
        or not actor.is_active
    ):
        raise AutonomyPolicyDenied(
            "Acceso al Repliker no autorizado."
        )

    return actor


def get_policy(
    db: Session,
    *,
    owner_id: int,
    repliker_id: int,
) -> dict:
    ensure_simulation_mode()
    _actor(db, owner_id, repliker_id)

    row = db.execute(
        select(policies).where(
            policies.c.repliker_id == repliker_id,
            policies.c.owner_id == owner_id,
        )
    ).mappings().first()

    if row is None:
        return {
            "repliker_id": repliker_id,
            "enabled": False,
            "max_price_cents": 0,
            "max_cost_cents": 0,
            "max_proposals_per_round": 1,
            "version": 0,
            "currency": "RCR",
            "planning_only": True,
        }

    return {
        "repliker_id": repliker_id,
        "enabled": bool(row["enabled"]),
        "max_price_cents": row["max_price_cents"],
        "max_cost_cents": row["max_cost_cents"],
        "max_proposals_per_round": (
            row["max_proposals_per_round"]
        ),
        "version": row["version"],
        "currency": "RCR",
        "planning_only": True,
    }


def update_policy(
    db: Session,
    *,
    owner_id: int,
    repliker_id: int,
    enabled: bool,
    max_price_cents: int,
    max_cost_cents: int,
    max_proposals_per_round: int,
    expected_version: int,
) -> dict:
    ensure_simulation_mode()
    _actor(db, owner_id, repliker_id)

    if type(enabled) is not bool:
        raise AutonomyPolicyError(
            "El estado debe ser booleano."
        )

    for name, value, low, high in (
        ("Precio", max_price_cents, 0, 100000),
        ("Costo", max_cost_cents, 0, 20000),
        ("Propuestas", max_proposals_per_round, 1, 5),
        ("Version", expected_version, 0, 1000000000),
    ):
        if (
            type(value) is not int
            or not low <= value <= high
        ):
            raise AutonomyPolicyError(
                name + " fuera del rango permitido."
            )

    if enabled and max_price_cents == 0:
        raise AutonomyPolicyError(
            "La autonomia activada necesita "
            "un limite de precio positivo."
        )

    if max_cost_cents > max_price_cents:
        raise AutonomyPolicyError(
            "El limite de costo no puede "
            "superar al de precio."
        )

    current = get_policy(
        db, owner_id=owner_id, repliker_id=repliker_id
    )

    if current["version"] != expected_version:
        raise AutonomyPolicyConflict(
            "La configuracion cambio. "
            "Consulta la version actual."
        )

    new_version = expected_version + 1

    values = {
        "enabled": enabled,
        "max_price_cents": max_price_cents,
        "max_cost_cents": max_cost_cents,
        "max_proposals_per_round": max_proposals_per_round,
        "version": new_version,
    }

    if expected_version == 0:
        db.execute(
            insert(policies).values(
                repliker_id=repliker_id,
                owner_id=owner_id,
                **values,
            )
        )
    else:
        result = db.execute(
            update(policies)
            .where(
                policies.c.repliker_id == repliker_id,
                policies.c.owner_id == owner_id,
                policies.c.version == expected_version,
            )
            .values(
                **values,
                updated_at=func.current_timestamp(),
            )
        )

        if result.rowcount != 1:
            raise AutonomyPolicyConflict(
                "Actualizacion simultanea detectada."
            )

    db.execute(
        insert(events).values(
            repliker_id=repliker_id,
            owner_id=owner_id,
            **values,
        )
    )

    return get_policy(
        db, owner_id=owner_id, repliker_id=repliker_id
    )


def check_proposal(
    db: Session,
    *,
    owner_id: int,
    repliker_id: int,
    price_cents: int,
    estimated_cost_cents: int,
) -> dict:
    """Valida una intencion; no realiza operaciones."""

    ensure_simulation_mode()

    if (
        type(price_cents) is not int
        or price_cents <= 0
        or type(estimated_cost_cents) is not int
        or estimated_cost_cents < 0
    ):
        raise AutonomyPolicyError(
            "Importes de propuesta invalidos."
        )

    policy = get_policy(
        db, owner_id=owner_id, repliker_id=repliker_id
    )

    if not policy["enabled"]:
        raise AutonomyPolicyDenied(
            "La autonomia esta desactivada."
        )

    if price_cents > policy["max_price_cents"]:
        raise AutonomyPolicyDenied(
            "Precio superior al limite permitido."
        )

    if estimated_cost_cents > policy["max_cost_cents"]:
        raise AutonomyPolicyDenied(
            "Costo superior al limite permitido."
        )

    if estimated_cost_cents > price_cents:
        raise AutonomyPolicyDenied(
            "Costo estimado superior al precio."
        )

    return {
        "allowed": True,
        "planning_only": True,
        "operation_executed": False,
        "repliker_id": repliker_id,
        "price_cents": price_cents,
        "estimated_cost_cents": estimated_cost_cents,
        "policy_version": policy["version"],
        "currency": "RCR",
    }


def policy_history(
    db: Session,
    *,
    owner_id: int,
    repliker_id: int,
    limit: int = 20,
) -> list[dict]:
    ensure_simulation_mode()
    _actor(db, owner_id, repliker_id)

    if type(limit) is not int or not 1 <= limit <= 50:
        raise AutonomyPolicyError(
            "Limite de historial invalido."
        )

    rows = db.execute(
        select(events)
        .where(
            events.c.repliker_id == repliker_id,
            events.c.owner_id == owner_id,
        )
        .order_by(events.c.version.desc())
        .limit(limit)
    ).mappings().all()

    return [
        {
            "version": row["version"],
            "enabled": bool(row["enabled"]),
            "max_price_cents": row["max_price_cents"],
            "max_cost_cents": row["max_cost_cents"],
            "max_proposals_per_round": (
                row["max_proposals_per_round"]
            ),
            "created_at": row["created_at"].isoformat(),
        }
        for row in rows
    ]
