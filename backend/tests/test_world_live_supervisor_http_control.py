"""Control HTTP aislado sin Gemini ni Supabase."""

from threading import Event
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_db
from app.agentic.world_live_supervisor import LiveSupervisorConfig
from app.agentic.world_live_supervisor_control import (
    LiveSupervisorController,
)
from app.api.routes import world_live_supervisor_http as control


class FakeDB:
    def rollback(self):
        pass


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(control, "_pilot_used", False)
    monkeypatch.setattr(control, "_controller", None)
    monkeypatch.setattr(
        control, "settings",
        SimpleNamespace(ENVIRONMENT="development"),
    )
    monkeypatch.setattr(
        control, "verify_agents",
        lambda db, config: None,
    )
    monkeypatch.setenv("ECONOMY_MODE", "simulation")
    monkeypatch.setenv("REAL_PAYMENTS_ENABLED", "false")
    monkeypatch.setenv("RW_SUPERVISOR_BIND", "0")
    monkeypatch.delenv(
        "RW_LIVE_SUPERVISOR_HTTP_ENABLED",
        raising=False,
    )
    monkeypatch.delenv(
        "RW_LIVE_SUPERVISOR_OPT_IN",
        raising=False,
    )

    yield

    current = control._controller

    if current is not None:
        assert current.stop(timeout=2)

    control._controller = None


def client_as(user):
    app = FastAPI()
    app.include_router(control.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: FakeDB()
    return TestClient(app)


def enable_test(monkeypatch):
    monkeypatch.setenv(
        "RW_LIVE_SUPERVISOR_HTTP_ENABLED", "1"
    )
    monkeypatch.setenv(
        "RW_LIVE_SUPERVISOR_OPT_IN", "1"
    )


def test_01_read_only_status():
    with client_as(
        SimpleNamespace(id=1, is_active=True)
    ) as client:
        response = client.get(
            "/api/v1/world/scheduler/live/control/mine"
        )

    assert response.status_code == 200
    assert response.json()["running"] is False
    assert control._controller is None


def test_02_start_blocked_by_default():
    with client_as(
        SimpleNamespace(id=1, is_active=True)
    ) as client:
        response = client.post(
            "/api/v1/world/scheduler/live/control/mine/start"
        )

    assert response.status_code == 403
    assert control._controller is None


def test_03_foreign_owner_denied(monkeypatch):
    enable_test(monkeypatch)

    with client_as(
        SimpleNamespace(id=2, is_active=True)
    ) as client:
        response = client.post(
            "/api/v1/world/scheduler/live/control/mine/start"
        )

    assert response.status_code == 403


def test_04_inactive_owner_denied():
    with client_as(
        SimpleNamespace(id=1, is_active=False)
    ) as client:
        response = client.get(
            "/api/v1/world/scheduler/live/control/mine"
        )

    assert response.status_code == 401


def test_05_start_stop_with_fake_runner(monkeypatch):
    enable_test(monkeypatch)
    entered = Event()

    def fake_runner(config, *, stop_event):
        entered.set()
        stop_event.wait(timeout=2)

    control._controller = LiveSupervisorController(
        config=LiveSupervisorConfig(),
        runner=fake_runner,
    )

    with client_as(
        SimpleNamespace(id=1, is_active=True)
    ) as client:
        start = client.post(
            "/api/v1/world/scheduler/live/control/mine/start"
        )

        assert start.status_code == 200
        assert start.json()["started"] is True
        assert entered.wait(timeout=1)

        status = client.get(
            "/api/v1/world/scheduler/live/control/mine"
        )
        assert status.json()["running"] is True

        stop = client.post(
            "/api/v1/world/scheduler/live/control/mine/stop"
        )
        assert stop.status_code == 200
        assert stop.json()["stopped"] is True


def test_06_duplicate_start_rejected(monkeypatch):
    enable_test(monkeypatch)
    entered = Event()

    def fake_runner(config, *, stop_event):
        entered.set()
        stop_event.wait(timeout=2)

    control._controller = LiveSupervisorController(
        runner=fake_runner
    )

    with client_as(
        SimpleNamespace(id=1, is_active=True)
    ) as client:
        first = client.post(
            "/api/v1/world/scheduler/live/control/mine/start"
        )
        assert first.status_code == 200
        assert entered.wait(timeout=1)

        second = client.post(
            "/api/v1/world/scheduler/live/control/mine/start"
        )
        assert second.status_code == 409

        client.post(
            "/api/v1/world/scheduler/live/control/mine/stop"
        )


def test_07_production_start_rejected(monkeypatch):
    enable_test(monkeypatch)

    monkeypatch.setattr(
        control, "settings",
        SimpleNamespace(ENVIRONMENT="production"),
    )

    with client_as(
        SimpleNamespace(id=1, is_active=True)
    ) as client:
        response = client.post(
            "/api/v1/world/scheduler/live/control/mine/start"
        )

    assert response.status_code == 403



def test_08_pilot_has_exactly_one_round():
    account = SimpleNamespace(
        id=1,
        is_active=True,
    )

    config = control._owner(account)

    assert config.max_rounds == 1


def test_09_pilot_rejects_second_start(monkeypatch):
    enable_test(monkeypatch)

    entered = Event()

    def fake_runner(config, *, stop_event):
        entered.set()
        stop_event.wait(timeout=2)

    config = control._owner(
        SimpleNamespace(id=1, is_active=True)
    )

    control._controller = LiveSupervisorController(
        config=config,
        runner=fake_runner,
    )

    base = (
        "/api/v1/world/scheduler/"
        "live/control/mine"
    )

    with client_as(
        SimpleNamespace(id=1, is_active=True)
    ) as client:

        first = client.post(base + "/start")

        assert first.status_code == 200
        assert first.json()["started"] is True
        assert first.json()["pilot_used"] is True
        assert entered.wait(timeout=1)

        stopped = client.post(base + "/stop")

        assert stopped.status_code == 200
        assert control._controller.stop(timeout=2)

        second = client.post(base + "/start")

        assert second.status_code == 409

        status = client.get(base)

        assert status.status_code == 200
        assert status.json()["pilot_used"] is True
        assert status.json()["running"] is False
