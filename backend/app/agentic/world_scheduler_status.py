"""Estado local de los controladores por propietario.

No inicia hilos, negociaciones ni conexiones externas.
El estado pertenece exclusivamente al proceso actual.
"""

from threading import RLock

from app.agentic.world_autonomous_scheduler import (
    WorldAutonomousScheduler,
)

_lock = RLock()
_schedulers = {}


class WorldSchedulerRegistryError(ValueError):
    pass


def _owner(owner_id):
    if type(owner_id) is not int or owner_id <= 0:
        raise WorldSchedulerRegistryError(
            "Propietario invalido."
        )


def register_owner_scheduler(*, owner_id, scheduler):
    _owner(owner_id)

    if not isinstance(scheduler, WorldAutonomousScheduler):
        raise WorldSchedulerRegistryError(
            "Controlador invalido."
        )

    config = scheduler.config

    if (
        config.economy_mode != "simulation"
        or config.real_payments_enabled is not False
        or config.external_ai_enabled is not False
    ):
        raise WorldSchedulerRegistryError(
            "Solo se admite simulacion sin IA externa."
        )

    with _lock:
        existing = _schedulers.get(owner_id)

        if existing is not None and existing is not scheduler:
            raise WorldSchedulerRegistryError(
                "Ya existe un controlador registrado."
            )

        _schedulers[owner_id] = scheduler


def unregister_owner_scheduler(*, owner_id):
    _owner(owner_id)

    with _lock:
        scheduler = _schedulers.get(owner_id)

        if scheduler is None:
            return False

        if scheduler.running:
            raise WorldSchedulerRegistryError(
                "Detenga primero el controlador."
            )

        del _schedulers[owner_id]
        return True


def owner_scheduler_snapshot(owner_id):
    _owner(owner_id)

    with _lock:
        scheduler = _schedulers.get(owner_id)

    if scheduler is None:
        return {
            "status": "not_connected",
            "connected": False,
            "enabled": False,
            "running": False,
            "rounds_executed": 0,
            "rounds_failed": 0,
            "last_round_id": None,
            "scope": "current_process",
            "external_ai_active": False,
            "real_payments_active": False,
        }

    running = bool(scheduler.running)
    enabled = bool(scheduler.config.enabled)

    if running:
        status = "running"
    elif enabled:
        status = "stopped"
    else:
        status = "disabled"

    return {
        "status": status,
        "connected": True,
        "enabled": enabled,
        "running": running,
        "rounds_executed": scheduler.executed,
        "rounds_failed": scheduler.failed,
        "last_round_id": scheduler.last_round_id,
        "scope": "current_process",
        "external_ai_active": False,
        "real_payments_active": False,
    }
