
"""Pruebas de conexion entre Gemini y LangGraph.

Las pruebas sustituyen la API externa, pero ejercitan
el coordinador real y su persistencia economica.
"""

import os
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select, func
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.agentic import world_live_runtime as live
from app.agentic.world_negotiation_graph import (
    negotiations,
    events,
)
from app.models.economy import LedgerTransaction


@pytest.fixture
def db(tmp_path):
    source = Path(os.environ["REPLIKERS_WORLD_TEST_DB"])
    destination = tmp_path / "gemini_integration.db"

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
        ),
        connect_args={"timeout": 15},
    )

    @event.listens_for(engine, "connect")
    def enable_fk(connection, record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    with Session(engine) as session:
        yield session
        session.rollback()

    engine.dispose()


def install_engines(
    monkeypatch,
    *,
    decision="accept",
    idea_fails=False,
    response_fails=False,
):
    calls = {
        "ideas": [],
        "responses": [],
        "models": [],
    }

    def idea_factory(model_name):
        calls["models"].append(("idea", model_name))

        def generate(context):
            calls["ideas"].append(context)

            if idea_fails:
                raise RuntimeError("IA de ideas no disponible")

            peer = context["potential_counterparties"][0]

            return {
                "title": "Investigacion economica autonomizada",
                "description": (
                    "Crear un informe original de oportunidades "
                    "comerciales para otro Repliker."
                ),
                "target_repliker_id": peer["repliker_id"],
                "price_cents": 3000,
                "estimated_cost_cents": 500,
            }

        return generate

    def response_factory(model_name):
        calls["models"].append(("response", model_name))

        def respond(context):
            calls["responses"].append(context)

            if response_fails:
                raise RuntimeError("IA de respuesta no disponible")

            return {
                "decision": decision,
                "message": (
                    "Acepto evaluar este negocio."
                    if decision == "accept"
                    else "Prefiero conservar mis recursos."
                ),
            }

        return respond

    monkeypatch.setattr(
        live,
        "make_gemini_idea_engine",
        idea_factory,
    )

    monkeypatch.setattr(
        live,
        "make_gemini_response_engine",
        response_factory,
    )

    return calls


def count(db, table):
    return db.scalar(
        select(func.count()).select_from(table)
    )


def test_01_three_agents_run(db, monkeypatch):
    calls = install_engines(monkeypatch)

    result = live.run_world_with_gemini(
        db,
        round_id="live-test-001",
        max_agents=3,
    )

    assert len(result) == 3
    assert all(r["status"] == "accepted" for r in result)
    assert len(calls["ideas"]) == 3
    assert len(calls["responses"]) == 3


def test_02_negotiations_persist(db, monkeypatch):
    install_engines(monkeypatch)

    live.run_world_with_gemini(
        db,
        round_id="live-test-002",
    )

    assert count(db, negotiations) == 3


def test_03_conversations_persist(db, monkeypatch):
    install_engines(monkeypatch)

    live.run_world_with_gemini(
        db,
        round_id="live-test-003",
    )

    assert count(db, events) == 6


def test_04_ledger_is_unchanged(db, monkeypatch):
    install_engines(monkeypatch)

    before = db.scalar(
        select(func.count(LedgerTransaction.id))
    )

    live.run_world_with_gemini(
        db,
        round_id="live-test-004",
    )

    after = db.scalar(
        select(func.count(LedgerTransaction.id))
    )

    assert before == after == 8


def test_05_round_is_idempotent(db, monkeypatch):
    calls = install_engines(monkeypatch)

    first = live.run_world_with_gemini(
        db,
        round_id="live-test-005",
    )

    second = live.run_world_with_gemini(
        db,
        round_id="live-test-005",
    )

    assert len(first) == len(second) == 3
    assert all(
        r["status"] == "already_recorded"
        for r in second
    )
    assert len(calls["ideas"]) == 3
    assert count(db, negotiations) == 3


def test_06_models_can_reject(db, monkeypatch):
    install_engines(
        monkeypatch,
        decision="reject",
    )

    result = live.run_world_with_gemini(
        db,
        round_id="live-test-006",
    )

    assert all(
        r["status"] == "rejected"
        for r in result
    )


def test_07_idea_failure_is_safe(db, monkeypatch):
    install_engines(
        monkeypatch,
        idea_fails=True,
    )

    result = live.run_world_with_gemini(
        db,
        round_id="live-test-007",
    )

    assert all(
        r["status"] == "idea_not_ready"
        for r in result
    )
    assert count(db, negotiations) == 0


def test_08_response_failure_is_safe(db, monkeypatch):
    install_engines(
        monkeypatch,
        response_fails=True,
    )

    result = live.run_world_with_gemini(
        db,
        round_id="live-test-008",
    )

    assert all(
        r["status"] == "response_error"
        for r in result
    )
    assert count(db, negotiations) == 0


def test_09_missing_credentials_fail_closed(db, monkeypatch):
    def missing_key(model_name):
        raise RuntimeError("No hay clave Gemini")

    monkeypatch.setattr(
        live,
        "make_gemini_idea_engine",
        missing_key,
    )

    with pytest.raises(RuntimeError):
        live.run_world_with_gemini(
            db,
            round_id="live-test-009",
        )

    assert count(db, negotiations) == 0


def test_10_invalid_model_is_rejected(db, monkeypatch):
    with pytest.raises(ValueError):
        live.run_world_with_gemini(
            db,
            round_id="live-test-010",
            model_name="../otro-modelo",
        )


def test_11_invalid_agent_count_is_rejected(db):
    for number in (0, -1, 4, True, "3"):
        with pytest.raises(ValueError):
            live.run_world_with_gemini(
                db,
                round_id="live-test-011",
                max_agents=number,
            )


def test_12_one_agent_only(db, monkeypatch):
    calls = install_engines(monkeypatch)

    result = live.run_world_with_gemini(
        db,
        round_id="live-test-012",
        max_agents=1,
    )

    assert len(result) == 1
    assert len(calls["ideas"]) == 1
    assert len(calls["responses"]) == 1
    assert result[0]["payment_executed"] is False
