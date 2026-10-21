
"""Pruebas de observabilidad segura Replikers World."""

import os
import sqlite3
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

from app.agentic.world_negotiation_graph import negotiations
from app.api.routes import world_observability


@pytest.fixture
def system(tmp_path):
    source = Path(
        os.environ["REPLIKERS_WORLD_TEST_DB"]
    )

    target = tmp_path / "observability.db"

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
        connect_args={"check_same_thread": False},
    )

    with Session(engine) as db:
        actor = db.scalar(
            select(Repliker)
            .where(
                Repliker.owner_id.isnot(None),
                Repliker.is_active.is_(True),
            )
            .order_by(Repliker.id)
        )

        assert actor is not None

        actor_id = actor.id
        owner_id = actor.owner_id

    owner = SimpleNamespace(
        id=owner_id,
        is_active=True,
    )

    app = FastAPI()
    app.include_router(
        world_observability.router,
        prefix="/api/v1",
    )

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[
        world_observability.get_db
    ] = test_db

    app.dependency_overrides[
        get_current_user
    ] = lambda: owner

    with TestClient(app) as client:
        yield {
            "client": client,
            "app": app,
            "owner": owner,
            "actor_id": actor_id,
            "engine": engine,
            "dashboard": (
                f"/api/v1/world/mine/"
                f"{actor_id}/dashboard"
            ),
            "timeline": (
                f"/api/v1/world/mine/"
                f"{actor_id}/timeline"
            ),
        }

    engine.dispose()


def test_01_dashboard_is_available(system):
    response = system["client"].get(
        system["dashboard"]
    )
    assert response.status_code == 200


def test_02_dashboard_has_correct_agent(system):
    data = system["client"].get(
        system["dashboard"]
    ).json()
    assert data["repliker_id"] == system["actor_id"]


def test_03_wallet_uses_fictional_currency(system):
    data = system["client"].get(
        system["dashboard"]
    ).json()
    assert data["wallet"]["currency"] == "RCR"


def test_04_autonomy_is_visible(system):
    data = system["client"].get(
        system["dashboard"]
    ).json()
    assert isinstance(data["autonomy"]["enabled"], bool)


def test_05_autonomy_contains_version(system):
    data = system["client"].get(
        system["dashboard"]
    ).json()
    assert data["autonomy"]["version"] >= 0


def test_06_activity_is_counted(system):
    data = system["client"].get(
        system["dashboard"]
    ).json()
    assert data["activity"]["negotiations_total"] >= 0


def test_07_memories_are_counted_privately(system):
    data = system["client"].get(
        system["dashboard"]
    ).json()
    count = data["activity"]["private_memories_count"]
    assert count is None or count >= 0


def test_08_no_false_profit(system):
    data = system["client"].get(
        system["dashboard"]
    ).json()
    disclosure = data["financial_disclosure"]
    assert disclosure["negotiated_values_are_profit"] is False
    assert disclosure["profit_verified_cents"] is None


def test_09_timeline_is_available(system):
    response = system["client"].get(
        system["timeline"]
    )
    assert response.status_code == 200


def test_10_timeline_contains_list(system):
    data = system["client"].get(
        system["timeline"]
    ).json()
    assert isinstance(data["events"], list)


def test_11_timeline_limit_one(system):
    data = system["client"].get(
        system["timeline"] + "?limit=1"
    ).json()
    assert len(data["events"]) <= 1


def test_12_timeline_limit_zero_is_invalid(system):
    response = system["client"].get(
        system["timeline"] + "?limit=0"
    )
    assert response.status_code == 422


def test_13_timeline_over_limit_is_invalid(system):
    response = system["client"].get(
        system["timeline"] + "?limit=101"
    )
    assert response.status_code == 422


def test_14_stranger_cannot_read_dashboard(system):
    system["owner"].id += 999999
    response = system["client"].get(
        system["dashboard"]
    )
    assert response.status_code == 404


def test_15_stranger_cannot_read_timeline(system):
    system["owner"].id += 999999
    response = system["client"].get(
        system["timeline"]
    )
    assert response.status_code == 404


def test_16_inactive_owner_is_blocked(system):
    system["owner"].is_active = False
    response = system["client"].get(
        system["dashboard"]
    )
    assert response.status_code == 401


def test_17_anonymous_user_is_blocked(system):
    system["app"].dependency_overrides.pop(
        get_current_user
    )

    response = system["client"].get(
        system["timeline"]
    )

    assert response.status_code in (401, 403)


def test_18_timeline_does_not_leak_memory_text(system):
    response = system["client"].get(
        system["timeline"]
    )

    data = response.json()

    assert data["contains_private_memory_text"] is False

    for event in data["events"]:
        assert "private_memory" not in event
        assert "password_hash" not in event
        assert event["verified_profit_cents"] is None


def test_19_timeline_only_contains_related_negotiations(system):
    with Session(system["engine"]) as db:
        agent_id = system["actor_id"]

        allowed = set(
            db.scalars(
                select(negotiations.c.id)
                .where(
                    (
                        negotiations.c.proposer_repliker_id
                        == agent_id
                    )
                    | (
                        negotiations.c.target_repliker_id
                        == agent_id
                    )
                )
            ).all()
        )

    response = system["client"].get(
        system["timeline"]
    )

    assert response.status_code == 200

    observed = {
        event["negotiation_id"]
        for event in response.json()["events"]
    }

    assert observed.issubset(allowed)


def test_20_observation_does_not_modify_ledger(system):
    with Session(system["engine"]) as db:
        before = db.scalar(
            select(func.count(LedgerTransaction.id))
        )

    assert system["client"].get(
        system["dashboard"]
    ).status_code == 200

    assert system["client"].get(
        system["timeline"]
    ).status_code == 200

    with Session(system["engine"]) as db:
        after = db.scalar(
            select(func.count(LedgerTransaction.id))
        )

    assert before == after == 11
