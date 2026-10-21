
"""Ejecucion de negociaciones World con politicas reales.

Integra:
- Titularidad de Replikers y usuarios activos.
- Autonomia activada individualmente.
- Limites de precio y costo estimado.
- Decision de aceptacion de la contraparte.
- Estrategias sociales originales o combinadas.
- Memoria persistente de negociaciones.

Este ejecutor NO ejecuta transferencias ni liquida
contratos. Sus comprobaciones no reemplazan futuros
controles transaccionales de gasto.

Importante: los otros motores World siguen existiendo.
Solo las rondas llamadas mediante esta funcion quedan
protegidas por estas comprobaciones.
"""

import re
from collections.abc import Callable, Mapping
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.repliker import Repliker

from app.services.economy_service import (
    ensure_simulation_mode,
)

from app.services.world_autonomy_policy import (
    AutonomyPolicyError,
    AutonomyPolicyDenied,
    check_proposal,
    get_policy,
)

from app.agentic.world_social_learning import (
    run_social_round,
)

from app.agentic.world_memory_runtime import (
    record_negotiation_memories,
)


class WorldGovernanceError(ValueError):
    pass


class WorldGovernanceDenied(WorldGovernanceError):
    pass


def _active_policy(
    db: Session,
    repliker_id: int,
) -> tuple[int, dict]:
    """Verificar agente y propietario sin cargar proyectos."""

    if type(repliker_id) is not int or repliker_id <= 0:
        raise WorldGovernanceDenied(
            "Identidad de agente invalida."
        )

    agent = db.get(Repliker, repliker_id)

    if agent is None or not agent.is_active:
        raise WorldGovernanceDenied(
            "Repliker inexistente o inactivo."
        )

    owner_id = agent.owner_id

    if type(owner_id) is not int or owner_id <= 0:
        raise WorldGovernanceDenied(
            "El agente no tiene propietario valido."
        )

    owner_active = db.execute(
        select(User.is_active)
        .where(User.id == owner_id)
    ).scalar_one_or_none()

    if owner_active is not True:
        raise WorldGovernanceDenied(
            "Propietario inexistente o inactivo."
        )

    try:
        policy = get_policy(
            db,
            owner_id=owner_id,
            repliker_id=repliker_id,
        )
    except (AutonomyPolicyError, AutonomyPolicyDenied) as exc:
        raise WorldGovernanceDenied(
            "No se pudo autorizar al agente."
        ) from exc

    if not policy["enabled"]:
        raise WorldGovernanceDenied(
            "Autonomia desactivada para el agente."
        )

    return owner_id, policy


def _memory_count(db: Session, negotiation_id: int) -> int:
    result = db.execute(
        text(
            "SELECT COUNT(*) FROM world_agent_memories "
            "WHERE negotiation_id = :negotiation_id"
        ),
        {"negotiation_id": negotiation_id},
    ).scalar_one()

    return int(result)


def run_governed_social_round(
    db: Session,
    *,
    round_id: str,
    idea_engine: Callable,
    response_engine: Callable,
    max_agents: int = 3,
    initiator_owner_id: int | None = None,
) -> list[dict[str, Any]]:
    """Ronda social con autorizacion comprobada por agente.

    Las propuestas desautorizadas se bloquean antes
    de crear una nueva negociacion.

    Solo se admite una propuesta por agente en cada
    invocacion, por debajo del limite configurado
    de una a cinco propuestas por ronda.

    Las negociaciones aceptadas y rechazadas guardan
    dos memorias: una por cada participante.
    """

    ensure_simulation_mode()

    if (
        not isinstance(round_id, str)
        or re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9:_-]{7,79}",
            round_id,
        ) is None
    ):
        raise WorldGovernanceError(
            "Identificador de ronda invalido."
        )

    if type(max_agents) is not int or not 1 <= max_agents <= 3:
        raise WorldGovernanceError(
            "Cantidad de agentes fuera de rango."
        )

    if not callable(idea_engine):
        raise WorldGovernanceError(
            "Motor de ideas invalido."
        )

    if not callable(response_engine):
        raise WorldGovernanceError(
            "Motor de respuestas invalido."
        )

    denied = {}
    authorized_versions = {}
    counterparty_denials = set()

    def guarded_idea(context):
        actor_id = context["repliker_id"]

        try:
            owner_id, policy = _active_policy(
                db, actor_id
            )
        except WorldGovernanceDenied as exc:
            denied[actor_id] = str(exc)
            raise

        authorized_versions[actor_id] = policy["version"]

        # Solo después de autorizar se permite
        # consumir recursos del modelo de ideas.
        proposal = idea_engine(context)

        try:
            if not isinstance(proposal, Mapping):
                raise WorldGovernanceDenied(
                    "La idea generada no es una propuesta."
                )

            forbidden_fields = {
                "owner_id",
                "user_id",
                "acting_repliker_id",
            }

            if forbidden_fields.intersection(proposal):
                raise WorldGovernanceDenied(
                    "La IA intento suministrar identidad "
                    "o permisos de propietario."
                )

            claimed_actor = proposal.get(
                "proposer_repliker_id"
            )

            if (
                claimed_actor is not None
                and claimed_actor != actor_id
            ):
                raise WorldGovernanceDenied(
                    "La propuesta suplanta a otro agente."
                )

            target_id = proposal.get(
                "target_repliker_id"
            )

            if (
                type(target_id) is not int
                or target_id == actor_id
            ):
                raise WorldGovernanceDenied(
                    "Contraparte invalida."
                )

            # No iniciar una negociacion con un
            # agente desactivado por su propietario.
            _active_policy(db, target_id)

            check_proposal(
                db,
                owner_id=owner_id,
                repliker_id=actor_id,
                price_cents=proposal.get("price_cents"),
                estimated_cost_cents=proposal.get(
                    "estimated_cost_cents"
                ),
            )

        except (
            WorldGovernanceDenied,
            AutonomyPolicyError,
            AutonomyPolicyDenied,
        ) as exc:
            denied[actor_id] = str(exc)
            raise WorldGovernanceDenied(
                "La propuesta fue bloqueada por "
                "la politica economica."
            ) from exc

        return dict(proposal)

    def guarded_response(context):
        buyer_id = context["acting_repliker_id"]

        try:
            _active_policy(db, buyer_id)

        except WorldGovernanceDenied:
            counterparty_denials.add(buyer_id)

            return {
                "decision": "reject",
                "message": (
                    "La contraparte no tiene "
                    "autonomia habilitada."
                ),
            }

        # Esta respuesta expresa voluntad negociadora.
        # No representa autorizacion de desembolso.
        return response_engine(context)

    results = run_social_round(
        db,
        round_id=round_id,
        idea_engine=guarded_idea,
        response_engine=guarded_response,
        max_agents=max_agents,
        **({'initiator_owner_id': initiator_owner_id} if initiator_owner_id is not None else {}),
    )

    if not isinstance(results, list):
        raise WorldGovernanceError(
            "El coordinador social devolvio "
            "un resultado inesperado."
        )

    for result in results:
        actor_id = result.get("repliker_id")
        status = result.get("status")
        negotiation_id = result.get("negotiation_id")

        result["governance_blocked"] = (
            actor_id in denied
        )

        result["governance_policy_version"] = (
            authorized_versions.get(actor_id)
        )

        result["governance_reason"] = (
            denied.get(actor_id)
        )

        result["settlement_executed"] = False
        result["real_money_used"] = False

        if status not in ("accepted", "rejected"):
            continue

        if type(negotiation_id) is not int:
            raise WorldGovernanceError(
                "Negociacion concluida sin "
                "identificador valido."
            )

        previous_memories = _memory_count(
            db, negotiation_id
        )

        if previous_memories == 0:
            record_negotiation_memories(
                db,
                negotiation_id=negotiation_id,
                round_id=round_id,
            )

            # Solo los recuerdos; nunca pagos.
            db.commit()

        elif previous_memories != 2:
            raise WorldGovernanceError(
                "La memoria previa es inconsistente."
            )

        final_memories = _memory_count(
            db, negotiation_id
        )

        if final_memories != 2:
            raise WorldGovernanceError(
                "No se registraron ambas memorias."
            )

        result["memories_recorded"] = 2

    return results
