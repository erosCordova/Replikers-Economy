
"""Orquestador de pruebas economicas en simulacion aislada.

No apto para aprobar automaticamente entregas reales.
No inicia supervisores ni efectua pagos externos.
"""

import hashlib
import os
from pathlib import Path

from sqlalchemy import text

from app.agentic.world_event_runtime import run_logged_governed_round
from app.services.world_contract_service import (
    open_contract,
    submit_delivery,
    review_delivery,
)
from app.services.world_settlement_service import settle_approved_contract


class SimulatedCycleError(RuntimeError):
    pass


def _require_isolated_simulation(db):
    checks = (
        os.getenv("ECONOMY_MODE") == "simulation",
        os.getenv("REAL_PAYMENTS_ENABLED", "").lower() == "false",
        os.getenv("AUTO_ENABLED", "").lower() == "false",
        os.getenv("RW_SUPERVISOR_BIND", "0") == "0",
        not os.getenv("GOOGLE_API_KEY"),
        not os.getenv("GEMINI_API_KEY"),
    )

    if not all(checks):
        raise SimulatedCycleError("Entorno de simulacion inseguro")

    database = db.get_bind().url

    if database.get_backend_name() != "sqlite":
        raise SimulatedCycleError("Solo se permite SQLite")

    path = Path(database.database).resolve()
    expected = os.getenv("REPLIKERS_WORLD_TEST_DB")

    if not expected or path != Path(expected).resolve():
        raise SimulatedCycleError("Base de datos no autorizada")

    if (
        path.parent.name != "replikers-world-backups"
        or not path.name.startswith("rw_economic_")
    ):
        raise SimulatedCycleError("Copia de ensayo requerida")


def run_simulated_owner_cycle(
    db,
    *,
    owner_id,
    idea_engine,
    response_engine,
):
    """Negocia, contrata y liquida una entrega ficticia verificable."""

    _require_isolated_simulation(db)

    if type(owner_id) is not int or owner_id <= 0:
        raise SimulatedCycleError("Propietario invalido")

    before_id = db.execute(
        text("SELECT COALESCE(MAX(id), 0) FROM world_negotiations")
    ).scalar_one()

    round_result = run_logged_governed_round(
        db,
        round_id="world_economic_" + os.urandom(12).hex(),
        idea_engine=idea_engine,
        response_engine=response_engine,
        max_agents=1,
        initiator_owner_id=owner_id,
    )

    accepted = [
        item for item in round_result.get("results", [])
        if isinstance(item, dict)
        and item.get("status") == "accepted"
    ]

    if len(accepted) != 1:
        raise SimulatedCycleError(
            "La negociacion no produjo una unica aceptacion"
        )

    negotiations = db.execute(
        text("""
            SELECT
                n.id,
                n.proposer_repliker_id,
                n.target_repliker_id,
                n.price_cents,
                seller.owner_id
            FROM world_negotiations n
            JOIN replikers seller
                ON seller.id = n.proposer_repliker_id
            WHERE n.id > :previous
              AND n.status = 'accepted'
            ORDER BY n.id
        """),
        {"previous": before_id},
    ).all()

    if len(negotiations) != 1:
        raise SimulatedCycleError(
            "Cantidad inesperada de acuerdos aceptados"
        )

    negotiation_id, seller, buyer, price, actual_owner = (
        negotiations[0]
    )

    if (
        int(actual_owner) != owner_id
        or seller == buyer
        or int(price) <= 0
        or int(accepted[0].get("repliker_id", -1)) != seller
    ):
        raise SimulatedCycleError(
            "La negociacion incumple el aislamiento"
        )

    # Contrato basado en el acuerdo aceptado.
    open_contract(
        db,
        negotiation_id=negotiation_id,
        acting_repliker_id=seller,
    )
    db.commit()

    contract_id = db.execute(
        text("""
            SELECT id
            FROM world_contracts
            WHERE negotiation_id = :negotiation
        """),
        {"negotiation": negotiation_id},
    ).scalar_one()

    # Artefacto FICTICIO y determinista, solo para pruebas.
    payload = (
        f"REPLIKERS WORLD | SIMULACION | "
        f"CONTRATO {contract_id} | "
        f"NEGOCIACION {negotiation_id}"
    ).encode("utf-8")

    reference = (
        "artifact:sha256:"
        + hashlib.sha256(payload).hexdigest()
    )

    submit_delivery(
        db,
        contract_id=contract_id,
        acting_repliker_id=seller,
        reference=reference,
    )
    db.commit()

    # Esta aprobacion automatica esta permitida solo
    # en la simulacion aislada; no es prueba de servicio real.
    review_delivery(
        db,
        contract_id=contract_id,
        acting_repliker_id=buyer,
        decision="approve",
        note="Aprobacion automatica de entrega FICTICIA",
    )
    db.commit()

    def reader(actual):
        if actual != reference:
            raise SimulatedCycleError(
                "Referencia SHA256 no reconocida"
            )
        return payload

    paid = settle_approved_contract(
        db,
        contract_id=contract_id,
        trusted_artifact_reader=reader,
    )
    db.commit()

    if (
        paid.get("status") != "settled"
        or paid.get("currency") != "RCR"
        or paid.get("repeated") is not False
        or int(paid.get("amount_cents", -1)) != int(price)
        or paid.get("transaction_id") is None
    ):
        raise SimulatedCycleError(
            "Liquidacion economica inconsistente"
        )

    def reject_second_read(_):
        raise SimulatedCycleError(
            "La liquidacion repetida intento releer el artefacto"
        )

    repeated = settle_approved_contract(
        db,
        contract_id=contract_id,
        trusted_artifact_reader=reject_second_read,
    )
    db.commit()

    if (
        repeated.get("repeated") is not True
        or repeated.get("transaction_id")
        != paid["transaction_id"]
    ):
        raise SimulatedCycleError("Se detecto riesgo de doble pago")

    return {
        "status": "settled",
        "simulation": True,
        "owner_id": owner_id,
        "seller_id": seller,
        "buyer_id": buyer,
        "negotiation_id": negotiation_id,
        "contract_id": contract_id,
        "transaction_id": paid["transaction_id"],
        "amount_cents": paid["amount_cents"],
        "currency": paid["currency"],
        "duplicate_payment": False,
    }
