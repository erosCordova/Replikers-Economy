"""Pruebas con PostgreSQL simulado, sin red ni Gemini."""

from threading import Event
from types import SimpleNamespace

import pytest

from app.agentic import world_live_supervisor as supervisor
from app.agentic import world_idea_graph
from app.agentic import world_negotiation_graph
from app.agentic import world_event_runtime
from app.database import session
from app.services import economy_service


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class FakeDB:
    def __init__(self, state):
        self.state = state
        self._holds_transaction_lock = False

    def __enter__(self):
        self.state["opened"] += 1
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.state["closed"] += 1
        return False

    def get_bind(self):
        return SimpleNamespace(
            dialect=SimpleNamespace(name="postgresql")
        )

    def execute(self, statement, parameters=None):
        sql = str(statement)

        if "SET TRANSACTION READ ONLY" in sql:
            self.state["read_only_transactions"] += 1
            return FakeResult(None)

        if "pg_try_advisory_xact_lock" in sql:
            self.state["lock_attempts"] += 1
            acquired = self.state["lock_granted"]
            self._holds_transaction_lock = acquired
            return FakeResult(acquired)

        if "pg_advisory_unlock" in sql:
            raise AssertionError(
                "No se permite desbloqueo manual"
            )

        raise AssertionError(
            "Consulta inesperada en simulacion"
        )

    def rollback(self):
        self.state["rollbacks"] += 1

        if self._holds_transaction_lock:
            self.state["lock_releases"] += 1
            self._holds_transaction_lock = False


def configure(
    monkeypatch,
    *,
    lock_granted=True,
    fail_idea=False,
    fail_round=False,
    stop_event=None,
):
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

    state = {
        "opened": 0,
        "closed": 0,
        "rollbacks": 0,
        "lock_attempts": 0,
        "lock_granted": lock_granted,
        "lock_releases": 0,
        "read_only_transactions": 0,
        "policy_checks": 0,
        "idea_builds": 0,
        "response_builds": 0,
        "rounds": 0,
    }

    def fake_sessions():
        return FakeDB(state)

    def fake_policy(db, config):
        state["policy_checks"] += 1

    def fake_idea(*args, **kwargs):
        state["idea_builds"] += 1
        if fail_idea:
            raise RuntimeError(
                "Fallo simulado del proveedor"
            )
        return lambda context: {}

    def fake_response(*args, **kwargs):
        state["response_builds"] += 1
        return lambda context: {}

    def fake_round(db, **kwargs):
        state["rounds"] += 1

        if fail_round:
            raise RuntimeError(
                "Fallo simulado durante la ronda"
            )

        if stop_event is not None:
            stop_event.set()

        return {
            "results": [],
            "events_inserted": 0,
            "payments_executed": False,
            "real_money_used": False,
        }

    monkeypatch.setattr(
        session,
        "SessionLocal",
        fake_sessions,
    )
    monkeypatch.setattr(
        supervisor,
        "verify_agents",
        fake_policy,
    )
    monkeypatch.setattr(
        economy_service,
        "ensure_simulation_mode",
        lambda: None,
    )
    monkeypatch.setattr(
        world_idea_graph,
        "make_gemini_idea_engine",
        fake_idea,
    )
    monkeypatch.setattr(
        world_negotiation_graph,
        "make_gemini_response_engine",
        fake_response,
    )
    monkeypatch.setattr(
        world_event_runtime,
        "run_logged_governed_round",
        fake_round,
    )

    return state


def test_01_duplicate_execution_is_blocked(monkeypatch):
    state = configure(
        monkeypatch,
        lock_granted=False,
    )

    with pytest.raises(
        supervisor.LiveSupervisorError,
        match="otra ejecucion",
    ):
        supervisor.run_bounded(
            supervisor.LiveSupervisorConfig(
                max_rounds=1,
            )
        )

    assert state["lock_attempts"] == 1
    assert state["rounds"] == 0
    assert state["idea_builds"] == 0
    assert state["response_builds"] == 0
    assert state["closed"] == 1


def test_02_success_releases_database_lock(monkeypatch):
    state = configure(monkeypatch)

    supervisor.run_bounded(
        supervisor.LiveSupervisorConfig(
            max_rounds=1,
        )
    )

    assert state["lock_attempts"] == 1
    assert state["lock_releases"] == 1
    assert state["rounds"] == 1
    assert state["policy_checks"] == 2
    assert state["opened"] == state["closed"]


def test_03_gemini_initialization_failure_unlocks(
    monkeypatch,
):
    state = configure(
        monkeypatch,
        fail_idea=True,
    )

    with pytest.raises(
        RuntimeError,
        match="proveedor",
    ):
        supervisor.run_bounded(
            supervisor.LiveSupervisorConfig(
                max_rounds=1,
            )
        )

    assert state["lock_releases"] == 1
    assert state["rounds"] == 0
    assert state["opened"] == state["closed"]


def test_04_round_failure_rolls_back_and_unlocks(
    monkeypatch,
):
    state = configure(
        monkeypatch,
        fail_round=True,
    )

    with pytest.raises(
        RuntimeError,
        match="durante la ronda",
    ):
        supervisor.run_bounded(
            supervisor.LiveSupervisorConfig(
                max_rounds=1,
            )
        )

    assert state["rounds"] == 1
    assert state["rollbacks"] >= 2
    assert state["lock_releases"] == 1
    assert state["opened"] == state["closed"]


def test_05_stop_prevents_additional_rounds(
    monkeypatch,
):
    stop = Event()

    state = configure(
        monkeypatch,
        stop_event=stop,
    )

    supervisor.run_bounded(
        supervisor.LiveSupervisorConfig(
            max_rounds=3,
            interval_seconds=60,
        ),
        stop_event=stop,
    )

    assert stop.is_set()
    assert state["rounds"] == 1
    assert state["lock_releases"] == 1
    assert state["opened"] == state["closed"]


def test_06_transaction_lock_is_read_only(monkeypatch):
    state = configure(monkeypatch)

    supervisor.run_bounded(
        supervisor.LiveSupervisorConfig(
            max_rounds=1,
        )
    )

    assert state["read_only_transactions"] == 1
    assert state["lock_attempts"] == 1
    assert state["lock_releases"] == 1
    assert state["opened"] == state["closed"]
