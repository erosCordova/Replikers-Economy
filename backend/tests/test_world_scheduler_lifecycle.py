"""Pruebas del ciclo de vida sin Gemini ni Supabase."""

import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url

from app.auth.dependencies import get_current_user
from app.api.routes.world_scheduler_status import router
from app.agentic.world_scheduler_lifecycle import (
    WorldSchedulerLifecycleError,
    configured_world_scheduler_lifecycle,
)
from app.agentic.world_scheduler_status import (
    owner_scheduler_snapshot,
)


@pytest.fixture
def local_engine(tmp_path):
    folder = tmp_path / "replikers-world-backups"
    folder.mkdir()

    path = folder / "rw_bridge_0123456789abcdef.db"

    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY
            );
            CREATE TABLE replikers (
                id INTEGER PRIMARY KEY,
                owner_id INTEGER,
                is_active INTEGER
            );
            CREATE TABLE world_agent_events (
                id INTEGER PRIMARY KEY
            );
            CREATE TABLE world_agent_memories (
                id INTEGER PRIMARY KEY
            );
            CREATE TABLE world_agent_autonomy_policies (
                id INTEGER PRIMARY KEY
            );
            CREATE TABLE ledger_transactions (
                id INTEGER PRIMARY KEY
            );
            INSERT INTO users VALUES (701);
            INSERT INTO replikers VALUES (1,701,1);
            INSERT INTO replikers VALUES (2,701,1);
        """)

    engine = create_engine(
        URL.create("sqlite", database=str(path))
    )

    yield engine

    engine.dispose()


def enable(monkeypatch, owner="701"):
    monkeypatch.setenv("RW_SUPERVISOR_BIND", "1")
    monkeypatch.setenv("RW_SUPERVISOR_OWNER_ID", owner)
    monkeypatch.setenv("ECONOMY_MODE", "simulation")
    monkeypatch.setenv("REAL_PAYMENTS_ENABLED", "false")


def test_01_disabled_by_default(monkeypatch, local_engine):
    monkeypatch.delenv("RW_SUPERVISOR_BIND", raising=False)

    with configured_world_scheduler_lifecycle(
        local_engine, "development"
    ) as scheduler:
        assert scheduler is None

    assert owner_scheduler_snapshot(701)["connected"] is False


def test_02_registered_and_cleaned(monkeypatch, local_engine):
    enable(monkeypatch)

    with configured_world_scheduler_lifecycle(
        local_engine, "development"
    ) as scheduler:
        assert scheduler is not None
        assert scheduler.running is False

        data = owner_scheduler_snapshot(701)
        assert data["connected"] is True
        assert data["status"] == "stopped"
        assert data["rounds_executed"] == 0

    assert owner_scheduler_snapshot(701)["connected"] is False


def test_03_unknown_owner_rejected(monkeypatch, local_engine):
    enable(monkeypatch, owner="702")

    with pytest.raises(WorldSchedulerLifecycleError):
        with configured_world_scheduler_lifecycle(
            local_engine, "development"
        ):
            pass

    assert owner_scheduler_snapshot(702)["connected"] is False


def test_04_production_rejected(monkeypatch, local_engine):
    enable(monkeypatch)

    with pytest.raises(WorldSchedulerLifecycleError):
        with configured_world_scheduler_lifecycle(
            local_engine, "production"
        ):
            pass


def test_05_postgresql_rejected(monkeypatch):
    enable(monkeypatch)

    fake_engine = SimpleNamespace(
        url=make_url(
            "postgresql+psycopg://user:password@localhost/db"
        )
    )

    with pytest.raises(WorldSchedulerLifecycleError):
        with configured_world_scheduler_lifecycle(
            fake_engine, "development"
        ):
            pass


def test_06_wrong_sqlite_filename_rejected(
    monkeypatch, tmp_path
):
    enable(monkeypatch)

    folder = tmp_path / "replikers-world-backups"
    folder.mkdir()

    path = folder / "replikers.db"

    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE users(id INTEGER PRIMARY KEY)")

    engine = create_engine(
        URL.create("sqlite", database=str(path))
    )

    try:
        with pytest.raises(WorldSchedulerLifecycleError):
            with configured_world_scheduler_lifecycle(
                engine, "development"
            ):
                pass
    finally:
        engine.dispose()


def test_07_real_payment_setting_rejected(
    monkeypatch, local_engine
):
    enable(monkeypatch)
    monkeypatch.setenv("REAL_PAYMENTS_ENABLED", "true")

    with pytest.raises(WorldSchedulerLifecycleError):
        with configured_world_scheduler_lifecycle(
            local_engine, "development"
        ):
            pass


def test_08_fastapi_startup_shutdown(
    monkeypatch, local_engine
):
    enable(monkeypatch)

    @asynccontextmanager
    async def lifespan(app):
        with configured_world_scheduler_lifecycle(
            local_engine, "development"
        ):
            yield

    app = FastAPI(lifespan=lifespan)
    app.include_router(router, prefix="/api/v1")

    app.dependency_overrides[get_current_user] = (
        lambda: SimpleNamespace(id=701)
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/world/scheduler/mine"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["connected"] is True
        assert data["status"] == "stopped"
        assert data["running"] is False
        assert data["rounds_executed"] == 0

    assert owner_scheduler_snapshot(701)["connected"] is False
