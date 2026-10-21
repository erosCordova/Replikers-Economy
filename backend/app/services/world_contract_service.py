
"""Contratos simulados de Replikers World.

Solo permite:
- Abrir contratos desde negociaciones aceptadas.
- Registrar una referencia de entrega.
- Registrar aprobacion o disputa del comprador.
- Consultar eventos y estados.

NO ejecuta pagos ni verifica externamente entregas.
El identificador de actor debe provenir de una capa
autenticada cuando se exponga este servicio mediante API.
"""

from typing import Any

from sqlalchemy import (
    Column, DateTime, Integer, MetaData, String,
    Table, Text, func, insert, select, update, text,
)
from sqlalchemy.orm import Session

from app.services.economy_service import (
    ensure_simulation_mode,
)


class ContractError(ValueError):
    pass


metadata = MetaData()

contracts = Table(
    "world_contracts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("negotiation_id", Integer, nullable=False),
    Column("seller_repliker_id", Integer, nullable=False),
    Column("buyer_repliker_id", Integer, nullable=False),
    Column("title", String(120), nullable=False),
    Column("description", Text, nullable=False),
    Column("currency", String(10), nullable=False),
    Column("price_cents", Integer, nullable=False),
    Column("estimated_cost_cents", Integer, nullable=False),
    Column("status", String(20), nullable=False),
    Column("delivery_reference", String(500)),
    Column("review_note", String(500)),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)

events = Table(
    "world_contract_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("contract_id", Integer, nullable=False),
    Column("actor_repliker_id", Integer, nullable=False),
    Column("event_type", String(20), nullable=False),
    Column("detail", String(500), nullable=False),
    Column("created_at", DateTime),
)


def _actor(value: Any) -> int:
    if type(value) is not int or value <= 0:
        raise ContractError(
            "Identificador de agente invalido."
        )
    return value


def get_contract(
    db: Session,
    contract_id: int,
) -> dict[str, Any]:
    ensure_simulation_mode()
    _actor(contract_id)

    row = db.execute(
        select(contracts).where(
            contracts.c.id == contract_id
        )
    ).mappings().first()

    if row is None:
        raise ContractError("Contrato no encontrado.")

    return dict(row)


def get_contract_events(
    db: Session,
    contract_id: int,
) -> list[dict[str, Any]]:
    get_contract(db, contract_id)

    rows = db.execute(
        select(events)
        .where(events.c.contract_id == contract_id)
        .order_by(events.c.id)
    ).mappings().all()

    return [dict(row) for row in rows]


def _event(
    db: Session,
    contract_id: int,
    actor_id: int,
    kind: str,
    detail: str,
) -> None:
    db.execute(
        insert(events).values(
            contract_id=contract_id,
            actor_repliker_id=actor_id,
            event_type=kind,
            detail=detail,
        )
    )


def open_contract(
    db: Session,
    *,
    negotiation_id: int,
    acting_repliker_id: int,
) -> dict[str, Any]:
    ensure_simulation_mode()

    _actor(negotiation_id)
    _actor(acting_repliker_id)

    negotiation = db.execute(
        text("""
            SELECT
                id,
                proposer_repliker_id,
                target_repliker_id,
                title,
                description,
                currency,
                price_cents,
                estimated_cost_cents,
                status
            FROM world_negotiations
            WHERE id = :id
        """),
        {"id": negotiation_id},
    ).mappings().first()

    if negotiation is None:
        raise ContractError(
            "Negociacion no encontrada."
        )

    if negotiation["status"] != "accepted":
        raise ContractError(
            "La negociacion no fue aceptada."
        )

    seller = negotiation["proposer_repliker_id"]

    if acting_repliker_id != seller:
        raise ContractError(
            "Solo el proponente puede abrir el contrato."
        )

    existing = db.execute(
        select(contracts.c.id).where(
            contracts.c.negotiation_id == negotiation_id
        )
    ).scalar_one_or_none()

    if existing is not None:
        return get_contract(db, existing)

    result = db.execute(
        insert(contracts).values(
            negotiation_id=negotiation_id,
            seller_repliker_id=seller,
            buyer_repliker_id=negotiation[
                "target_repliker_id"
            ],
            title=negotiation["title"],
            description=negotiation["description"],
            currency=negotiation["currency"],
            price_cents=negotiation["price_cents"],
            estimated_cost_cents=negotiation[
                "estimated_cost_cents"
            ],
            status="open",
        )
    )

    contract_id = result.inserted_primary_key[0]

    _event(
        db,
        contract_id,
        acting_repliker_id,
        "opened",
        "Contrato abierto desde negociacion aceptada.",
    )

    return get_contract(db, contract_id)


def submit_delivery(
    db: Session,
    *,
    contract_id: int,
    acting_repliker_id: int,
    reference: str,
) -> dict[str, Any]:
    ensure_simulation_mode()

    actor = _actor(acting_repliker_id)
    contract = get_contract(db, contract_id)

    if actor != contract["seller_repliker_id"]:
        raise ContractError(
            "Solo el vendedor declara la entrega."
        )

    if not isinstance(reference, str):
        raise ContractError(
            "Referencia de entrega invalida."
        )

    reference = reference.strip()

    if not 8 <= len(reference) <= 500:
        raise ContractError(
            "La referencia debe tener entre "
            "8 y 500 caracteres."
        )

    if contract["status"] == "submitted":
        if contract["delivery_reference"] == reference:
            return contract

        raise ContractError(
            "Ya existe otra entrega registrada."
        )

    if contract["status"] != "open":
        raise ContractError(
            "El contrato no admite nuevas entregas."
        )

    result = db.execute(
        update(contracts)
        .where(
            contracts.c.id == contract_id,
            contracts.c.status == "open",
        )
        .values(
            status="submitted",
            delivery_reference=reference,
            updated_at=func.current_timestamp(),
        )
    )

    if result.rowcount != 1:
        raise ContractError(
            "El estado cambio durante la operacion."
        )

    _event(
        db,
        contract_id,
        actor,
        "submitted",
        reference,
    )

    return get_contract(db, contract_id)


def review_delivery(
    db: Session,
    *,
    contract_id: int,
    acting_repliker_id: int,
    decision: str,
    note: str,
) -> dict[str, Any]:
    ensure_simulation_mode()

    actor = _actor(acting_repliker_id)
    contract = get_contract(db, contract_id)

    if actor != contract["buyer_repliker_id"]:
        raise ContractError(
            "Solo el comprador revisa la entrega."
        )

    if decision not in ("approve", "dispute"):
        raise ContractError(
            "La decision debe ser approve o dispute."
        )

    if not isinstance(note, str):
        raise ContractError(
            "Observacion invalida."
        )

    note = note.strip()

    if not 3 <= len(note) <= 500:
        raise ContractError(
            "La observacion debe tener entre "
            "3 y 500 caracteres."
        )

    new_status = (
        "approved"
        if decision == "approve"
        else "disputed"
    )

    if contract["status"] == new_status:
        if contract["review_note"] == note:
            return contract

        raise ContractError(
            "La revision ya fue registrada."
        )

    if contract["status"] != "submitted":
        raise ContractError(
            "La entrega no esta pendiente de revision."
        )

    result = db.execute(
        update(contracts)
        .where(
            contracts.c.id == contract_id,
            contracts.c.status == "submitted",
        )
        .values(
            status=new_status,
            review_note=note,
            updated_at=func.current_timestamp(),
        )
    )

    if result.rowcount != 1:
        raise ContractError(
            "El estado cambio durante la revision."
        )

    _event(
        db,
        contract_id,
        actor,
        new_status,
        note,
    )

    return get_contract(db, contract_id)
