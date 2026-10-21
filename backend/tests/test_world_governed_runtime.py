
"""Autonomia gobernada, negociacion y memoria World."""

import os
import sqlite3
import uuid
from pathlib import Path

import pytest

from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.models.repliker import Repliker
from app.models.user import User
from app.models.economy import LedgerTransaction

from app.agentic.world_social_learning import (
    adoptions,
    strategies,
)
from app.agentic.world_negotiation_graph import negotiations

from app.agentic.world_governed_runtime import (
    WorldGovernanceError,
    run_governed_social_round,
)

from app.services.world_autonomy_policy import (
    get_policy,
    update_policy,
)


@pytest.fixture
def world(tmp_path):
    """Base independiente para cada prueba."""

    source = Path(
        os.environ["REPLIKERS_WORLD_TEST_DB"]
    )

    target = tmp_path / "governed_world.db"

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
        connect_args={
            "timeout": 20,
            "check_same_thread": False,
        },
    )

    @event.listens_for(engine, "connect")
    def fk(connection, record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    try:
        with Session(engine) as db:
            for actor_id in (1, 2, 3):
                actor = db.get(Repliker, actor_id)

                assert actor is not None
                assert actor.owner_id is not None
                assert actor.is_active

                owner_active = db.execute(
                    select(User.is_active)
                    .where(User.id == actor.owner_id)
                ).scalar_one_or_none()

                assert owner_active is True

            yield db
            db.rollback()

    finally:
        engine.dispose()


def grant(db, *actor_ids, enabled=True):
    for actor_id in actor_ids:
        actor = db.get(Repliker, actor_id)

        current = get_policy(
            db,
            owner_id=actor.owner_id,
            repliker_id=actor_id,
        )

        update_policy(
            db,
            owner_id=actor.owner_id,
            repliker_id=actor_id,
            enabled=enabled,
            max_price_cents=3000,
            max_cost_cents=500,
            max_proposals_per_round=1,
            expected_version=current["version"],
        )

    db.commit()


def idea(context):
    actor_id = context["repliker_id"]

    target = 2 if actor_id == 1 else 1

    return {
        "title": "Estudio digital entre Replikers",
        "description": (
            "Elaborar y compartir un informe digital "
            "experimental para otra entidad autonomica."
        ),
        "target_repliker_id": target,
        "price_cents": 2500,
        "estimated_cost_cents": 300,
        "inspired_by_strategy_ids": [],
    }


def accept(context):
    return {
        "decision": "accept",
        "message": "Acepto evaluar esta propuesta.",
    }


def reject(context):
    return {
        "decision": "reject",
        "message": "Rechazo la propuesta por ahora.",
    }


def run(
    db,
    *,
    creator=idea,
    responder=accept,
    identifier=None,
    agents=1,
):
    return run_governed_social_round(
        db,
        round_id=identifier or (
            "governed_" + uuid.uuid4().hex
        ),
        idea_engine=creator,
        response_engine=responder,
        max_agents=agents,
    )


def count(db, table):
    return db.scalar(
        select(func.count()).select_from(table)
    )


def memories(db, negotiation_id):
    return db.execute(
        text(
            "SELECT COUNT(*) "
            "FROM world_agent_memories "
            "WHERE negotiation_id = :id"
        ),
        {"id": negotiation_id},
    ).scalar_one()


def test_01_default_disables_negotiation(world):
    before = count(world, negotiations)
    results = run(world)

    assert len(results) == 1
    assert results[0]["governance_blocked"] is True
    assert count(world, negotiations) == before


def test_02_disabled_does_not_call_idea_model(world):
    invoked = []

    def expensive_model(context):
        invoked.append(True)
        return idea(context)

    run(world, creator=expensive_model)

    assert invoked == []


def test_03_enabled_seller_requires_enabled_buyer(world):
    grant(world, 1)

    before = count(world, negotiations)
    results = run(world)

    assert results[0]["governance_blocked"] is True
    assert count(world, negotiations) == before


def test_04_authorized_negotiation_is_accepted(world):
    grant(world, 1, 2)

    results = run(world)

    assert results[0]["status"] == "accepted"
    assert results[0]["governance_blocked"] is False
    assert results[0]["governance_policy_version"] == 1


def test_05_price_limit_blocks_offer(world):
    grant(world, 1, 2)

    def overpriced(context):
        result = idea(context)
        result["price_cents"] = 3001
        return result

    before = count(world, negotiations)
    results = run(world, creator=overpriced)

    assert results[0]["governance_blocked"] is True
    assert count(world, negotiations) == before


def test_06_cost_limit_blocks_offer(world):
    grant(world, 1, 2)

    def too_expensive(context):
        result = idea(context)
        result["estimated_cost_cents"] = 501
        return result

    before = count(world, negotiations)
    results = run(world, creator=too_expensive)

    assert results[0]["governance_blocked"] is True
    assert count(world, negotiations) == before


def test_07_negative_cost_blocks_offer(world):
    grant(world, 1, 2)

    def invalid(context):
        result = idea(context)
        result["estimated_cost_cents"] = -1
        return result

    before = count(world, negotiations)
    results = run(world, creator=invalid)

    assert results[0]["governance_blocked"] is True
    assert count(world, negotiations) == before


def test_08_inactive_owner_blocks_agent(world):
    grant(world, 1, 2)

    actor = world.get(Repliker, 1)

    # La actualizacion es SQL directo, de modo que
    # no se cargan relaciones ajenas a esta prueba.
    world.execute(
        text(
            "UPDATE users SET is_active = 0 "
            "WHERE id = :owner_id"
        ),
        {"owner_id": actor.owner_id},
    )
    world.commit()

    before = count(world, negotiations)
    results = run(world)

    assert results[0]["governance_blocked"] is True
    assert count(world, negotiations) == before


def test_09_blocked_round_preserves_ledger(world):
    before = count(world, LedgerTransaction.__table__)

    run(world)

    assert count(
        world, LedgerTransaction.__table__
    ) == before == 11


def test_10_accepted_round_does_not_transfer_money(world):
    grant(world, 1, 2)

    before = count(world, LedgerTransaction.__table__)

    results = run(world)

    assert results[0]["status"] == "accepted"
    assert results[0]["settlement_executed"] is False

    assert count(
        world, LedgerTransaction.__table__
    ) == before == 11


def test_11_accepted_negotiation_is_remembered(world):
    grant(world, 1, 2)

    result = run(world)[0]

    assert result["status"] == "accepted"
    assert result["memories_recorded"] == 2

    assert memories(
        world, result["negotiation_id"]
    ) == 2


def test_12_replay_does_not_duplicate_memories(world):
    grant(world, 1, 2)

    identifier = "governed_replay_" + uuid.uuid4().hex

    first = run(world, identifier=identifier)

    negotiation_id = first[0]["negotiation_id"]

    second = run(world, identifier=identifier)

    assert second[0]["status"] == "already_recorded"
    assert memories(world, negotiation_id) == 2


def test_13_rejected_negotiation_is_remembered(world):
    grant(world, 1, 2)

    result = run(world, responder=reject)[0]

    assert result["status"] == "rejected"
    assert result["memories_recorded"] == 2

    assert memories(
        world, result["negotiation_id"]
    ) == 2


def test_14_original_idea_keeps_provenance(world):
    grant(world, 1, 2)

    result = run(world)[0]

    assert result["strategy_origin"] == "original"

    row = world.execute(
        select(adoptions)
        .where(
            adoptions.c.negotiation_id
            == result["negotiation_id"]
        )
    ).mappings().one()

    assert row["origin"] == "original"


def test_15_social_combination_preserves_provenance(world):
    grant(world, 1, 2)

    def combined(context):
        result = idea(context)

        catalog = context["public_strategies"]
        source_ids = [
            entry["strategy_id"]
            for entry in catalog[:2]
        ]

        assert len(source_ids) == 2

        result["inspired_by_strategy_ids"] = source_ids

        return result

    result = run(world, creator=combined)[0]

    assert result["status"] == "accepted"
    assert result["strategy_origin"] == "combined"
    assert result["memories_recorded"] == 2


def test_16_disabling_after_round_blocks_future_idea(world):
    grant(world, 1, 2)

    first = run(world)
    assert first[0]["status"] == "accepted"

    grant(world, 1, enabled=False)

    before = count(world, negotiations)
    blocked = run(world)

    assert blocked[0]["governance_blocked"] is True
    assert count(world, negotiations) == before


def test_17_model_exception_creates_no_negotiation(world):
    grant(world, 1, 2)

    def failed_model(context):
        raise RuntimeError("Simulated model outage")

    before = count(world, negotiations)

    results = run(world, creator=failed_model)

    assert results[0]["status"] == "idea_not_ready"
    assert count(world, negotiations) == before


def test_18_round_identifier_is_validated(world):
    with pytest.raises(WorldGovernanceError):
        run(world, identifier="../../unsafe")


def test_19_agent_limit_is_validated(world):
    with pytest.raises(WorldGovernanceError):
        run(world, agents=4)


def test_20_owner_impersonation_is_rejected(world):
    grant(world, 1, 2)

    def forged_identity(context):
        result = idea(context)
        result["owner_id"] = 999999
        return result

    before = count(world, negotiations)

    result = run(world, creator=forged_identity)[0]

    assert result["governance_blocked"] is True
    assert count(world, negotiations) == before


def test_21_success_does_not_publish_private_memories(world):
    grant(world, 1, 2)

    before = count(world, strategies)
    run(world)

    assert count(world, strategies) == before


def test_22_gov_runtime_rejects_invalid_engines(world):
    with pytest.raises(WorldGovernanceError):
        run_governed_social_round(
            world,
            round_id="invalid_engine_001",
            idea_engine=None,
            response_engine=accept,
        )
