
"""Pruebas de politicas y autorizacion de autonomia World."""

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

from app.auth.dependencies import get_current_user, get_db
from app.models.repliker import Repliker
from app.models.economy import LedgerTransaction
from app.api.routes.world_autonomy import router
from app.services.world_autonomy_policy import (
    get_policy,
    update_policy,
    policies,
    events,
)


@pytest.fixture
def world(tmp_path):
    source = Path(os.environ["REPLIKERS_WORLD_TEST_DB"])
    target = tmp_path / "autonomy_test.db"

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
        connect_args={"check_same_thread": False},
    )

    with Session(engine) as db:
        agent = db.scalar(
            select(Repliker)
            .where(
                Repliker.owner_id.isnot(None),
                Repliker.is_active.is_(True),
            )
            .order_by(Repliker.id)
        )
        assert agent is not None

        agent_id = agent.id
        owner_id = agent.owner_id

    owner = SimpleNamespace(
        id=owner_id, is_active=True
    )

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    def isolated_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = isolated_db
    app.dependency_overrides[get_current_user] = lambda: owner

    with TestClient(app) as client:
        yield {
            "client": client,
            "app": app,
            "engine": engine,
            "owner": owner,
            "owner_id": owner_id,
            "agent_id": agent_id,
            "path": (
                "/api/v1/world/mine/"
                + str(agent_id)
                + "/autonomy"
            ),
        }

    engine.dispose()


def payload(version=0, enabled=True):
    return {
        "enabled": enabled,
        "max_price_cents": 5000,
        "max_cost_cents": 800,
        "max_proposals_per_round": 3,
        "expected_version": version,
    }


def proposal(price=2000, cost=200):
    return {
        "price_cents": price,
        "estimated_cost_cents": cost,
    }


def enable(w):
    response = w["client"].put(
        w["path"], json=payload()
    )
    assert response.status_code == 200, response.text
    return response


def test_01_default_is_disabled(world):
    r = world["client"].get(world["path"])
    assert r.status_code == 200
    assert r.json()["enabled"] is False


def test_02_default_version_is_zero(world):
    r = world["client"].get(world["path"])
    assert r.json()["version"] == 0


def test_03_only_owner_can_read(world):
    world["owner"].id += 999999
    assert world["client"].get(
        world["path"]
    ).status_code == 404


def test_04_only_owner_can_configure(world):
    world["owner"].id += 999999
    assert world["client"].put(
        world["path"], json=payload()
    ).status_code == 404


def test_05_only_owner_can_check(world):
    world["owner"].id += 999999
    assert world["client"].post(
        world["path"] + "/check",
        json=proposal(),
    ).status_code == 404


def test_06_only_owner_can_read_history(world):
    world["owner"].id += 999999
    assert world["client"].get(
        world["path"] + "/history"
    ).status_code == 404


def test_07_owner_can_enable(world):
    r = enable(world)
    assert r.json()["enabled"] is True
    assert r.json()["version"] == 1


def test_08_policy_persists(world):
    enable(world)
    r = world["client"].get(world["path"])
    assert r.json()["max_price_cents"] == 5000


def test_09_first_change_is_audited(world):
    enable(world)
    r = world["client"].get(
        world["path"] + "/history"
    )
    assert r.status_code == 200
    assert len(r.json()["history"]) == 1


def test_10_disabled_agent_cannot_plan(world):
    r = world["client"].post(
        world["path"] + "/check",
        json=proposal(),
    )
    assert r.status_code == 403


def test_11_enabled_agent_can_plan(world):
    enable(world)
    r = world["client"].post(
        world["path"] + "/check",
        json=proposal(),
    )
    assert r.status_code == 200
    assert r.json()["allowed"] is True
    assert r.json()["operation_executed"] is False


def test_12_price_limit_is_enforced(world):
    enable(world)
    r = world["client"].post(
        world["path"] + "/check",
        json=proposal(price=5001),
    )
    assert r.status_code == 403


def test_13_cost_limit_is_enforced(world):
    enable(world)
    r = world["client"].post(
        world["path"] + "/check",
        json=proposal(cost=801),
    )
    assert r.status_code == 403


def test_14_negative_price_is_invalid(world):
    enable(world)
    r = world["client"].post(
        world["path"] + "/check",
        json=proposal(price=-1),
    )
    assert r.status_code == 422


def test_15_extra_field_is_rejected(world):
    attempt = payload()
    attempt["owner_id"] = 999999
    r = world["client"].put(
        world["path"], json=attempt
    )
    assert r.status_code == 422


def test_16_stale_version_is_rejected(world):
    enable(world)
    r = world["client"].put(
        world["path"], json=payload(version=0)
    )
    assert r.status_code == 409


def test_17_owner_can_disable(world):
    enable(world)
    r = world["client"].put(
        world["path"],
        json=payload(version=1, enabled=False),
    )
    assert r.status_code == 200
    assert r.json()["enabled"] is False
    assert r.json()["version"] == 2


def test_18_disable_is_audited(world):
    enable(world)
    world["client"].put(
        world["path"],
        json=payload(version=1, enabled=False),
    )
    r = world["client"].get(
        world["path"] + "/history"
    )
    assert [
        item["version"]
        for item in r.json()["history"]
    ] == [2, 1]


def test_19_ledger_is_never_modified(world):
    with Session(world["engine"]) as db:
        before = db.scalar(
            select(func.count(LedgerTransaction.id))
        )

    enable(world)

    world["client"].post(
        world["path"] + "/check",
        json=proposal(),
    )

    with Session(world["engine"]) as db:
        after = db.scalar(
            select(func.count(LedgerTransaction.id))
        )

    assert before == after == 11


def test_20_unauthenticated_is_denied(world):
    world["app"].dependency_overrides.pop(
        get_current_user
    )
    r = world["client"].get(world["path"])
    assert r.status_code in (401, 403)


def test_21_inactive_owner_is_denied(world):
    world["owner"].is_active = False
    assert world["client"].get(
        world["path"]
    ).status_code == 401


def test_22_cost_cannot_exceed_price_limit(world):
    attempt = payload()
    attempt["max_price_cents"] = 100
    attempt["max_cost_cents"] = 500
    assert world["client"].put(
        world["path"], json=attempt
    ).status_code == 400


def test_23_no_write_methods_on_history(world):
    assert world["client"].post(
        world["path"] + "/history",
    ).status_code == 405


def test_24_unknown_agent_is_hidden(world):
    path = (
        "/api/v1/world/mine/"
        "999999999/autonomy"
    )
    assert world["client"].get(
        path
    ).status_code == 404


def test_25_failed_replay_creates_no_event(world):
    enable(world)
    world["client"].put(
        world["path"],
        json=payload(version=0),
    )

    with Session(world["engine"]) as db:
        assert db.scalar(
            select(func.count()).select_from(events)
        ) == 1


def test_26_no_policy_write_until_configured(world):
    world["client"].get(world["path"])

    with Session(world["engine"]) as db:
        assert db.scalar(
            select(func.count()).select_from(policies)
        ) == 0


def test_27_allows_planning_without_creating_contract(world):
    from app.services.world_contract_service import contracts

    with Session(world["engine"]) as db:
        before = db.scalar(
            select(func.count()).select_from(contracts)
        )

    enable(world)
    world["client"].post(
        world["path"] + "/check",
        json=proposal(),
    )

    with Session(world["engine"]) as db:
        after = db.scalar(
            select(func.count()).select_from(contracts)
        )

    assert before == after


def test_28_history_limit_is_respected(world):
    enable(world)
    world["client"].put(
        world["path"],
        json=payload(version=1, enabled=False),
    )

    r = world["client"].get(
        world["path"] + "/history?limit=1"
    )

    assert r.status_code == 200
    assert len(r.json()["history"]) == 1
    assert r.json()["history"][0]["version"] == 2
