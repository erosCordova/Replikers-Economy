
"""Coordinador economico multiagente de Replikers World.

Ejecuta una ronda donde cada Repliker:
1. Observa su entorno economico.
2. Solicita una idea a su motor de decision.
3. Valida su propuesta.
4. Contacta a la contraparte elegida.
5. Recibe una respuesta.
6. Registra la negociacion.

No ejecuta pagos ni contratos.
No asigna profesiones a los agentes.

Los motores de IA pueden ser modelos LangChain
o dobles de prueba. El servicio debe ejecutarse
en un proceso interno de confianza.
"""

import re
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agentic.world_idea_graph import (
    build_world_idea_graph,
)
from app.agentic.world_negotiation_graph import (
    build_world_negotiation_graph,
    negotiations,
)
from app.models.economy import LedgerAccount
from app.models.repliker import Repliker
from app.services.economy_service import (
    ensure_simulation_mode,
)


class WorldAutonomyError(ValueError):
    pass


def _validate_round_id(value: str) -> str:
    if (
        not isinstance(value, str)
        or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_-]{0,49}",
            value,
        )
    ):
        raise WorldAutonomyError(
            "Identificador de ronda invalido."
        )

    return value


def available_agents(
    db: Session,
    *,
    limit: int = 3,
    initiator_owner_id: int | None = None,
) -> list[int]:
    """Encontrar agentes activos con billetera RCR."""

    ensure_simulation_mode()

    if type(limit) is not int or not 1 <= limit <= 50:
        raise WorldAutonomyError(
            "El limite debe estar entre 1 y 50."
        )

    if initiator_owner_id is not None and (
        type(initiator_owner_id) is not int or initiator_owner_id <= 0
    ):
        raise WorldAutonomyError("Propietario iniciador invalido.")
    agents = db.scalars(
        select(Repliker.id)
        .join(
            LedgerAccount,
            LedgerAccount.repliker_id == Repliker.id,
        )
        .where(
            Repliker.is_active.is_(True),
            LedgerAccount.is_active.is_(True),
            LedgerAccount.kind == "repliker_available",
            LedgerAccount.currency == "RCR",
            *((Repliker.owner_id == initiator_owner_id,) if initiator_owner_id is not None else ()),
        )
        .distinct()
        .order_by(Repliker.id)
        .limit(limit)
    ).all()

    return list(agents)


def run_actor_cycle(
    db: Session,
    *,
    actor_id: int,
    round_id: str,
    idea_engine: Callable,
    response_engine: Callable,
) -> dict[str, Any]:
    """Ejecuta una iniciativa y negociacion.

    El llamante controla commit/rollback.
    """

    ensure_simulation_mode()
    _validate_round_id(round_id)

    if type(actor_id) is not int or actor_id <= 0:
        raise WorldAutonomyError(
            "Repliker invalido."
        )

    key = f"worldcycle-{round_id}-agent-{actor_id}"

    # No volver a consultar modelos para una
    # negociacion ya confirmada.
    previous = db.execute(
        select(
            negotiations.c.id,
            negotiations.c.status,
            negotiations.c.title,
            negotiations.c.target_repliker_id,
        ).where(
            negotiations.c.idempotency_key == key
        )
    ).first()

    if previous is not None:
        return {
            "repliker_id": actor_id,
            "status": "already_recorded",
            "previous_decision": previous.status,
            "negotiation_id": previous.id,
            "title": previous.title,
            "target_repliker_id":
                previous.target_repliker_id,
            "payment_executed": False,
            "contract_executed": False,
        }

    # Primer grafo: generar una iniciativa.
    idea_graph = build_world_idea_graph(
        db=db,
        idea_engine=idea_engine,
    )

    idea_result = idea_graph.invoke({
        "repliker_id": actor_id,
    })

    if idea_result.get("status") != "lista_para_negociar":
        return {
            "repliker_id": actor_id,
            "status": "idea_not_ready",
            "detail": idea_result.get("status"),
            "payment_executed": False,
            "contract_executed": False,
        }

    proposal = idea_result["validated_idea"]

    # La identidad del proponente siempre se
    # verifica en el backend.
    if proposal["proposer_repliker_id"] != actor_id:
        raise WorldAutonomyError(
            "La propuesta no pertenece al actor."
        )

    # Segundo grafo: solicitar una respuesta
    # a la contraparte propuesta.
    negotiation_graph = build_world_negotiation_graph(
        db=db,
        response_engine=response_engine,
    )

    negotiation_result = negotiation_graph.invoke({
        "idempotency_key": key,
        "proposal": proposal,
    })

    status = negotiation_result.get(
        "status",
        "unknown",
    )

    return {
        "repliker_id": actor_id,
        "status": status,
        "negotiation_id":
            negotiation_result.get("negotiation_id"),
        "title": proposal["title"],
        "target_repliker_id":
            proposal["target_repliker_id"],
        "price_cents":
            proposal["price_cents"],
        "payment_executed": False,
        "contract_executed": False,
    }


def run_world_round(
    db: Session,
    *,
    round_id: str,
    idea_engine: Callable,
    response_engine: Callable,
    max_agents: int = 3,
) -> list[dict[str, Any]]:
    """Ejecutar una ronda para varios Replikers.

    Cada negociacion confirmada se guarda antes
    de comenzar la siguiente. Ante un error,
    no se confirma la operacion fallida.
    """

    ensure_simulation_mode()
    _validate_round_id(round_id)

    if not callable(idea_engine):
        raise WorldAutonomyError(
            "Motor de ideas invalido."
        )

    if not callable(response_engine):
        raise WorldAutonomyError(
            "Motor de respuestas invalido."
        )

    agent_ids = available_agents(
        db,
        limit=max_agents,
    )

    results = []

    for actor_id in agent_ids:
        try:
            result = run_actor_cycle(
                db,
                actor_id=actor_id,
                round_id=round_id,
                idea_engine=idea_engine,
                response_engine=response_engine,
            )

            if result["status"] in (
                "accepted",
                "rejected",
            ):
                db.commit()
            else:
                # Los estados no confirmados no
                # deben dejar operaciones pendientes.
                db.rollback()

            results.append(result)

        except Exception:
            db.rollback()
            raise

    return results
