
"""Integracion de IA gobernada, sin llamadas externas."""

import json
import os
import sqlite3
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.models.repliker import Repliker
from app.models.economy import LedgerTransaction

from app.agentic.world_gemini_governed import (
    WorldAIOutputError,
    WorldAIConfigurationError,
    parse_model_json,
    run_governed_world_with_model,
    run_governed_world_with_gemini,
)

from app.services.world_autonomy_policy import (
    get_policy,
    update_policy,
)
from app.services.world_event_service import world_events
from app.agentic.world_negotiation_graph import negotiations


class FakeModel:
    def __init__(
        self,
        *,
        decision="accept",
        price=2500,
        cost=300,
        forged=False,
        invalid=False,
    ):
        self.calls = 0
        self.decision = decision
        self.price = price
        self.cost = cost
        self.forged = forged
        self.invalid = invalid

    def invoke(self, prompt):
        self.calls += 1

        if self.invalid:
            return SimpleNamespace(
                content="NO ES JSON"
            )

        if "TIPO=IDEA" in prompt:
            data = {
                "title": "Servicio autonomo experimental",
                "description": (
                    "Crear un informe digital para otro Repliker."
                ),
                "target_repliker_id": 2,
                "price_cents": self.price,
                "estimated_cost_cents": self.cost,
                "inspired_by_strategy_ids": [],
            }

            if self.forged:
                data["owner_id"] = 999999

        else:
            data = {
                "decision": self.decision,
                "message": "Decision del agente simulado.",
            }

        return SimpleNamespace(
            content=json.dumps(data)
        )


@pytest.fixture
def world(tmp_path):
    source = Path(
        os.environ["REPLIKERS_WORLD_TEST_DB"]
    )

    destination = tmp_path / "gemini_mock.db"

    with sqlite3.connect(
        source.resolve().as_uri() + "?mode=ro",
        uri=True,
    ) as origin:
        with sqlite3.connect(str(destination)) as target:
            origin.backup(target)

    engine = create_engine(
        URL.create(
            "sqlite+pysqlite",
            database=str(destination),
        ),
        connect_args={
            "timeout": 20,
            "check_same_thread": False,
        },
    )

    try:
        with Session(engine) as db:
            yield db
            db.rollback()
    finally:
        engine.dispose()


def enable(db, *actors):
    for actor_id in actors:
        actor = db.get(Repliker, actor_id)

        assert actor is not None

        current = get_policy(
            db,
            owner_id=actor.owner_id,
            repliker_id=actor_id,
        )

        update_policy(
            db,
            owner_id=actor.owner_id,
            repliker_id=actor_id,
            enabled=True,
            max_price_cents=3000,
            max_cost_cents=500,
            max_proposals_per_round=1,
            expected_version=current["version"],
        )

    db.commit()


def execute(db, model, round_id=None):
    return run_governed_world_with_model(
        db,
        round_id=round_id or (
            "gemini_test_" + uuid.uuid4().hex
        ),
        model=model,
        max_agents=1,
    )


def count(db, table):
    return db.scalar(
        select(func.count()).select_from(table)
    )


def test_01_external_gemini_requires_optin():
    with pytest.raises(WorldAIConfigurationError):
        run_governed_world_with_gemini(
            None,
            round_id="gemini_optin_123",
        )


def test_02_invalid_json_is_rejected():
    with pytest.raises(WorldAIOutputError):
        parse_model_json("texto incorrecto")


def test_03_duplicate_json_keys_are_rejected():
    with pytest.raises(WorldAIOutputError):
        parse_model_json('{"x":1,"x":2}')


def test_04_json_markdown_fence_is_supported():
    result = parse_model_json(
        '```json\n{"valid":true}\n```'
    )
    assert result == {"valid": True}


def test_05_disabled_agent_never_calls_model(world):
    fake = FakeModel()
    before = count(world, negotiations)

    result = execute(world, fake)

    assert fake.calls == 0
    assert result["results"][0]["governance_blocked"]
    assert count(world, negotiations) == before


def test_06_disabled_counterparty_never_calls_model(world):
    enable(world, 1)
    fake = FakeModel()

    before = count(world, negotiations)
    result = execute(world, fake)

    assert fake.calls == 0
    assert count(world, negotiations) == before
    assert result["payments_executed"] is False


def test_07_authorized_idea_is_accepted_and_logged(world):
    enable(world, 1, 2)
    fake = FakeModel()

    result = execute(world, fake)

    assert result["results"][0]["status"] == "accepted"
    assert result["events_inserted"] == 1
    assert fake.calls == 2
    assert count(world, world_events) == 1


def test_08_accepted_round_creates_two_memories(world):
    enable(world, 1, 2)

    result = execute(world, FakeModel())
    negotiation_id = result["results"][0]["negotiation_id"]

    amount = world.execute(
        text(
            "SELECT COUNT(*) FROM world_agent_memories "
            "WHERE negotiation_id = :id"
        ),
        {"id": negotiation_id},
    ).scalar_one()

    assert amount == 2


def test_09_rejection_is_logged_without_payment(world):
    enable(world, 1, 2)

    result = execute(
        world,
        FakeModel(decision="reject"),
    )

    assert result["results"][0]["status"] == "rejected"
    assert result["events_inserted"] == 1
    assert result["payments_executed"] is False


def test_10_overpriced_ai_idea_creates_no_negotiation(world):
    enable(world, 1, 2)

    fake = FakeModel(price=3001)
    before = count(world, negotiations)

    execute(world, fake)

    assert fake.calls == 1
    assert count(world, negotiations) == before


def test_11_owner_impersonation_is_rejected(world):
    enable(world, 1, 2)

    fake = FakeModel(forged=True)
    before = count(world, negotiations)

    execute(world, fake)

    assert fake.calls == 1
    assert count(world, negotiations) == before


def test_12_ledger_is_unchanged_by_model_decision(world):
    enable(world, 1, 2)

    before = count(
        world,
        LedgerTransaction.__table__,
    )

    result = execute(world, FakeModel())

    after = count(
        world,
        LedgerTransaction.__table__,
    )

    assert result["real_money_used"] is False
    assert before == after == 11
