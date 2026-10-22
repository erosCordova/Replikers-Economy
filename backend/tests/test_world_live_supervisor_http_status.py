"""Estado HTTP del supervisor Gemini, sin conectarse a BD."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.api.routes.world_scheduler_status import router


def client_as(user):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_01_blocked_by_default(monkeypatch):
    monkeypatch.delenv(
        "RW_LIVE_SUPERVISOR_OPT_IN", raising=False
    )

    with client_as(
        SimpleNamespace(id=1, is_active=True)
    ) as client:
        response = client.get(
            "/api/v1/world/scheduler/live/mine"
        )

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert response.json()["running"] is False
    assert response.json()["start_endpoint_available"] is False
    assert "no-store" in response.headers["cache-control"]


def test_02_configured_but_inactive(monkeypatch):
    monkeypatch.setenv(
        "RW_LIVE_SUPERVISOR_OPT_IN", "1"
    )
    monkeypatch.setenv("ECONOMY_MODE", "simulation")
    monkeypatch.setenv("REAL_PAYMENTS_ENABLED", "false")
    monkeypatch.setenv("RW_SUPERVISOR_BIND", "0")

    with client_as(
        SimpleNamespace(id=1, is_active=True)
    ) as client:
        response = client.get(
            "/api/v1/world/scheduler/live/mine"
        )

    assert response.status_code == 200
    assert response.json()["status"] == "configured_inactive"
    assert response.json()["running"] is False


def test_03_foreign_owner_denied(monkeypatch):
    with client_as(
        SimpleNamespace(id=2, is_active=True)
    ) as client:
        response = client.get(
            "/api/v1/world/scheduler/live/mine"
        )

    assert response.status_code == 403


def test_04_inactive_account_denied(monkeypatch):
    with client_as(
        SimpleNamespace(id=1, is_active=False)
    ) as client:
        response = client.get(
            "/api/v1/world/scheduler/live/mine"
        )

    assert response.status_code == 401
