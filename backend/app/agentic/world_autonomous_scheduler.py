"""Controlador opt-in de rondas World: no se inicia al importarse."""
from dataclasses import dataclass
from threading import Event, Lock, Thread, current_thread
from typing import Callable
from uuid import uuid4

_PROCESS_ROUND_LOCK = Lock()

class WorldSchedulerError(ValueError):
    pass

@dataclass(frozen=True)
class WorldScheduleConfig:
    database_url: str
    enabled: bool = False
    economy_mode: str = "simulation"
    real_payments_enabled: bool = False
    external_ai_enabled: bool = False
    max_agents: int = 1
    interval_seconds: int = 600

    def __post_init__(self):
        if not isinstance(self.database_url, str) or not self.database_url.startswith("sqlite:///"):
            raise WorldSchedulerError("Solo se admite SQLite aislado.")
        if self.economy_mode != "simulation":
            raise WorldSchedulerError("Modo economico no permitido.")
        if self.real_payments_enabled is not False:
            raise WorldSchedulerError("Los pagos reales estan prohibidos.")
        if self.external_ai_enabled is not False:
            raise WorldSchedulerError("La IA externa requiere otra integracion.")
        if type(self.enabled) is not bool:
            raise WorldSchedulerError("enabled debe ser booleano.")
        if type(self.max_agents) is not int or not 1 <= self.max_agents <= 3:
            raise WorldSchedulerError("Cantidad de agentes invalida.")
        if type(self.interval_seconds) is not int or not 60 <= self.interval_seconds <= 86400:
            raise WorldSchedulerError("Intervalo permitido: 60 a 86400 segundos.")

class WorldAutonomousScheduler:
    """Ejecutor secuencial con runner inyectado, desactivado por defecto."""

    def __init__(self, *, config: WorldScheduleConfig, runner: Callable):
        if not callable(runner):
            raise WorldSchedulerError("Se necesita un ejecutor valido.")
        self.config = config
        self.runner = runner
        self._stop = Event()
        self._thread = None
        self._lifecycle_lock = Lock()
        self.executed = 0
        self.failed = 0
        self.last_round_id = None

    def run_once(self):
        if not self.config.enabled:
            return {"status": "disabled"}
        if not _PROCESS_ROUND_LOCK.acquire(blocking=False):
            return {"status": "busy"}

        round_id = "world_auto_" + uuid4().hex

        try:
            result = self.runner(
                round_id=round_id,
                max_agents=self.config.max_agents,
            )
            self.executed += 1
            self.last_round_id = round_id

            return {
                "status": "executed",
                "round_id": round_id,
                "result": result,
            }

        except Exception as error:
            self.failed += 1
            self.last_round_id = round_id

            return {
                "status": "error",
                "round_id": round_id,
                "error_type": type(error).__name__,
            }

        finally:
            _PROCESS_ROUND_LOCK.release()

    def _loop(self):
        while not self._stop.is_set():
            self.run_once()
            if self._stop.wait(self.config.interval_seconds):
                break

    def start(self):
        if not self.config.enabled:
            raise WorldSchedulerError("El controlador esta desactivado.")

        with self._lifecycle_lock:
            if self._thread is not None and self._thread.is_alive():
                return False

            self._stop.clear()
            self._thread = Thread(
                target=self._loop,
                daemon=True,
                name="replikers-world-scheduler",
            )
            self._thread.start()
            return True

    def stop(self, timeout=10):
        with self._lifecycle_lock:
            thread = self._thread
            if thread is None:
                return True
            self._stop.set()

        if thread is not current_thread():
            thread.join(timeout=timeout)

        return not thread.is_alive()

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()
