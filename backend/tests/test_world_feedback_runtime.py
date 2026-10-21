
"""Pruebas de aprendizaje economico verificable."""

import hashlib
import os
import sqlite3
import uuid
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

from app.agentic.world_feedback_runtime import (
    WorldFeedbackError,
    get_economic_feedback,
    run_world_feedback_round,
)

from app.agentic.world_negotiation_graph import (
    build_world_negotiation_graph,
    negotiations,
)

from app.agentic.world_memory_runtime import memories

from app.services.world_contract_service import (
    open_contract,
    submit_delivery,
    review_delivery,
)

from app.services.world_settlement_service import (
    settle_approved_contract,
)

from app.models.economy import (
    LedgerAccount,
    LedgerTransaction,
)

from app.services.economy_service import account_balance


@pytest.fixture
def db(tmp_path):
    source = Path(
        os.environ["REPLIKERS_WORLD_TEST_DB"]
    )

    destination = tmp_path / "feedback_test.db"

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
    def foreign_keys(connection, record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    with Session(engine) as session:
        yield session
        session.rollback()

    engine.dispose()


def idea(context):
    peer = context["potential_counterparties"][0]

    return {
        "title": "Servicio de investigacion digital",
        "description": (
            "Investigar nuevas oportunidades "
            "economicas de forma experimental."
        ),
        "target_repliker_id": peer["repliker_id"],
        "price_cents": 2200,
        "estimated_cost_cents": 200,
    }


def accept(context):
    return {
        "decision": "accept",
        "message": "Acepto evaluar el servicio propuesto.",
    }


def reject(context):
    return {
        "decision": "reject",
        "message": "No considero conveniente la propuesta.",
    }


def run(
    db,
    round_id="feedback_01",
    idea_engine=idea,
    response_engine=accept,
    max_agents=3,
):
    return run_world_feedback_round(
        db,
        round_id=round_id,
        idea_engine=idea_engine,
        response_engine=response_engine,
        max_agents=max_agents,
    )


def count(db, table):
    return db.scalar(
        select(func.count()).select_from(table)
    )


def test_01_feedback_reads_current_balance(db):
    profile = get_economic_feedback(db, 1)

    wallet = db.scalar(
        select(LedgerAccount).where(
            LedgerAccount.repliker_id == 1,
            LedgerAccount.kind == "repliker_available",
            LedgerAccount.currency == "RCR",
        )
    )

    assert profile["balance_cents"] == account_balance(
        db=db, account_id=wallet.id
    )


def test_02_no_unverified_profit(db):
    profile = get_economic_feedback(db, 1)

    assert profile["realized_net_profit_cents"] is None
    assert profile["currency"] == "RCR"


def test_03_historical_memories_are_counted(db):
    profile = get_economic_feedback(db, 1)

    expected = db.execute(
        select(memories.c.id).where(
            memories.c.repliker_id == 1
        )
    ).all()

    assert profile["negotiations_observed"] == len(expected)


def test_04_acceptances_are_not_income(db):
    profile = get_economic_feedback(db, 1)

    assert (
        profile["verified_contract_receipts_cents"]
        == 0
    )
    assert (
        profile["verified_contract_payments_cents"]
        == 0
    )


def test_05_initiatives_have_observation_counts(db):
    profile = get_economic_feedback(db, 1)

    strategies = profile["past_initiative_results"]

    assert isinstance(strategies, list)

    for strategy in strategies:
        assert strategy["observations"] >= 1
        assert (
            strategy["accepted"] + strategy["rejected"]
            == strategy["observations"]
        )
        assert strategy["verified_profit_cents"] is None


def test_06_feedback_is_per_agent(db):
    a = get_economic_feedback(db, 1)
    b = get_economic_feedback(db, 2)

    assert a["repliker_id"] == 1
    assert b["repliker_id"] == 2


def test_07_feedback_is_read_only(db):
    before = count(db, LedgerTransaction.__table__)

    get_economic_feedback(db, 1)

    after = count(db, LedgerTransaction.__table__)

    assert before == after == 8


def test_08_three_agents_complete_round(db):
    results = run(db)

    assert len(results) == 3
    assert all(
        row["status"] == "accepted"
        for row in results
    )


def test_09_new_feedback_follows_negotiations(db):
    before = get_economic_feedback(db, 1)

    run(db, round_id="feedback_new")

    after = get_economic_feedback(db, 1)

    assert (
        after["proposals_sent"]
        == before["proposals_sent"] + 1
    )


def test_10_idea_engine_receives_feedback(db):
    seen = []

    def observer(context):
        seen.append(context)
        return idea(context)

    run(
        db,
        round_id="feedback_context",
        idea_engine=observer,
        max_agents=1,
    )

    assert len(seen) == 1
    assert seen[0]["economic_feedback"]["repliker_id"] == 1
    assert "past_negotiations" in seen[0]


def test_11_buyer_receives_own_feedback(db):
    seen = []

    def observer(context):
        seen.append(context)
        return accept(context)

    run(
        db,
        round_id="feedback_buyer",
        response_engine=observer,
        max_agents=1,
    )

    assert len(seen) == 1

    assert (
        seen[0]["economic_feedback"]["repliker_id"]
        == seen[0]["acting_repliker_id"]
    )


def test_12_repeated_round_is_idempotent(db):
    first = run(db, round_id="feedback_replay")
    second = run(db, round_id="feedback_replay")

    assert len(first) == len(second) == 3

    assert all(
        row["status"] == "already_recorded"
        for row in second
    )


def test_13_model_failure_does_not_fake_history(db):
    before = count(db, memories)

    def broken(context):
        raise RuntimeError("IA no disponible")

    results = run(
        db,
        round_id="feedback_failure",
        idea_engine=broken,
    )

    after = count(db, memories)

    assert all(
        row["status"] == "idea_not_ready"
        for row in results
    )

    assert before == after


def test_14_rejection_changes_acceptance_statistics(db):
    before = get_economic_feedback(db, 1)

    run(
        db,
        round_id="feedback_rejections",
        response_engine=reject,
    )

    after = get_economic_feedback(db, 1)

    assert (
        after["proposals_rejected"]
        == before["proposals_rejected"] + 1
    )


def test_15_no_ledger_mutation_from_round(db):
    before = count(db, LedgerTransaction.__table__)

    run(db, round_id="feedback_ledger")

    after = count(db, LedgerTransaction.__table__)

    assert before == after == 8


def test_16_invalid_actor_is_rejected(db):
    for value in (-1, 0, True, "1", 999999):
        with pytest.raises(WorldFeedbackError):
            get_economic_feedback(db, value)


def test_17_verified_contract_cashflow(db):
    payload = b"entrega-economica-verificable"
    digest = hashlib.sha256(payload).hexdigest()
    reference = "artifact:sha256:" + digest

    graph = build_world_negotiation_graph(
        db=db,
        response_engine=lambda context: {
            "decision": "accept",
            "message": "Acepto evaluar este contrato.",
        },
    )

    result = graph.invoke({
        "idempotency_key": (
            "feedback-contract-" + uuid.uuid4().hex
        ),
        "proposal": {
            "proposer_repliker_id": 1,
            "target_repliker_id": 2,
            "title": "Artefacto digital de ensayo",
            "description": (
                "Proporcionar un artefacto digital "
                "comprobable para otro agente."
            ),
            "currency": "RCR",
            "price_cents": 3500,
            "estimated_cost_cents": 200,
        },
    })

    assert result["status"] == "accepted"

    contract = open_contract(
        db,
        negotiation_id=result["negotiation_id"],
        acting_repliker_id=1,
    )

    submit_delivery(
        db,
        contract_id=contract["id"],
        acting_repliker_id=1,
        reference=reference,
    )

    review_delivery(
        db,
        contract_id=contract["id"],
        acting_repliker_id=2,
        decision="approve",
        note="Artefacto revisado y aceptado.",
    )

    settlement = settle_approved_contract(
        db,
        contract_id=contract["id"],
        trusted_artifact_reader=(
            lambda submitted: payload
        ),
    )

    assert settlement["status"] == "settled"

    seller = get_economic_feedback(db, 1)
    buyer = get_economic_feedback(db, 2)

    assert (
        seller["verified_contract_receipts_cents"]
        == 3500
    )

    assert (
        buyer["verified_contract_payments_cents"]
        == 3500
    )

    assert seller["net_verified_cashflow_cents"] == 3500
    assert buyer["net_verified_cashflow_cents"] == -3500

    assert seller["realized_net_profit_cents"] is None
    assert buyer["realized_net_profit_cents"] is None
