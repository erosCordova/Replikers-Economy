
"""Pruebas de comparacion economica de estrategias."""

import hashlib
import os
import sqlite3
import uuid
from pathlib import Path

import pytest

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.agentic.world_strategy_evaluation import (
    StrategyEvaluationError,
    get_strategy_comparison,
    run_strategy_evidence_round,
)

from app.agentic.world_social_learning import (
    adoptions,
    strategies,
)
from app.agentic.world_negotiation_graph import negotiations
from app.models.economy import LedgerTransaction

from app.services.world_contract_service import (
    open_contract,
    submit_delivery,
    review_delivery,
)
from app.services.world_settlement_service import (
    settle_approved_contract,
)


@pytest.fixture
def db(tmp_path):
    source = Path(
        os.environ["REPLIKERS_WORLD_TEST_DB"]
    )
    target = tmp_path / "comparison.db"

    with sqlite3.connect(
        source.resolve().as_uri() + "?mode=ro",
        uri=True,
    ) as origin:
        with sqlite3.connect(str(target)) as destination:
            origin.backup(destination)

    engine = create_engine(
        URL.create(
            "sqlite+pysqlite",
            database=str(target),
        ),
        connect_args={"timeout": 15},
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


def idea(context):
    actor = context["repliker_id"]
    catalog = context["public_strategies"]
    peer = context["potential_counterparties"][0]

    if actor == 1:
        sources = [
            item["strategy_id"]
            for item in catalog[:2]
        ]
    elif actor == 2:
        sources = [
            item["strategy_id"]
            for item in catalog[:1]
        ]
    else:
        sources = []

    return {
        "title": "Servicio de analisis experimental",
        "description": (
            "Preparar un estudio digital de "
            "oportunidades para otro Repliker."
        ),
        "target_repliker_id": peer["repliker_id"],
        "price_cents": 2500,
        "estimated_cost_cents": 300,
        "inspired_by_strategy_ids": sources,
    }


def accept(context):
    return {
        "decision": "accept",
        "message": "Acepto evaluar el servicio.",
    }


def mixed_response(context):
    decision = (
        "reject"
        if context["acting_repliker_id"] == 2
        else "accept"
    )

    return {
        "decision": decision,
        "message": (
            "Acepto estudiar la propuesta."
            if decision == "accept"
            else "No acepto el precio propuesto."
        ),
    }


def run(
    db,
    round_id="compare_001",
    creator=idea,
    responder=accept,
    max_agents=3,
):
    return run_strategy_evidence_round(
        db,
        round_id=round_id,
        idea_engine=creator,
        response_engine=responder,
        max_agents=max_agents,
    )


def count(db, table):
    return db.scalar(
        select(func.count()).select_from(table)
    )


def test_01_three_types_are_reported(db):
    report = get_strategy_comparison(db)

    assert set(report["groups"]) == {
        "original", "adapted", "combined"
    }


def test_02_previously_combined_idea_is_recorded(db):
    report = get_strategy_comparison(db)

    assert (
        report["groups"]["combined"]["negotiations"]
        >= 1
    )


def test_03_older_negotiations_are_unclassified(db):
    report = get_strategy_comparison(db)

    assert (
        report["negotiations_without_provenance"]
        >= 1
    )


def test_04_no_fake_profit(db):
    report = get_strategy_comparison(db)

    assert report["economic_winner"] is None
    assert report["causal_comparison"] is False
    assert report["verified_net_profit_cents"] is None

    for group in report["groups"].values():
        assert group["verified_net_profit_cents"] is None


def test_05_no_fake_receipts(db):
    report = get_strategy_comparison(db)

    assert all(
        group["verified_receipts_cents"] == 0
        for group in report["groups"].values()
    )


def test_06_feedback_is_scoped_to_agent(db):
    report = get_strategy_comparison(
        db,
        repliker_id=1,
    )

    assert report["scope"] == "single_repliker"
    assert report["repliker_id"] == 1


def test_07_invalid_actor_is_rejected(db):
    for actor in (-1, 0, True, "1", 999999):
        with pytest.raises(StrategyEvaluationError):
            get_strategy_comparison(
                db,
                repliker_id=actor,
            )


def test_08_comparison_is_read_only(db):
    before = count(db, LedgerTransaction.__table__)
    get_strategy_comparison(db)
    after = count(db, LedgerTransaction.__table__)

    assert before == after


def test_09_three_strategy_types_are_exercised(db):
    results = run(db, round_id="all_origins")

    assert len(results) == 3
    assert [
        result["strategy_origin"]
        for result in results
    ] == ["combined", "adapted", "original"]


def test_10_acceptance_rates_are_consistent(db):
    run(db, round_id="rates", responder=mixed_response)

    report = get_strategy_comparison(db)

    for group in report["groups"].values():
        count = group["negotiations"]

        assert (
            group["accepted"] + group["rejected"]
            == count
        )

        if count:
            assert group["acceptance_rate"] == round(
                group["accepted"] / count,
                4,
            )


def test_11_ideas_receive_evidence(db):
    observed = []

    def observer(context):
        observed.append(context)
        return idea(context)

    run(
        db,
        round_id="idea_context",
        creator=observer,
        max_agents=1,
    )

    assert len(observed) == 1
    assert (
        observed[0]["strategy_evidence"]["repliker_id"]
        == 1
    )


def test_12_buyer_receives_own_evidence(db):
    observed = []

    def observer(context):
        observed.append(context)
        return accept(context)

    run(
        db,
        round_id="buyer_context",
        responder=observer,
        max_agents=1,
    )

    assert len(observed) == 1

    assert (
        observed[0]["strategy_evidence"]["repliker_id"]
        == observed[0]["acting_repliker_id"]
    )


def test_13_replay_is_idempotent(db):
    first = run(db, round_id="compare_replay")
    count_before = count(db, adoptions)

    second = run(db, round_id="compare_replay")

    assert len(first) == len(second) == 3
    assert all(
        row["status"] == "already_recorded"
        for row in second
    )
    assert count(db, adoptions) == count_before


def test_14_invalid_inspiration_is_rejected(db):
    def invalid(context):
        result = idea(context)
        result["inspired_by_strategy_ids"] = [999999]
        return result

    before = count(db, adoptions)

    result = run(
        db,
        round_id="invalid_inspiration",
        creator=invalid,
        max_agents=1,
    )

    assert result[0]["status"] == "idea_not_ready"
    assert count(db, adoptions) == before


def test_15_no_payment_from_strategy_round(db):
    before = count(db, LedgerTransaction.__table__)

    run(db, round_id="no_payment")

    assert count(
        db,
        LedgerTransaction.__table__,
    ) == before == 8


def test_16_verified_receipts_are_attributed(db):
    results = run(
        db,
        round_id="settlement_test",
    )

    original = next(
        item for item in results
        if item["strategy_origin"] == "original"
    )

    assert original["status"] == "accepted"
    assert original["repliker_id"] == 3

    payload = b"replikers-world-evidence-verified"
    digest = hashlib.sha256(payload).hexdigest()

    contract = open_contract(
        db,
        negotiation_id=original["negotiation_id"],
        acting_repliker_id=3,
    )

    submit_delivery(
        db,
        contract_id=contract["id"],
        acting_repliker_id=3,
        reference="artifact:sha256:" + digest,
    )

    review_delivery(
        db,
        contract_id=contract["id"],
        acting_repliker_id=1,
        decision="approve",
        note="Entrega digital aceptada.",
    )

    payment = settle_approved_contract(
        db,
        contract_id=contract["id"],
        trusted_artifact_reader=lambda ref: payload,
    )

    assert payment["status"] == "settled"

    report = get_strategy_comparison(
        db,
        repliker_id=3,
    )

    original_group = report["groups"]["original"]

    assert original_group["settled_contracts"] == 1
    assert original_group["verified_receipts_cents"] == 2500
    assert original_group["verified_net_profit_cents"] is None


def test_17_model_failure_does_not_create_records(db):
    before = count(db, adoptions)

    def broken(context):
        raise RuntimeError("Modelo no disponible")

    result = run(
        db,
        round_id="broken_model",
        creator=broken,
        max_agents=1,
    )

    assert result[0]["status"] == "idea_not_ready"
    assert count(db, adoptions) == before


def test_18_economic_winner_is_not_invented(db):
    run(
        db,
        round_id="comparison_is_not_profit",
    )

    report = get_strategy_comparison(db)

    assert report["economic_winner"] is None
    assert report["costs_verified"] is False
    assert report["causal_comparison"] is False
