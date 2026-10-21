
"""Pruebas del primer ciclo multiagente."""

import os
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import (
    create_engine,
    event,
    func,
    select,
)
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.agentic.world_autonomy_runtime import (
    WorldAutonomyError,
    available_agents,
    run_actor_cycle,
    run_world_round,
)
from app.agentic.world_negotiation_graph import (
    negotiations,
    events,
)
from app.models.economy import LedgerTransaction


@pytest.fixture
def db(tmp_path):
    source = Path(
        os.environ["REPLIKERS_WORLD_TEST_DB"]
    )
    target = tmp_path / "autonomy.db"

    with sqlite3.connect(
        source.resolve().as_uri() + "?mode=ro",
        uri=True,
    ) as origin:
        with sqlite3.connect(str(target)) as dest:
            origin.backup(dest)

    engine = create_engine(
        URL.create(
            "sqlite+pysqlite",
            database=str(target),
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


def generate_idea(context):
    peers = context["potential_counterparties"]

    buyer = next(
        peer for peer in peers
        if peer["balance_cents"] >= 3000
    )

    return {
        "title": "Servicio autonomo de investigacion",
        "description": (
            "Crear un informe digital de oportunidades "
            "comerciales para otro Repliker."
        ),
        "target_repliker_id": buyer["repliker_id"],
        "price_cents": 3000,
        "estimated_cost_cents": 500,
    }


def accept_offer(context):
    return {
        "decision": "accept",
        "message": (
            "Acepto negociar las condiciones "
            "del servicio propuesto."
        ),
    }


def reject_offer(context):
    return {
        "decision": "reject",
        "message": (
            "La propuesta no encaja con "
            "mis prioridades actuales."
        ),
    }


def run(db, round_id="ronda001", responder=accept_offer):
    return run_world_round(
        db,
        round_id=round_id,
        idea_engine=generate_idea,
        response_engine=responder,
    )


def count_rows(db, table):
    return db.scalar(
        select(func.count()).select_from(table)
    )


def test_01_finds_three_agents(db):
    assert len(available_agents(db)) == 3


def test_02_three_agents_initiate_business(db):
    results = run(db)

    assert len(results) == 3
    assert all(
        item["status"] == "accepted"
        for item in results
    )


def test_03_negotiations_are_persisted(db):
    run(db)

    assert count_rows(db, negotiations) == 3


def test_04_conversation_events_are_persisted(db):
    run(db)

    assert count_rows(db, events) == 6


def test_05_does_not_execute_payments(db):
    before = db.scalar(
        select(func.count(LedgerTransaction.id))
    )

    results = run(db)

    after = db.scalar(
        select(func.count(LedgerTransaction.id))
    )

    assert before == after == 8
    assert all(
        item["payment_executed"] is False
        for item in results
    )


def test_06_does_not_execute_contracts(db):
    results = run(db)

    assert all(
        item["contract_executed"] is False
        for item in results
    )


def test_07_idempotent_round(db):
    first = run(db, round_id="repeticion001")
    second = run(db, round_id="repeticion001")

    assert len(first) == len(second) == 3

    assert all(
        item["status"] == "already_recorded"
        for item in second
    )

    assert count_rows(db, negotiations) == 3


def test_08_repeated_round_does_not_call_ai(db):
    run(db, round_id="sinreconsulta001")

    def forbidden_engine(context):
        raise RuntimeError(
            "No debe repetirse la llamada."
        )

    results = run_world_round(
        db,
        round_id="sinreconsulta001",
        idea_engine=forbidden_engine,
        response_engine=forbidden_engine,
    )

    assert all(
        item["status"] == "already_recorded"
        for item in results
    )


def test_09_agents_can_reject(db):
    results = run(
        db,
        round_id="rechazo001",
        responder=reject_offer,
    )

    assert all(
        item["status"] == "rejected"
        for item in results
    )

    assert count_rows(db, negotiations) == 3


def test_10_idea_engine_failure_is_safe(db):
    def broken(context):
        raise RuntimeError("Modelo no disponible")

    results = run_world_round(
        db,
        round_id="errorideas001",
        idea_engine=broken,
        response_engine=accept_offer,
    )

    assert all(
        item["status"] == "idea_not_ready"
        for item in results
    )
    assert count_rows(db, negotiations) == 0


def test_11_invalid_counterparty_is_rejected(db):
    def invalid_idea(context):
        result = generate_idea(context)
        result["target_repliker_id"] = 999999
        return result

    results = run_world_round(
        db,
        round_id="invalida001",
        idea_engine=invalid_idea,
        response_engine=accept_offer,
    )

    assert all(
        item["status"] == "idea_not_ready"
        for item in results
    )

    assert count_rows(db, negotiations) == 0


def test_12_self_negotiation_is_rejected(db):
    def self_idea(context):
        result = generate_idea(context)
        result["target_repliker_id"] = context["repliker_id"]
        return result

    results = run_world_round(
        db,
        round_id="autocompra001",
        idea_engine=self_idea,
        response_engine=accept_offer,
    )

    assert all(
        item["status"] == "idea_not_ready"
        for item in results
    )


def test_13_buyer_engine_failure_is_safe(db):
    def broken(context):
        raise RuntimeError("Sin respuesta")

    results = run_world_round(
        db,
        round_id="errorrespuesta001",
        idea_engine=generate_idea,
        response_engine=broken,
    )

    assert all(
        item["status"] == "response_error"
        for item in results
    )

    assert count_rows(db, negotiations) == 0


def test_14_limits_agent_count(db):
    results = run_world_round(
        db,
        round_id="limite001",
        idea_engine=generate_idea,
        response_engine=accept_offer,
        max_agents=2,
    )

    assert len(results) == 2


def test_15_invalid_round_id_is_rejected(db):
    with pytest.raises(WorldAutonomyError):
        run_world_round(
            db,
            round_id="../../otra-base",
            idea_engine=generate_idea,
            response_engine=accept_offer,
        )


def test_16_ai_receives_context_not_profession(db):
    contexts = []

    def observer(context):
        contexts.append(context)
        return generate_idea(context)

    run_world_round(
        db,
        round_id="contexto001",
        idea_engine=observer,
        response_engine=accept_offer,
    )

    assert len(contexts) == 3

    for context in contexts:
        assert context["currency"] == "RCR"
        assert context["stage"] == "simulation"
        assert context["available_cents"] > 0
        assert len(context["potential_counterparties"]) == 2
        assert "profession" not in context
        assert "assigned_job" not in context
