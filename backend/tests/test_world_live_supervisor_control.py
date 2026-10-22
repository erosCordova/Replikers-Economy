"""Pruebas locales sin Gemini ni Supabase."""

from threading import Event

import pytest

from app.agentic.world_live_supervisor import (
    LiveSupervisorConfig,
    LiveSupervisorError,
    run_bounded,
)
from app.agentic.world_live_supervisor_control import (
    LiveSupervisorController,
)


@pytest.fixture
def authorized(monkeypatch):
    monkeypatch.setenv(
        "RW_LIVE_SUPERVISOR_OPT_IN", "1"
    )
    monkeypatch.setenv(
        "ECONOMY_MODE", "simulation"
    )
    monkeypatch.setenv(
        "REAL_PAYMENTS_ENABLED", "false"
    )
    monkeypatch.setenv(
        "RW_SUPERVISOR_BIND", "0"
    )


def test_01_inactive_by_default(authorized):
    calls = []

    controller = LiveSupervisorController(
        runner=lambda config, stop_event: calls.append(1)
    )

    assert controller.snapshot()["status"] == "idle"
    assert controller.snapshot()["running"] is False
    assert calls == []


def test_02_rejects_unauthorized_start(monkeypatch):
    monkeypatch.delenv(
        "RW_LIVE_SUPERVISOR_OPT_IN",
        raising=False,
    )

    controller = LiveSupervisorController(
        runner=lambda config, stop_event: None
    )

    with pytest.raises(LiveSupervisorError):
        controller.start()

    assert not controller.snapshot()["running"]


def test_03_cooperative_stop(authorized):
    entered = Event()

    def runner(config, stop_event):
        entered.set()
        stop_event.wait(timeout=3)

    controller = LiveSupervisorController(
        config=LiveSupervisorConfig(max_rounds=1),
        runner=runner,
    )

    assert controller.start()

    try:
        assert entered.wait(timeout=2)
        assert controller.snapshot()["running"]
    finally:
        assert controller.stop(timeout=2)

    state = controller.snapshot()

    assert not state["running"]
    assert state["status"] == "stopped"
    assert state["stop_requested"]


def test_04_no_duplicate_start(authorized):
    entered = Event()

    def runner(config, stop_event):
        entered.set()
        stop_event.wait(timeout=3)

    controller = LiveSupervisorController(
        runner=runner
    )

    assert controller.start()

    try:
        assert entered.wait(timeout=2)
        assert controller.start() is False
    finally:
        assert controller.stop(timeout=2)


def test_05_failure_recorded(authorized):
    entered = Event()

    def runner(config, stop_event):
        try:
            raise RuntimeError("Fallo simulado")
        finally:
            entered.set()

    controller = LiveSupervisorController(
        runner=runner
    )

    assert controller.start()
    assert entered.wait(timeout=2)
    assert controller.stop(timeout=2)

    state = controller.snapshot()

    assert state["status"] == "failed"
    assert state["executions_failed"] == 1
    assert state["last_error_type"] == "RuntimeError"


def test_06_direct_execution_blocked(monkeypatch):
    monkeypatch.delenv(
        "RW_LIVE_SUPERVISOR_OPT_IN",
        raising=False,
    )

    with pytest.raises(
        LiveSupervisorError,
        match="Autorizacion explicita",
    ):
        run_bounded(
            LiveSupervisorConfig(max_rounds=1)
        )


def test_07_invalid_runner():
    with pytest.raises(LiveSupervisorError):
        LiveSupervisorController(runner=123)


def test_08_production_rejected(
    authorized, monkeypatch
):
    monkeypatch.setenv(
        "ECONOMY_MODE", "production"
    )

    controller = LiveSupervisorController(
        runner=lambda config, stop_event: None
    )

    with pytest.raises(LiveSupervisorError):
        controller.start()


def test_09_invalid_stop_timeout():
    controller = LiveSupervisorController(
        runner=lambda config, stop_event: None
    )

    with pytest.raises(LiveSupervisorError):
        controller.stop(timeout=-1)


def test_10_stop_without_start():
    controller = LiveSupervisorController(
        runner=lambda config, stop_event: None
    )

    assert controller.stop(timeout=1)
    assert not controller.snapshot()["running"]
