
"""Evaluacion verificable de estrategias de Replikers World.

Compara estrategias originales, adaptadas y combinadas.

Separacion estricta entre:
- Negociaciones aceptadas.
- Contratos realmente liquidados.
- Cobros contractuales comprobados.
- Beneficio neto desconocido.

Los historiales son observacionales. No se infiere
causalidad ni se proclama un ganador economico.

Uso interno: el llamante debe aplicar autorizacion
antes de exponer datos a usuarios externos.
"""

from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.repliker import Repliker
from app.models.economy import (
    LedgerAccount,
    LedgerTransaction,
)

from app.agentic.world_negotiation_graph import negotiations
from app.agentic.world_social_learning import (
    adoptions,
    run_social_round,
)
from app.services.world_contract_service import contracts
from app.services.world_settlement_service import settlements
from app.services.economy_service import ensure_simulation_mode


class StrategyEvaluationError(ValueError):
    pass


ORIGINS = ("original", "adapted", "combined")


def get_strategy_comparison(
    db: Session,
    *,
    repliker_id: int | None = None,
) -> dict[str, Any]:
    """Comparar resultados respaldados por la base contable.

    Si se indica repliker_id, devuelve exclusivamente
    operaciones propuestas por ese Repliker.
    """

    ensure_simulation_mode()

    if repliker_id is not None:
        if type(repliker_id) is not int or repliker_id <= 0:
            raise StrategyEvaluationError(
                "Identificador de Repliker invalido."
            )

        if db.get(Repliker, repliker_id) is None:
            raise StrategyEvaluationError(
                "El Repliker no existe."
            )

    statement = (
        select(
            adoptions.c.id.label("adoption_id"),
            adoptions.c.origin,
            adoptions.c.repliker_id,
            negotiations.c.id.label("negotiation_id"),
            negotiations.c.status.label("negotiation_status"),
            negotiations.c.proposer_repliker_id,
            negotiations.c.target_repliker_id,
            negotiations.c.currency,
            negotiations.c.price_cents,
            contracts.c.id.label("contract_id"),
            contracts.c.status.label("contract_status"),
            settlements.c.ledger_transaction_id,
        )
        .select_from(adoptions)
        .join(
            negotiations,
            negotiations.c.id == adoptions.c.negotiation_id,
        )
        .outerjoin(
            contracts,
            contracts.c.negotiation_id == negotiations.c.id,
        )
        .outerjoin(
            settlements,
            settlements.c.contract_id == contracts.c.id,
        )
        .order_by(adoptions.c.id)
    )

    if repliker_id is not None:
        statement = statement.where(
            adoptions.c.repliker_id == repliker_id
        )

    rows = db.execute(statement).all()

    groups = {
        origin: {
            "origin": origin,
            "negotiations": 0,
            "accepted": 0,
            "rejected": 0,
            "approved_contracts": 0,
            "settled_contracts": 0,
            "verified_receipts_cents": 0,
            "acceptance_rate": None,
            "settlement_rate": None,
            "verified_net_profit_cents": None,
        }
        for origin in ORIGINS
    }

    for row in rows:
        origin = row.origin

        if origin not in groups:
            raise StrategyEvaluationError(
                "Procedencia de estrategia invalida."
            )

        if row.repliker_id != row.proposer_repliker_id:
            raise StrategyEvaluationError(
                "Una estrategia fue atribuida "
                "a otro proponente."
            )

        if row.currency != "RCR":
            raise StrategyEvaluationError(
                "Moneda de estrategia incompatible."
            )

        if row.negotiation_status not in (
            "accepted",
            "rejected",
        ):
            raise StrategyEvaluationError(
                "Resultado de negociacion invalido."
            )

        group = groups[origin]

        group["negotiations"] += 1
        group[row.negotiation_status] += 1

        if row.contract_status == "approved":
            group["approved_contracts"] += 1

        transaction_id = row.ledger_transaction_id

        if transaction_id is None:
            continue

        if row.negotiation_status != "accepted":
            raise StrategyEvaluationError(
                "Hay un pago asociado a una "
                "negociacion no aceptada."
            )

        if row.contract_status != "approved":
            raise StrategyEvaluationError(
                "El contrato liquidado no esta aprobado."
            )

        transaction = db.get(
            LedgerTransaction,
            transaction_id,
        )

        if transaction is None:
            raise StrategyEvaluationError(
                "No existe la transaccion contractual."
            )

        seller = db.scalar(
            select(LedgerAccount)
            .where(
                LedgerAccount.kind == "repliker_available",
                LedgerAccount.currency == "RCR",
                LedgerAccount.repliker_id
                == row.proposer_repliker_id,
            )
        )

        buyer = db.scalar(
            select(LedgerAccount)
            .where(
                LedgerAccount.kind == "repliker_available",
                LedgerAccount.currency == "RCR",
                LedgerAccount.repliker_id
                == row.target_repliker_id,
            )
        )

        valid_transfer = (
            seller is not None
            and buyer is not None
            and transaction.from_account_id == buyer.id
            and transaction.to_account_id == seller.id
            and transaction.currency == "RCR"
            and transaction.transaction_type
            == "world_agent_transfer"
            and transaction.amount_cents == row.price_cents
        )

        if not valid_transfer:
            raise StrategyEvaluationError(
                "La liquidacion no coincide con "
                "los participantes y el precio."
            )

        group["settled_contracts"] += 1
        group["verified_receipts_cents"] += (
            transaction.amount_cents
        )

    for group in groups.values():
        count = group["negotiations"]
        accepted = group["accepted"]

        if count:
            group["acceptance_rate"] = round(
                accepted / count,
                4,
            )

        if accepted:
            group["settlement_rate"] = round(
                group["settled_contracts"] / accepted,
                4,
            )

    unclassified_query = (
        select(func.count(negotiations.c.id))
        .select_from(negotiations)
        .outerjoin(
            adoptions,
            adoptions.c.negotiation_id == negotiations.c.id,
        )
        .where(adoptions.c.id.is_(None))
    )

    if repliker_id is not None:
        unclassified_query = unclassified_query.where(
            negotiations.c.proposer_repliker_id == repliker_id
        )

    unclassified = db.scalar(unclassified_query) or 0

    return {
        "scope": (
            "single_repliker"
            if repliker_id is not None
            else "all_replikers"
        ),
        "repliker_id": repliker_id,
        "currency": "RCR",
        "groups": groups,
        "negotiations_with_provenance": len(rows),
        "negotiations_without_provenance": unclassified,
        "economic_winner": None,
        "causal_comparison": False,
        "verified_net_profit_cents": None,
        "costs_verified": False,
        "interpretation": (
            "Estas estadisticas describen resultados "
            "observados y cobros contractuales. "
            "No demuestran que una estrategia "
            "cause mayores ganancias. "
            "Faltan costos ejecutados verificables "
            "y experimentos comparables."
        ),
    }


def run_strategy_evidence_round(
    db: Session,
    *,
    round_id: str,
    idea_engine: Callable,
    response_engine: Callable,
    max_agents: int = 3,
) -> list[dict[str, Any]]:
    """Ejecutar una ronda con estadisticas verificables.

    Cada motor recibe unicamente la comparacion
    particular del Repliker al que representa.

    Se reutilizan todas las validaciones del
    coordinador social y sus tablas de procedencia.
    """

    ensure_simulation_mode()

    if not callable(idea_engine):
        raise StrategyEvaluationError(
            "Motor de ideas invalido."
        )

    if not callable(response_engine):
        raise StrategyEvaluationError(
            "Motor de respuestas invalido."
        )

    def evidence_idea(context):
        actor = context["repliker_id"]

        enriched = {
            **context,
            "strategy_evidence": get_strategy_comparison(
                db,
                repliker_id=actor,
            ),
            "strategy_evidence_rule": (
                "Evidence is observational, not causal. "
                "Verified contract receipts are not "
                "net profit. Unverified costs must "
                "never be presented as facts."
            ),
        }

        return idea_engine(enriched)

    def evidence_response(context):
        actor = context["acting_repliker_id"]

        enriched = {
            **context,
            "strategy_evidence": get_strategy_comparison(
                db,
                repliker_id=actor,
            ),
        }

        return response_engine(enriched)

    return run_social_round(
        db,
        round_id=round_id,
        idea_engine=evidence_idea,
        response_engine=evidence_response,
        max_agents=max_agents,
    )
