"""Pruebas del controlador, sin internet ni operaciones economicas."""
from threading import Event, Thread
import pytest
from app.agentic.world_autonomous_scheduler import (
    WorldAutonomousScheduler,
    WorldScheduleConfig,
    WorldSchedulerError,
)

DB = "sqlite:////tmp/world_isolated_test.db"

def configuration(**overrides):
    args = {"database_url": DB, "enabled": True}
    args.update(overrides)
    return WorldScheduleConfig(**args)

def scheduler(runner=lambda **kw: {}):
    return WorldAutonomousScheduler(
        config=configuration(),
        runner=runner,
    )

def test_01_disabled_by_default():
    config = WorldScheduleConfig(database_url=DB)
    value = WorldAutonomousScheduler(
        config=config,
        runner=lambda **kw: {},
    )
    assert value.run_once()["status"] == "disabled"
    with pytest.raises(WorldSchedulerError):
        value.start()

def test_02_requires_simulation():
    with pytest.raises(WorldSchedulerError):
        configuration(economy_mode="production")

def test_03_rejects_postgresql():
    with pytest.raises(WorldSchedulerError):
        configuration(database_url="postgresql://server/database")

def test_04_rejects_real_payments():
    with pytest.raises(WorldSchedulerError):
        configuration(real_payments_enabled=True)

def test_05_rejects_external_ai():
    with pytest.raises(WorldSchedulerError):
        configuration(external_ai_enabled=True)

def test_06_validates_agents_and_interval():
    with pytest.raises(WorldSchedulerError):
        configuration(max_agents=4)
    with pytest.raises(WorldSchedulerError):
        configuration(interval_seconds=1)

def test_07_unique_round_ids():
    seen = []

    def runner(**kwargs):
        seen.append(kwargs)
        return {"results": []}

    value = scheduler(runner)
    first = value.run_once()
    second = value.run_once()

    assert first["status"] == "executed"
    assert second["status"] == "executed"
    assert first["round_id"] != second["round_id"]
    assert all(item["max_agents"] == 1 for item in seen)
    assert value.executed == 2

def test_08_prevents_simultaneous_runs():
    entered = Event()
    release = Event()
    observed = []

    def runner(**kwargs):
        entered.set()
        assert release.wait(timeout=5)
        return {}

    value = scheduler(runner)
    worker = Thread(
        target=lambda: observed.append(value.run_once())
    )
    worker.start()

    try:
        assert entered.wait(timeout=5)
        assert value.run_once()["status"] == "busy"
    finally:
        release.set()
        worker.join(timeout=5)

    assert not worker.is_alive()
    assert observed[0]["status"] == "executed"

def test_09_errors_release_lock():
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError("Prueba")
        return {"ok": True}

    value = scheduler(runner)

    assert value.run_once()["status"] == "error"
    assert value.run_once()["status"] == "executed"
    assert value.failed == 1
    assert value.executed == 1

def test_10_start_and_stop():
    entered = Event()

    def runner(**kwargs):
        entered.set()
        return {}

    value = scheduler(runner)

    try:
        assert value.start() is True
        assert entered.wait(timeout=5)
        assert value.start() is False
    finally:
        assert value.stop(timeout=5)

    assert value.running is False
