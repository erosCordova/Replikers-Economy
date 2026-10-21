
"""Pruebas de contratos de Replikers World."""

import os
import sqlite3
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.agentic.world_negotiation_graph import (
    build_world_negotiation_graph,
)
from app.models.economy import LedgerTransaction
from app.services.world_contract_service import (
    ContractError,
    contracts,
    events,
    get_contract,
    get_contract_events,
    open_contract,
    submit_delivery,
    review_delivery,
)


@pytest.fixture
def db(tmp_path):
    source = Path(
        os.environ["REPLIKERS_WORLD_TEST_DB"]
    )
    destination = tmp_path / "contracts_test.db"

    with sqlite3.connect(
        source.resolve().as_uri() + "?mode=ro",
        uri=True,
    ) as original:
        with sqlite3.connect(str(destination)) as copy:
            original.backup(copy)

    engine = create_engine(
        URL.create(
            "sqlite+pysqlite",
            database=str(destination),
        )
    )

    @event.listens_for(engine, "connect")
    def fk(connection, record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    with Session(engine) as session:
        yield session
        session.rollback()

    engine.dispose()


def negotiation(db, accepted=True):
    graph = build_world_negotiation_graph(
        db=db,
        response_engine=lambda context: {
            "decision": (
                "accept" if accepted else "reject"
            ),
            "message": (
                "Acepto evaluar las condiciones."
                if accepted
                else "No acepto esta propuesta."
            ),
        },
    )

    result = graph.invoke({
        "idempotency_key":
            "contract-" + uuid.uuid4().hex,
        "proposal": {
            "proposer_repliker_id": 1,
            "target_repliker_id": 2,
            "title": "Servicio digital",
            "description":
                "Desarrollar un recurso digital de prueba.",
            "currency": "RCR",
            "price_cents": 5000,
            "estimated_cost_cents": 1000,
        },
    })

    assert result["status"] == (
        "accepted" if accepted else "rejected"
    )

    db.flush()
    return result["negotiation_id"]


def opened(db):
    neg_id = negotiation(db)
    return open_contract(
        db,
        negotiation_id=neg_id,
        acting_repliker_id=1,
    )


def submitted(db):
    contract = opened(db)
    return submit_delivery(
        db,
        contract_id=contract["id"],
        acting_repliker_id=1,
        reference="artifact:entrega-de-prueba-001",
    )


def test_01_open_accepted_negotiation(db):
    contract = opened(db)
    assert contract["status"] == "open"
    assert contract["price_cents"] == 5000


def test_02_rejected_negotiation_cannot_open(db):
    neg_id = negotiation(db, accepted=False)
    with pytest.raises(ContractError):
        open_contract(
            db,
            negotiation_id=neg_id,
            acting_repliker_id=1,
        )


def test_03_only_seller_can_open(db):
    neg_id = negotiation(db)
    with pytest.raises(ContractError):
        open_contract(
            db,
            negotiation_id=neg_id,
            acting_repliker_id=2,
        )


def test_04_contract_creation_is_idempotent(db):
    neg_id = negotiation(db)

    first = open_contract(
        db,
        negotiation_id=neg_id,
        acting_repliker_id=1,
    )
    second = open_contract(
        db,
        negotiation_id=neg_id,
        acting_repliker_id=1,
    )

    assert first["id"] == second["id"]
    assert len(get_contract_events(db, first["id"])) == 1


def test_05_seller_submits_delivery(db):
    contract = submitted(db)
    assert contract["status"] == "submitted"
    assert contract["delivery_reference"].startswith(
        "artifact:"
    )


def test_06_buyer_cannot_submit_delivery(db):
    contract = opened(db)

    with pytest.raises(ContractError):
        submit_delivery(
            db,
            contract_id=contract["id"],
            acting_repliker_id=2,
            reference="artifact:entrega-invalida",
        )


def test_07_invalid_reference_rejected(db):
    contract = opened(db)

    with pytest.raises(ContractError):
        submit_delivery(
            db,
            contract_id=contract["id"],
            acting_repliker_id=1,
            reference="abc",
        )


def test_08_buyer_approves_delivery(db):
    contract = submitted(db)

    approved = review_delivery(
        db,
        contract_id=contract["id"],
        acting_repliker_id=2,
        decision="approve",
        note="Acepto la entrega declarada.",
    )

    assert approved["status"] == "approved"


def test_09_cannot_approve_before_delivery(db):
    contract = opened(db)

    with pytest.raises(ContractError):
        review_delivery(
            db,
            contract_id=contract["id"],
            acting_repliker_id=2,
            decision="approve",
            note="Aceptacion prematura.",
        )


def test_10_seller_cannot_approve(db):
    contract = submitted(db)

    with pytest.raises(ContractError):
        review_delivery(
            db,
            contract_id=contract["id"],
            acting_repliker_id=1,
            decision="approve",
            note="Aprobacion no autorizada.",
        )


def test_11_buyer_can_dispute(db):
    contract = submitted(db)

    result = review_delivery(
        db,
        contract_id=contract["id"],
        acting_repliker_id=2,
        decision="dispute",
        note="El trabajo requiere revision.",
    )

    assert result["status"] == "disputed"


def test_12_cannot_modify_approved_contract(db):
    contract = submitted(db)

    review_delivery(
        db,
        contract_id=contract["id"],
        acting_repliker_id=2,
        decision="approve",
        note="Entrega aceptada.",
    )

    with pytest.raises(ContractError):
        submit_delivery(
            db,
            contract_id=contract["id"],
            acting_repliker_id=1,
            reference="artifact:segunda-entrega",
        )


def test_13_ledger_remains_unchanged(db):
    before = db.scalar(
        select(func.count(LedgerTransaction.id))
    )

    contract = submitted(db)

    review_delivery(
        db,
        contract_id=contract["id"],
        acting_repliker_id=2,
        decision="approve",
        note="Revision aprobada.",
    )

    after = db.scalar(
        select(func.count(LedgerTransaction.id))
    )

    assert before == after == 8


def test_14_contract_preserves_agreed_terms(db):
    contract = opened(db)

    assert contract["seller_repliker_id"] == 1
    assert contract["buyer_repliker_id"] == 2
    assert contract["currency"] == "RCR"
    assert contract["price_cents"] == 5000
    assert contract["estimated_cost_cents"] == 1000


def test_15_history_order(db):
    contract = submitted(db)

    review_delivery(
        db,
        contract_id=contract["id"],
        acting_repliker_id=2,
        decision="approve",
        note="Trabajo revisado.",
    )

    history = get_contract_events(db, contract["id"])

    assert [
        item["event_type"] for item in history
    ] == [
        "opened", "submitted", "approved"
    ]


def test_16_repeated_review_is_idempotent(db):
    contract = submitted(db)

    first = review_delivery(
        db,
        contract_id=contract["id"],
        acting_repliker_id=2,
        decision="approve",
        note="Entrega aprobada.",
    )

    second = review_delivery(
        db,
        contract_id=contract["id"],
        acting_repliker_id=2,
        decision="approve",
        note="Entrega aprobada.",
    )

    assert first["id"] == second["id"]
    assert len(get_contract_events(db, first["id"])) == 3
