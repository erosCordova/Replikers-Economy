"""Pruebas aisladas del supervisor autenticado."""

from threading import Event
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.api.routes.world_scheduler_status import router
from app.agentic.world_autonomous_scheduler import (
    WorldAutonomousScheduler,
    WorldScheduleConfig,
)
from app.agentic.world_scheduler_status import (
    WorldSchedulerRegistryError,
    owner_scheduler_snapshot,
    register_owner_scheduler,
    unregister_owner_scheduler,
)


def scheduler_factory(runner=None):
    return WorldAutonomousScheduler(
        config=WorldScheduleConfig(
            database_url="sqlite:////tmp/world_status_test.db",
            enabled=True,
            max_agents=1,
            interval_seconds=600,
        ),
        runner=runner or (lambda **kwargs: {}),
    )


def client_for(owner_id):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    app.dependency_overrides[get_current_user] = (
        lambda: SimpleNamespace(id=owner_id)
    )

    return TestClient(app)


def test_01_unconnected():
    with client_for(701) as client:
        response = client.get(
            "/api/v1/world/scheduler/mine"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "not_connected"
    assert data["connected"] is False
    assert data["running"] is False
    assert data["rounds_executed"] == 0
    assert data["scope"] == "current_process"


def test_02_registered_stopped():
    scheduler = scheduler_factory()

    register_owner_scheduler(
        owner_id=702,
        scheduler=scheduler,
    )

    try:
        with client_for(702) as client:
            data = client.get(
                "/api/v1/world/scheduler/mine"
            ).json()

        assert data["status"] == "stopped"
        assert data["connected"] is True
        assert data["running"] is False

    finally:
        unregister_owner_scheduler(owner_id=702)


def test_03_execution_counters():
    scheduler = scheduler_factory()

    register_owner_scheduler(
        owner_id=703,
        scheduler=scheduler,
    )

    try:
        result = scheduler.run_once()

        assert result["status"] == "executed"

        with client_for(703) as client:
            data = client.get(
                "/api/v1/world/scheduler/mine"
            ).json()

        assert data["rounds_executed"] == 1
        assert data["rounds_failed"] == 0
        assert data["last_round_id"] == result["round_id"]

    finally:
        unregister_owner_scheduler(owner_id=703)


def test_04_failed_execution():
    def fail(**kwargs):
        raise RuntimeError("SIMULATED_ERROR")

    scheduler = scheduler_factory(fail)

    register_owner_scheduler(
        owner_id=704,
        scheduler=scheduler,
    )

    try:
        assert scheduler.run_once()["status"] == "error"

        with client_for(704) as client:
            data = client.get(
                "/api/v1/world/scheduler/mine"
            ).json()

        assert data["rounds_executed"] == 0
        assert data["rounds_failed"] == 1

    finally:
        unregister_owner_scheduler(owner_id=704)


def test_05_other_owner_isolated():
    scheduler = scheduler_factory()

    register_owner_scheduler(
        owner_id=705,
        scheduler=scheduler,
    )

    try:
        scheduler.run_once()

        with client_for(706) as client:
            data = client.get(
                "/api/v1/world/scheduler/mine"
            ).json()

        assert data["connected"] is False
        assert data["rounds_executed"] == 0
        assert data["last_round_id"] is None

    finally:
        unregister_owner_scheduler(owner_id=705)


def test_06_authentication_required():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    def deny():
        raise HTTPException(status_code=401)

    app.dependency_overrides[get_current_user] = deny

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/world/scheduler/mine"
        )

    assert response.status_code == 401


def test_07_invalid_or_duplicate_registration():
    first = scheduler_factory()
    second = scheduler_factory()

    with pytest.raises(WorldSchedulerRegistryError):
        register_owner_scheduler(
            owner_id=-1,
            scheduler=first,
        )

    register_owner_scheduler(
        owner_id=707,
        scheduler=first,
    )

    try:
        with pytest.raises(WorldSchedulerRegistryError):
            register_owner_scheduler(
                owner_id=707,
                scheduler=second,
            )

        assert owner_scheduler_snapshot(707)["connected"]

    finally:
        unregister_owner_scheduler(owner_id=707)


def test_08_running_state():
    entered = Event()
    release = Event()

    def runner(**kwargs):
        entered.set()
        assert release.wait(timeout=5)
        return {}

    scheduler = scheduler_factory(runner)

    register_owner_scheduler(
        owner_id=708,
        scheduler=scheduler,
    )

    try:
        assert scheduler.start() is True
        assert entered.wait(timeout=5)

        with client_for(708) as client:
            data = client.get(
                "/api/v1/world/scheduler/mine"
            ).json()

        assert data["status"] == "running"
        assert data["running"] is True

    finally:
        release.set()
        assert scheduler.stop(timeout=5)
        unregister_owner_scheduler(owner_id=708)
