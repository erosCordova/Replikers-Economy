
"""Pruebas aisladas del flujo economico LangGraph."""

import os
import sqlite3
from pathlib import Path

os.environ["SECRET_KEY"] = (
    "world-test-temporary-secret-"
    "not-for-production-2026"
)
os.environ["ECONOMY_MODE"] = "simulation"
os.environ["REAL_PAYMENTS_ENABLED"] = "false"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agentic.world_economic_graph import (
    build_world_economic_graph,
)


@pytest.fixture
def session():
    path = Path(
        os.environ["REPLIKERS_WORLD_TEST_DB"]
    )

    def readonly_connection():
        conn = sqlite3.connect(
            path.resolve().as_uri() + "?mode=ro",
            uri=True,
        )
        conn.execute("PRAGMA query_only=ON")
        return conn

    engine = create_engine(
        "sqlite+pysqlite://",
        creator=readonly_connection,
    )

    with Session(engine) as db:
        yield db

    engine.dispose()


def offers(price=2500, seller=2):
    return [{
        "offer_id": "oferta-001",
        "seller_repliker_id": seller,
        "price_cents": price,
        "currency": "RCR",
        "description":
            "Servicio digital de prueba",
    }]


def execute(session, decision, candidates=None):
    graph = build_world_economic_graph(
        db=session,
        decision_engine=lambda context: decision,
    )

    return graph.invoke({
        "buyer_repliker_id": 1,
        "offers": (
            offers()
            if candidates is None
            else candidates
        ),
    })


def test_graph_accepts_valid_proposal(session):
    result = execute(
        session,
        {
            "offer_id": "oferta-001",
            "reason": "Propuesta a evaluar",
        },
    )

    assert result["status"] == "propuesta_valida"
    assert result["selected_offer"]["price_cents"] == 2500
    assert result["payment_executed"] is False


def test_graph_rejects_unknown_offer(session):
    result = execute(
        session,
        {
            "offer_id": "oferta-inventada",
            "reason": "Prueba",
        },
    )

    assert result["status"] == "oferta_no_existente"
    assert result["payment_executed"] is False


def test_graph_rejects_insufficient_balance(session):
    result = execute(
        session,
        {
            "offer_id": "oferta-001",
            "reason": "Prueba",
        },
        offers(price=99_999_999),
    )

    assert result["status"] == "saldo_insuficiente"
    assert result["payment_executed"] is False


def test_graph_rejects_self_purchase(session):
    result = execute(
        session,
        {
            "offer_id": "oferta-001",
            "reason": "Prueba",
        },
        offers(seller=1),
    )

    assert result["status"] == "autocompra_rechazada"


def test_graph_accepts_no_opportunity(session):
    result = execute(
        session,
        {
            "offer_id": None,
            "reason": "No conviene comprar",
        },
    )

    assert result["status"] == "sin_oportunidad"


def test_graph_rejects_duplicate_offers(session):
    repeated = offers() + offers()

    result = execute(
        session,
        {
            "offer_id": "oferta-001",
            "reason": "Prueba",
        },
        repeated,
    )

    assert result["status"] == "mercado_invalido"


def test_model_cannot_change_price(session):
    result = execute(
        session,
        {
            "offer_id": "oferta-001",
            "price_cents": 1,
            "reason": "Intento de manipular precio",
        },
    )

    assert result["status"] == "propuesta_valida"
    assert result["selected_offer"]["price_cents"] == 2500
    assert result["payment_executed"] is False


def test_graph_handles_model_failure(session):
    def failing_model(context):
        raise RuntimeError("Modelo no disponible")

    graph = build_world_economic_graph(
        db=session,
        decision_engine=failing_model,
    )

    result = graph.invoke({
        "buyer_repliker_id": 1,
        "offers": offers(),
    })

    assert result["status"] == "error_motor_decision"
    assert result["payment_executed"] is False


def test_graph_rejects_missing_wallet(session):
    graph = build_world_economic_graph(
        db=session,
        decision_engine=lambda context: {
            "offer_id": "oferta-001",
            "reason": "Prueba",
        },
    )

    result = graph.invoke({
        "buyer_repliker_id": 999999999,
        "offers": offers(),
    })

    assert result["status"] == "sin_billetera"


def test_graph_never_changes_ledger(session):
    path = Path(
        os.environ["REPLIKERS_WORLD_TEST_DB"]
    )

    def tx_count():
        with sqlite3.connect(
            path.resolve().as_uri() + "?mode=ro",
            uri=True,
        ) as con:
            return con.execute(
                "SELECT COUNT(*) FROM ledger_transactions"
            ).fetchone()[0]

    previous = tx_count()

    result = execute(
        session,
        {
            "offer_id": "oferta-001",
            "reason": "Evaluacion simulada",
        },
    )

    assert result["status"] == "propuesta_valida"
    assert tx_count() == previous


def test_negative_or_invalid_price_is_rejected(session):
    for bad_price in (-100, 0, True, "100"):
        result = execute(
            session,
            {
                "offer_id": "oferta-001",
                "reason": "Prueba",
            },
            offers(price=bad_price),
        )
        assert result["status"] == "mercado_invalido"


def test_rejects_unsupported_currency(session):
    result = execute(
        session,
        {
            "offer_id": "oferta-001",
            "reason": "Prueba",
        },
        [{
            **offers()[0],
            "currency": "PEN",
        }],
    )

    assert result["status"] == "mercado_invalido"
