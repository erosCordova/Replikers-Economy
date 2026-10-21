
"""Pruebas persistentes de negociacion entre Replikers."""

import os
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select, func
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.agentic.world_idea_graph import (
    build_world_idea_graph,
)
from app.agentic.world_negotiation_graph import (
    build_world_negotiation_graph,
    negotiations,
    events,
)
from app.models.economy import LedgerTransaction


@pytest.fixture
def db(tmp_path):
    source = Path(
        os.environ["REPLIKERS_WORLD_TEST_DB"]
    )
    destination = tmp_path / "negotiation_test.db"

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
    def enable_foreign_keys(connection, record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    with Session(engine) as session:
        yield session
        session.rollback()

    engine.dispose()


def proposal():
    return {
        "proposer_repliker_id": 1,
        "target_repliker_id": 2,
        "title": "Servicio digital personalizado",
        "description": (
            "Crear un recurso digital util para "
            "el otro Repliker dentro de la simulacion."
        ),
        "currency": "RCR",
        "price_cents": 5000,
        "estimated_cost_cents": 1000,
        "counterparty_accepted": False,
        "contract_executed": False,
        "payment_executed": False,
    }


def run(db, idea=None, reply=None, key="negotiation-0001"):
    if idea is None:
        idea = proposal()

    if reply is None:
        reply = {
            "decision": "accept",
            "message": "Me interesa evaluar esta propuesta.",
        }

    graph = build_world_negotiation_graph(
        db=db,
        response_engine=lambda context: reply,
    )

    return graph.invoke({
        "proposal": idea,
        "idempotency_key": key,
    })


def test_acceptance_is_recorded(db):
    result = run(db)
    db.commit()

    assert result["status"] == "accepted"
    assert result["payment_executed"] is False
    assert result["contract_executed"] is False

    rows = db.execute(select(negotiations)).all()
    assert len(rows) == 1

    history = db.execute(
        select(events.c.event_type)
        .order_by(events.c.id)
    ).scalars().all()

    assert history == ["proposal", "accept"]


def test_rejection_is_recorded(db):
    result = run(
        db,
        reply={
            "decision": "reject",
            "message": "No considero conveniente esta oferta.",
        },
    )
    db.commit()

    assert result["status"] == "rejected"

    history = db.execute(
        select(events.c.event_type)
        .order_by(events.c.id)
    ).scalars().all()

    assert history == ["proposal", "reject"]


def test_idempotency_prevents_duplicate(db):
    first = run(db)
    db.commit()

    calls = []

    def unexpected_response(context):
        calls.append(context)
        raise RuntimeError("No deberia volver a decidir")

    graph = build_world_negotiation_graph(
        db=db,
        response_engine=unexpected_response,
    )

    repeated = graph.invoke({
        "proposal": proposal(),
        "idempotency_key": "negotiation-0001",
    })

    assert first["status"] == "accepted"
    assert repeated["status"] == "already_recorded"
    assert repeated["negotiation_id"] == first["negotiation_id"]
    assert not calls

    count = db.scalar(
        select(func.count()).select_from(negotiations)
    )
    assert count == 1


def test_idempotency_conflict_is_rejected(db):
    run(db)
    db.commit()

    changed = proposal()
    changed["price_cents"] = 7000

    result = run(db, idea=changed)

    assert result["status"] == "key_conflict"


def test_self_negotiation_is_rejected(db):
    idea = proposal()
    idea["target_repliker_id"] = 1

    result = run(db, idea=idea)

    assert result["status"] == "self_negotiation"


def test_unknown_counterparty_is_rejected(db):
    idea = proposal()
    idea["target_repliker_id"] = 99999999

    result = run(db, idea=idea)

    assert result["status"] == "agent_unavailable"


def test_insufficient_buyer_funds(db):
    idea = proposal()
    idea["price_cents"] = 999999

    result = run(db, idea=idea)

    assert result["status"] == "insufficient_buyer_funds"


def test_insufficient_proposer_funds(db):
    idea = proposal()
    idea["price_cents"] = 9999999
    idea["estimated_cost_cents"] = 999999

    result = run(db, idea=idea)

    assert result["status"] == "insufficient_proposer_funds"


def test_invalid_response_does_not_persist(db):
    result = run(
        db,
        reply={
            "decision": "pay_immediately",
            "message": "Enviar todos los creditos.",
        },
    )

    assert result["status"] == "response_error"

    count = db.scalar(
        select(func.count()).select_from(negotiations)
    )
    assert count == 0


def test_model_cannot_create_contract(db):
    result = run(
        db,
        reply={
            "decision": "accept",
            "message": "Acepto conversar sobre la oferta.",
            "payment_executed": True,
            "contract_executed": True,
            "price_cents": 1,
        },
    )

    assert result["status"] == "accepted"
    assert result["payment_executed"] is False
    assert result["contract_executed"] is False

    saved_price = db.scalar(
        select(negotiations.c.price_cents)
    )

    assert saved_price == 5000


def test_negotiation_does_not_change_ledger(db):
    previous = db.scalar(
        select(func.count(LedgerTransaction.id))
    )

    run(db)
    db.commit()

    current = db.scalar(
        select(func.count(LedgerTransaction.id))
    )

    assert previous == 8
    assert current == previous


def test_idea_graph_connects_to_negotiation(db):
    idea_graph = build_world_idea_graph(
        db=db,
        idea_engine=lambda context: {
            "title": "Servicio digital personalizado",
            "description": (
                "Crear un recurso digital util para "
                "el otro Repliker dentro de la simulacion."
            ),
            "target_repliker_id": 2,
            "price_cents": 5000,
            "estimated_cost_cents": 1000,
        },
    )

    generated = idea_graph.invoke({
        "repliker_id": 1,
    })

    assert generated["status"] == "lista_para_negociar"

    negotiation = run(
        db,
        idea=generated["validated_idea"],
        key="negotiation-from-idea-0002",
    )

    db.commit()

    assert negotiation["status"] == "accepted"

    negotiation_id = negotiation["negotiation_id"]

    recorded_events = db.execute(
        select(events.c.event_type)
        .where(events.c.negotiation_id == negotiation_id)
        .order_by(events.c.id)
    ).scalars().all()

    assert recorded_events == [
        "proposal",
        "accept",
    ]
