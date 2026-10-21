"""Pruebas de memoria economica multiagente."""

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

from app.agentic.world_memory_runtime import (
    WorldMemoryError,
    get_agent_memories,
    record_negotiation_memories,
    run_world_round_with_memory,
    memories,
)

from app.agentic.world_negotiation_graph import negotiations
from app.models.economy import LedgerTransaction


@pytest.fixture
def db(tmp_path):
    source = Path(
        os.environ["REPLIKERS_WORLD_TEST_DB"]
    )

    target = tmp_path / "memory_test.db"

    with sqlite3.connect(
        source.resolve().as_uri() + "?mode=ro",
        uri=True,
    ) as original:
        with sqlite3.connect(str(target)) as copy:
            original.backup(copy)

    engine = create_engine(
        URL.create(
            "sqlite+pysqlite",
            database=str(target),
        )
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    with Session(engine) as session:
        yield session
        session.rollback()

    engine.dispose()


def historic_id(db):
    return db.scalar(
        select(negotiations.c.id)
        .order_by(negotiations.c.id)
        .limit(1)
    )


def backfill(db):
    return record_negotiation_memories(
        db,
        negotiation_id=historic_id(db),
        round_id="historical_gemini",
    )


def idea_engine(context):
    peer = context["potential_counterparties"][0]

    return {
        "title": "Investigacion economica digital",
        "description": (
            "Crear un estudio digital de oportunidades "
            "para otro agente economico."
        ),
        "target_repliker_id": peer["repliker_id"],
        "price_cents": 2500,
        "estimated_cost_cents": 400,
    }


def accept_engine(context):
    return {
        "decision": "accept",
        "message": "Acepto evaluar esta propuesta economica.",
    }


def reject_engine(context):
    return {
        "decision": "reject",
        "message": "No considero conveniente esta propuesta.",
    }


def run(
    db,
    round_id="memory_round_01",
    response=accept_engine,
    idea=idea_engine,
    count=3,
):
    return run_world_round_with_memory(
        db,
        round_id=round_id,
        idea_engine=idea,
        response_engine=response,
        max_agents=count,
    )


def count_rows(db, table):
    return db.scalar(
        select(func.count()).select_from(table)
    )


def test_01_historical_negotiation_is_remembered(db):
    assert backfill(db) == 2
    assert count_rows(db, memories) == 2


def test_02_backfill_is_idempotent(db):
    assert backfill(db) == 2
    assert backfill(db) == 0
    assert count_rows(db, memories) == 2


def test_03_memories_are_private_to_actor(db):
    backfill(db)

    first = get_agent_memories(db, 1)
    second = get_agent_memories(db, 2)
    third = get_agent_memories(db, 3)

    assert len(first) == 1
    assert len(second) == 1
    assert third == []


def test_04_memories_do_not_fake_profit(db):
    backfill(db)

    memory = get_agent_memories(db, 1)[0]

    assert memory["realized_profit"] is None
    assert memory["payment_verified"] is False
    assert memory["outcome"] == "accepted"


def test_05_three_agents_record_experiences(db):
    results = run(db)

    assert len(results) == 3
    assert all(
        item["status"] == "accepted"
        for item in results
    )
    assert count_rows(db, memories) == 6


def test_06_two_roles_per_negotiation(db):
    run(db)

    records = db.execute(
        select(memories.c.role)
    ).scalars().all()

    assert records.count("proposer") == 3
    assert records.count("counterparty") == 3


def test_07_repeated_round_does_not_duplicate(db):
    first = run(db, round_id="memory_replay")
    second = run(db, round_id="memory_replay")

    assert len(first) == len(second) == 3
    assert all(
        item["status"] == "already_recorded"
        for item in second
    )
    assert count_rows(db, memories) == 6


def test_08_replay_does_not_reconsult_models(db):
    run(db, round_id="memory_no_ai")

    def forbidden(context):
        raise RuntimeError("No debe llamarse.")

    second = run(
        db,
        round_id="memory_no_ai",
        idea=forbidden,
        response=forbidden,
    )

    assert all(
        item["status"] == "already_recorded"
        for item in second
    )


def test_09_agents_receive_previous_memories(db):
    backfill(db)

    observed = []

    def capturing_ideas(context):
        observed.append(context)
        return idea_engine(context)

    run(
        db,
        round_id="memory_context",
        idea=capturing_ideas,
        count=1,
    )

    assert len(observed) == 1
    assert len(
        observed[0]["past_negotiations"]
    ) >= 1


def test_10_counterparties_receive_memories(db):
    backfill(db)

    observed = []

    def capturing_responses(context):
        observed.append(context)
        return accept_engine(context)

    run(
        db,
        round_id="memory_buyer",
        response=capturing_responses,
        count=1,
    )

    assert len(observed) == 1
    assert (
        "past_negotiations"
        in observed[0]
    )


def test_11_rejections_are_remembered(db):
    results = run(
        db,
        round_id="memory_rejected",
        response=reject_engine,
    )

    assert all(
        item["status"] == "rejected"
        for item in results
    )

    outcomes = db.execute(
        select(memories.c.outcome)
    ).scalars().all()

    assert outcomes == ["rejected"] * 6


def test_12_model_failure_creates_no_fake_memory(db):
    def broken(context):
        raise RuntimeError("Sin acceso al modelo.")

    results = run(
        db,
        round_id="memory_error",
        idea=broken,
    )

    assert all(
        item["status"] == "idea_not_ready"
        for item in results
    )
    assert count_rows(db, memories) == 0


def test_13_ledger_is_unchanged(db):
    before = count_rows(db, LedgerTransaction.__table__)

    run(db)

    after = count_rows(db, LedgerTransaction.__table__)

    assert before == after == 8


def test_14_invalid_round_is_rejected(db):
    with pytest.raises(WorldMemoryError):
        run(
            db,
            round_id="../../otra-base",
        )


def test_15_invalid_memory_access_is_rejected(db):
    with pytest.raises(WorldMemoryError):
        get_agent_memories(db, -1)

    with pytest.raises(WorldMemoryError):
        get_agent_memories(db, 1, limit=0)

    with pytest.raises(WorldMemoryError):
        get_agent_memories(db, 1, limit=True)
