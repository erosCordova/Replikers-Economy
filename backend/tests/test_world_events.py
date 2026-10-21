
"""Pruebas de eventos, propiedad y persistencia."""

import os
import sqlite3
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.models.repliker import Repliker
from app.models.economy import LedgerTransaction

from app.services.world_autonomy_policy import (
    get_policy,
    update_policy,
)
from app.services.world_event_service import (
    world_events,
    record_round_events,
    WorldEventError,
)
from app.agentic.world_event_runtime import (
    run_logged_governed_round,
)
from app.api.routes import world_events as event_api


@pytest.fixture
def world(tmp_path):
    source = Path(
        os.environ["REPLIKERS_WORLD_TEST_DB"]
    )

    target = tmp_path / "events.db"

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
        ),
        connect_args={
            "check_same_thread": False
        },
    )

    try:
        with Session(engine) as db:
            actor = db.get(Repliker, 1)

            assert actor is not None
            assert actor.owner_id is not None

            principal = SimpleNamespace(
                id=actor.owner_id,
                is_active=True,
            )

            app = FastAPI()

            app.include_router(
                event_api.router,
                prefix="/api/v1",
            )

            def test_db():
                with Session(engine) as other:
                    yield other

            app.dependency_overrides[
                event_api.get_db
            ] = test_db

            app.dependency_overrides[
                get_current_user
            ] = lambda: principal

            with TestClient(app) as client:
                yield db, client, principal, app

    finally:
        engine.dispose()


def idea(context):
    actor_id = context["repliker_id"]

    return {
        "title": "Prueba de colaboracion",
        "description": "Informe digital experimental",
        "target_repliker_id": (
            2 if actor_id == 1 else 1
        ),
        "price_cents": 2000,
        "estimated_cost_cents": 200,
        "inspired_by_strategy_ids": [],
    }


def accept(context):
    return {
        "decision": "accept",
        "message": "Acepto el ensayo.",
    }


def enable(db):
    for actor_id in (1, 2):
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
            enabled=True,
            max_price_cents=3000,
            max_cost_cents=500,
            max_proposals_per_round=1,
            expected_version=current["version"],
        )

    db.commit()


def execute(db, round_id=None):
    return run_logged_governed_round(
        db,
        round_id=(
            round_id
            or "events_" + uuid.uuid4().hex
        ),
        idea_engine=idea,
        response_engine=accept,
        max_agents=1,
    )


def count(db):
    return db.scalar(
        select(func.count()).select_from(world_events)
    )


def test_01_initially_empty(world):
    assert count(world[0]) == 0


def test_02_blocked_round_logged(world):
    db, _, _, _ = world
    result = execute(db)

    assert result["events_inserted"] == 1
    assert result["results"][0]["governance_blocked"] is True
    assert count(db) == 1


def test_03_accepted_round_logged(world):
    db, _, _, _ = world
    enable(db)

    result = execute(db)

    assert result["results"][0]["status"] == "accepted"
    assert result["events_inserted"] == 1
    assert count(db) == 1


def test_04_replay_idempotent(world):
    db, _, _, _ = world
    enable(db)

    round_id = "idempotent_" + uuid.uuid4().hex

    first = execute(db, round_id)
    second = execute(db, round_id)

    assert first["events_inserted"] == 1
    assert second["events_inserted"] == 0
    assert count(db) == 1


def test_05_owner_can_see_events(world):
    db, client, _, _ = world
    execute(db)

    response = client.get(
        "/api/v1/world/events/mine"
    )

    assert response.status_code == 200
    assert response.json()["total_returned"] == 1


def test_06_stranger_cannot_list_others(world):
    db, client, principal, _ = world
    execute(db)

    principal.id += 999999

    response = client.get(
        "/api/v1/world/events/mine"
    )

    assert response.status_code == 200
    assert response.json()["events"] == []


def test_07_stranger_cannot_read_agent(world):
    db, client, principal, _ = world
    execute(db)

    principal.id += 999999

    response = client.get(
        "/api/v1/world/events/mine/1"
    )

    assert response.status_code == 404


def test_08_owner_can_filter_agent(world):
    db, client, _, _ = world
    execute(db)

    response = client.get(
        "/api/v1/world/events/mine/1"
    )

    assert response.status_code == 200
    assert len(response.json()["events"]) == 1


def test_09_no_private_memory_leaks(world):
    db, client, _, _ = world
    enable(db)
    execute(db)

    response = client.get(
        "/api/v1/world/events/mine"
    )

    body = response.text

    assert "private_memory" not in body
    assert "password_hash" not in body
    assert "message" not in body


def test_10_no_false_profit(world):
    db, client, _, _ = world
    enable(db)
    execute(db)

    event = client.get(
        "/api/v1/world/events/mine"
    ).json()["events"][0]

    assert event["verified_profit_cents"] is None
    assert event["real_money_used"] is False


def test_11_invalid_limit(world):
    response = world[1].get(
        "/api/v1/world/events/mine?limit=101"
    )
    assert response.status_code == 422


def test_12_anonymous_denied(world):
    _, client, _, app = world

    app.dependency_overrides.pop(
        get_current_user
    )

    response = client.get(
        "/api/v1/world/events/mine"
    )

    assert response.status_code in (401, 403)


def test_13_inactive_owner_denied(world):
    _, client, principal, _ = world
    principal.is_active = False

    response = client.get(
        "/api/v1/world/events/mine"
    )

    assert response.status_code == 401


def test_14_ledger_unchanged(world):
    db, _, _, _ = world

    before = db.scalar(
        select(func.count(LedgerTransaction.id))
    )

    enable(db)
    execute(db)

    after = db.scalar(
        select(func.count(LedgerTransaction.id))
    )

    assert before == after == 11


def test_15_duplicate_actor_rejected(world):
    db, _, _, _ = world

    with pytest.raises(WorldEventError):
        record_round_events(
            db,
            round_id="duplicate_1234",
            results=[
                {
                    "repliker_id": 1,
                    "status": "accepted",
                },
                {
                    "repliker_id": 1,
                    "status": "accepted",
                },
            ],
        )

    db.rollback()


def test_16_invalid_round_id(world):
    with pytest.raises(WorldEventError):
        record_round_events(
            world[0],
            round_id="../../etc",
            results=[],
        )


def test_17_routes_only_read(world):
    routes = event_api.router.routes

    # RW_WORLD_EVENTS_4_GET_AST_V3
    assert len(routes) == 4
    assert {route.path for route in routes} == {
        '/world/events/mine',
        '/world/events/mine/{repliker_id}',
        '/world/events/economy/mine',
        '/world/events/economy/ledger/mine',
    }
    assert all(set(route.methods or ()) == {"GET"} for route in routes)

    assert all(
        set(route.methods) <= {"GET", "HEAD"}
        for route in routes
    )


def test_18_filter_after_id(world):
    db, client, _, _ = world
    execute(db)

    response = client.get(
        "/api/v1/world/events/mine?after_id=999999"
    )

    assert response.status_code == 200
    assert response.json()["events"] == []
