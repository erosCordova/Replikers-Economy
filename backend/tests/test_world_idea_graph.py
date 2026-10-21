
"""Pruebas del generador autonomo de ideas."""

import os
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agentic.world_idea_graph import (
    build_world_idea_graph,
)


@pytest.fixture
def db():
    path = Path(os.environ["REPLIKERS_WORLD_TEST_DB"])

    def readonly_connection():
        con = sqlite3.connect(
            path.resolve().as_uri() + "?mode=ro",
            uri=True,
        )
        con.execute("PRAGMA query_only=ON")
        return con

    engine = create_engine(
        "sqlite+pysqlite://",
        creator=readonly_connection,
    )

    with Session(engine) as session:
        yield session

    engine.dispose()


def valid_idea():
    return {
        "title": "Servicio digital innovador",
        "description": (
            "Proponer un servicio digital "
            "personalizado al otro agente."
        ),
        "target_repliker_id": 2,
        "price_cents": 5000,
        "estimated_cost_cents": 1000,
    }


def run(db, proposal, actor=1):
    graph = build_world_idea_graph(
        db=db,
        idea_engine=lambda context: proposal,
    )

    return graph.invoke({
        "repliker_id": actor,
    })


def test_generates_own_proposal(db):
    result = run(db, valid_idea())

    assert result["status"] == "lista_para_negociar"
    assert result["payment_executed"] is False


def test_calculates_margin(db):
    result = run(db, valid_idea())

    idea = result["validated_idea"]

    assert idea["estimated_gross_margin_cents"] == 4000
    assert idea["counterparty_accepted"] is False
    assert idea["contract_executed"] is False


def test_rejects_unknown_peer(db):
    idea = valid_idea()
    idea["target_repliker_id"] = 999999

    assert run(db, idea)["status"] == (
        "contraparte_no_existente"
    )


def test_rejects_self_negotiation(db):
    idea = valid_idea()
    idea["target_repliker_id"] = 1

    assert run(db, idea)["status"] == (
        "autonegociacion_rechazada"
    )


def test_rejects_insufficient_capital(db):
    idea = valid_idea()
    idea["estimated_cost_cents"] = 999999999

    assert run(db, idea)["status"] == (
        "capital_insuficiente"
    )


def test_rejects_unaffordable_price(db):
    idea = valid_idea()
    idea["price_cents"] = 999999999

    assert run(db, idea)["status"] == (
        "contraparte_sin_capital"
    )


def test_rejects_negative_margin(db):
    idea = valid_idea()
    idea["price_cents"] = 500
    idea["estimated_cost_cents"] = 1000

    assert run(db, idea)["status"] == (
        "margen_estimado_no_positivo"
    )


def test_rejects_invalid_amounts(db):
    for value in (-1, True, "1000", None):
        idea = valid_idea()
        idea["price_cents"] = value

        assert run(db, idea)["status"] == (
            "importes_invalidos"
        )


def test_rejects_invalid_description(db):
    idea = valid_idea()
    idea["description"] = "Breve"

    assert run(db, idea)["status"] == (
        "descripcion_invalida"
    )


def test_rejects_unknown_actor(db):
    result = run(
        db,
        valid_idea(),
        actor=999999,
    )

    assert result["status"] == "agente_sin_billetera"


def test_model_error_does_not_create_trade(db):
    def broken_engine(context):
        raise RuntimeError("Modelo no disponible")

    graph = build_world_idea_graph(
        db=db,
        idea_engine=broken_engine,
    )

    result = graph.invoke({
        "repliker_id": 1,
    })

    assert result["status"] == "error_generacion"
    assert result["payment_executed"] is False


def test_invalid_model_response(db):
    result = run(db, "respuesta incorrecta")

    assert result["status"] == "error_generacion"


def test_model_cannot_execute_payment(db):
    idea = valid_idea()

    idea["payment_executed"] = True
    idea["counterparty_accepted"] = True
    idea["contract_executed"] = True

    result = run(db, idea)

    assert result["status"] == "lista_para_negociar"
    assert result["payment_executed"] is False
    assert result["validated_idea"]["payment_executed"] is False
    assert result["validated_idea"]["counterparty_accepted"] is False
    assert result["validated_idea"]["contract_executed"] is False


def test_database_is_unchanged(db):
    path = Path(os.environ["REPLIKERS_WORLD_TEST_DB"])

    def transaction_count():
        with sqlite3.connect(
            path.resolve().as_uri() + "?mode=ro",
            uri=True,
        ) as con:
            return con.execute(
                "SELECT COUNT(*) FROM ledger_transactions"
            ).fetchone()[0]

    before = transaction_count()

    result = run(db, valid_idea())

    assert result["status"] == "lista_para_negociar"
    assert transaction_count() == before


def test_engine_receives_economic_context(db):
    seen = {}

    def engine(context):
        seen.update(context)
        return valid_idea()

    graph = build_world_idea_graph(
        db=db,
        idea_engine=engine,
    )

    result = graph.invoke({
        "repliker_id": 1,
    })

    assert result["status"] == "lista_para_negociar"
    assert seen["repliker_id"] == 1
    assert seen["currency"] == "RCR"
    assert seen["available_cents"] > 0
    assert len(seen["potential_counterparties"]) == 2
