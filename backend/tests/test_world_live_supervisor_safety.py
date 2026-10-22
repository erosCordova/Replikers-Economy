"""Pruebas del supervisor real, sin llamadas externas."""

import sys
from types import SimpleNamespace

import pytest

from app.agentic import world_live_supervisor as supervisor


def test_01_default_is_bounded():
    config = supervisor.LiveSupervisorConfig()
    assert config.max_rounds == 2
    assert config.max_agents == 1
    assert config.interval_seconds == 300
    assert config.agent_ids == (18, 19)


@pytest.mark.parametrize("rounds", [0, 4, True, -1])
def test_02_invalid_rounds(rounds):
    with pytest.raises(supervisor.LiveSupervisorError):
        supervisor.LiveSupervisorConfig(max_rounds=rounds)


@pytest.mark.parametrize("interval", [0, 59, 86401, True])
def test_03_invalid_interval(interval):
    with pytest.raises(supervisor.LiveSupervisorError):
        supervisor.LiveSupervisorConfig(
            interval_seconds=interval
        )


@pytest.mark.parametrize(
    "agents",
    [(18, 18), (18,), (18, True), (-1, 19)],
)
def test_04_invalid_agents(agents):
    with pytest.raises(supervisor.LiveSupervisorError):
        supervisor.LiveSupervisorConfig(agent_ids=agents)


def test_05_boolean_is_not_agent_count():
    with pytest.raises(supervisor.LiveSupervisorError):
        supervisor.LiveSupervisorConfig(max_agents=True)


def test_06_production_mode_rejected(monkeypatch):
    monkeypatch.setenv("ECONOMY_MODE", "production")
    monkeypatch.setenv("REAL_PAYMENTS_ENABLED", "false")
    monkeypatch.setenv("RW_SUPERVISOR_BIND", "0")

    with pytest.raises(supervisor.LiveSupervisorError):
        supervisor.verify_environment()


def test_07_real_payments_rejected(monkeypatch):
    monkeypatch.setenv("ECONOMY_MODE", "simulation")
    monkeypatch.setenv("REAL_PAYMENTS_ENABLED", "true")
    monkeypatch.setenv("RW_SUPERVISOR_BIND", "0")

    with pytest.raises(supervisor.LiveSupervisorError):
        supervisor.verify_environment()


def test_08_old_supervisor_conflict(monkeypatch):
    monkeypatch.setenv("ECONOMY_MODE", "simulation")
    monkeypatch.setenv("REAL_PAYMENTS_ENABLED", "false")
    monkeypatch.setenv("RW_SUPERVISOR_BIND", "1")

    with pytest.raises(supervisor.LiveSupervisorError):
        supervisor.verify_environment()


def test_09_plan_does_not_execute(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["world_live_supervisor", "--plan"],
    )
    monkeypatch.setenv(
        "RW_LIVE_SUPERVISOR_OPT_IN", "1"
    )

    def forbidden(config):
        pytest.fail("El plan nunca debe ejecutar rondas")

    monkeypatch.setattr(
        supervisor, "run_bounded", forbidden
    )

    supervisor.main()

    salida = capsys.readouterr().out
    assert "RESULTADO_GENERAL=PLAN_SEGURO" in salida


def test_10_run_requires_opt_in(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["world_live_supervisor", "--run"],
    )
    monkeypatch.delenv(
        "RW_LIVE_SUPERVISOR_OPT_IN",
        raising=False,
    )

    def forbidden(config):
        pytest.fail("Ejecucion sin autorizacion")

    monkeypatch.setattr(
        supervisor, "run_bounded", forbidden
    )

    supervisor.main()

    salida = capsys.readouterr().out

    assert (
        "EJECUCION_SIN_AUTORIZACION_BLOQUEADA"
        in salida
    )


def test_11_opt_in_is_explicit(monkeypatch):
    llamadas = []

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "world_live_supervisor",
            "--run",
            "--rounds", "1",
            "--interval", "60",
        ],
    )

    monkeypatch.setenv(
        "RW_LIVE_SUPERVISOR_OPT_IN", "1"
    )

    monkeypatch.setattr(
        supervisor,
        "run_bounded",
        lambda config: llamadas.append(config),
    )

    supervisor.main()

    assert len(llamadas) == 1
    assert llamadas[0].max_rounds == 1
    assert llamadas[0].interval_seconds == 60


def test_12_disabled_policy_is_rejected(monkeypatch):
    from app.services import world_autonomy_policy

    monkeypatch.setattr(
        world_autonomy_policy,
        "get_policy",
        lambda *args, **kwargs: {"enabled": False},
    )

    class FakeDB:
        def get(self, model, key):
            if model.__name__ == "User":
                return SimpleNamespace(is_active=True)

            return SimpleNamespace(
                owner_id=1,
                is_active=True,
                status="available",
            )

    with pytest.raises(
        supervisor.LiveSupervisorError,
        match="Autonomia desactivada",
    ):
        supervisor.verify_agents(
            FakeDB(),
            supervisor.LiveSupervisorConfig(),
        )


def test_13_foreign_agent_is_rejected(monkeypatch):
    class FakeDB:
        def get(self, model, key):
            if model.__name__ == "User":
                return SimpleNamespace(is_active=True)

            return SimpleNamespace(
                owner_id=999,
                is_active=True,
                status="available",
            )

    with pytest.raises(
        supervisor.LiveSupervisorError,
        match="Agente no disponible",
    ):
        supervisor.verify_agents(
            FakeDB(),
            supervisor.LiveSupervisorConfig(),
        )
