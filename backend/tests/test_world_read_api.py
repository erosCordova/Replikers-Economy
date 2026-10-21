
"""Pruebas de aislamiento de propietarios World."""

import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.models.repliker import Repliker
from app.models.economy import LedgerTransaction
from app.auth.dependencies import get_current_user
from app.services.world_access_service import (
    require_active_owner,
    require_owned_repliker,
)
from app.api.routes import world_read


@pytest.fixture
def setup_world(tmp_path):
    origin = Path(
        os.environ["REPLIKERS_WORLD_TEST_DB"]
    )
    target = tmp_path / "protected_world.db"

    with sqlite3.connect(
        origin.resolve().as_uri() + "?mode=ro",
        uri=True,
    ) as source:
        with sqlite3.connect(str(target)) as destination:
            source.backup(destination)

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

        owner_id = int(actor.owner_id)
        actor_id = actor.id

    principal = SimpleNamespace(
        id=owner_id,
        is_active=True,
    )

    app = FastAPI()
    app.include_router(
        world_read.router,
        prefix="/api/v1",
    )

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[
        world_read.get_db
    ] = override_db

    app.dependency_overrides[
        get_current_user
    ] = lambda: principal

    client = TestClient(app)

    try:
        yield {
            "app": app,
            "client": client,
            "principal": principal,
            "actor_id": actor_id,
            "engine": engine,
        }
    finally:
        client.close()
        engine.dispose()


def owner_path(fixture, suffix=""):
    return (
        "/api/v1/world/mine/"
        + str(fixture["actor_id"])
        + suffix
    )


def stranger(fixture):
    fixture["principal"].id += 1000000


def test_01_owner_can_list_agents(setup_world):
    response = setup_world["client"].get(
        "/api/v1/world/mine"
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


def test_02_owner_can_read_own_agent(setup_world):
    response = setup_world["client"].get(
        owner_path(setup_world)
    )
    assert response.status_code == 200
    assert response.json()["repliker_id"] == (
        setup_world["actor_id"]
    )


def test_03_owner_can_read_own_balance(setup_world):
    response = setup_world["client"].get(
        owner_path(setup_world)
    )
    assert response.status_code == 200
    assert response.json()["wallet"]["currency"] == "RCR"


def test_04_stranger_cannot_read_agent(setup_world):
    stranger(setup_world)
    response = setup_world["client"].get(
        owner_path(setup_world)
    )
    assert response.status_code == 404


def test_05_stranger_cannot_read_economy(setup_world):
    stranger(setup_world)
    response = setup_world["client"].get(
        owner_path(setup_world, "/economy")
    )
    assert response.status_code == 404


def test_06_stranger_cannot_read_memories(setup_world):
    stranger(setup_world)
    response = setup_world["client"].get(
        owner_path(setup_world, "/memories")
    )
    assert response.status_code == 404


def test_07_stranger_cannot_read_negotiations(setup_world):
    stranger(setup_world)
    response = setup_world["client"].get(
        owner_path(setup_world, "/negotiations")
    )
    assert response.status_code == 404


def test_08_stranger_list_is_empty(setup_world):
    stranger(setup_world)
    response = setup_world["client"].get(
        "/api/v1/world/mine"
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_09_owner_can_read_memories(setup_world):
    response = setup_world["client"].get(
        owner_path(setup_world, "/memories")
    )
    assert response.status_code == 200
    assert isinstance(
        response.json()["memories"],
        list,
    )


def test_10_owner_can_read_negotiations(setup_world):
    response = setup_world["client"].get(
        owner_path(setup_world, "/negotiations")
    )
    assert response.status_code == 200
    assert isinstance(
        response.json()["negotiations"],
        list,
    )


def test_11_public_strategies_exclude_private_data(setup_world):
    response = setup_world["client"].get(
        "/api/v1/world/public-strategies"
    )
    assert response.status_code == 200

    for item in response.json()["strategies"]:
        assert "balance_cents" not in item
        assert "password_hash" not in item
        assert "past_negotiations" not in item


def test_12_inactive_user_is_denied(setup_world):
    setup_world["principal"].is_active = False

    response = setup_world["client"].get(
        "/api/v1/world/mine"
    )
    assert response.status_code == 401


def test_13_unauthenticated_is_denied(setup_world):
    setup_world["app"].dependency_overrides.pop(
        get_current_user
    )

    response = setup_world["client"].get(
        "/api/v1/world/mine"
    )
    assert response.status_code in (401, 403)


def test_14_queries_never_modify_ledger(setup_world):
    with Session(setup_world["engine"]) as db:
        before = db.scalar(
            select(func.count(LedgerTransaction.id))
        )

    paths = (
        "/api/v1/world/mine",
        owner_path(setup_world),
        owner_path(setup_world, "/economy"),
        owner_path(setup_world, "/memories"),
        owner_path(setup_world, "/negotiations"),
        "/api/v1/world/public-strategies",
    )

    for path in paths:
        response = setup_world["client"].get(path)
        assert response.status_code == 200

    with Session(setup_world["engine"]) as db:
        after = db.scalar(
            select(func.count(LedgerTransaction.id))
        )

    assert before == after


def test_15_inactive_agent_is_rejected():
    class FakeDB:
        def get(self, model, actor_id):
            return SimpleNamespace(
                id=actor_id,
                owner_id=7,
                is_active=False,
            )

    principal = SimpleNamespace(
        id=7,
        is_active=True,
    )

    with pytest.raises(HTTPException) as exc:
        require_owned_repliker(
            FakeDB(),
            principal,
            1,
        )

    assert exc.value.status_code == 403


def test_16_no_payment_routes_are_exposed(setup_world):
    """Verificar el router real y los metodos HTTP.

    Algunas versiones de FastAPI exponen contenedores
    internos en app.routes. El router World conserva
    directamente las definiciones verificables.
    """

    expected = {
        "/world/mine",
        "/world/mine/{repliker_id}",
        "/world/mine/{repliker_id}/economy",
        "/world/mine/{repliker_id}/memories",
        "/world/mine/{repliker_id}/negotiations",
        "/world/public-strategies",
    }

    routes = [
        route
        for route in world_read.router.routes
        if isinstance(
            getattr(route, "path", None),
            str,
        )
    ]

    actual = {
        route.path
        for route in routes
    }

    assert actual == expected
    assert len(routes) == 6

    for route in routes:
        methods = set(route.methods)

        assert "GET" in methods
        assert methods <= {"GET", "HEAD"}

    client = setup_world["client"]
    actor_id = setup_world["actor_id"]

    for path in sorted(expected):
        full_path = "/api/v1" + path.replace(
            "{repliker_id}", str(actor_id)
        )

        response = client.get(full_path)
        assert response.status_code == 200, (
            full_path,
            response.status_code,
        )

        for method in ("POST", "PUT", "PATCH", "DELETE"):
            response = client.request(
                method,
                full_path,
            )

            assert response.status_code in (404, 405), (
                method,
                full_path,
                response.status_code,
            )
