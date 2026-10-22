"""Control local del supervisor World.

No inicia rondas al importarse.
La parada es cooperativa y no cancela una llamada
a Gemini que ya este procesandose.
"""

import os
from threading import Event, Lock, Thread, current_thread

from app.agentic.world_live_supervisor import (
    LiveSupervisorConfig,
    LiveSupervisorError,
    run_bounded,
    verify_environment,
)


class LiveSupervisorController:

    def __init__(self, config=None, runner=None):
        self.config = (
            config if config is not None
            else LiveSupervisorConfig()
        )

        if not isinstance(self.config, LiveSupervisorConfig):
            raise LiveSupervisorError(
                "Configuracion invalida."
            )

        self._runner = (
            runner if runner is not None
            else run_bounded
        )

        if not callable(self._runner):
            raise LiveSupervisorError(
                "Ejecutor invalido."
            )

        self._lock = Lock()
        self._stop = Event()
        self._thread = None
        self._state = "idle"
        self._completed = 0
        self._failed = 0
        self._last_error_type = None

    def _worker(self):
        try:
            self._runner(
                self.config,
                stop_event=self._stop,
            )

            with self._lock:
                self._completed += 1
                self._state = (
                    "stopped"
                    if self._stop.is_set()
                    else "completed"
                )

        except Exception as error:
            with self._lock:
                self._failed += 1
                self._last_error_type = type(error).__name__
                self._state = "failed"

    def start(self):
        with self._lock:
            if (
                self._thread is not None
                and self._thread.is_alive()
            ):
                return False

            if os.getenv(
                "RW_LIVE_SUPERVISOR_OPT_IN"
            ) != "1":
                raise LiveSupervisorError(
                    "Inicio sin autorizacion explicita."
                )

            verify_environment()

            self._stop = Event()
            self._state = "running"
            self._last_error_type = None

            self._thread = Thread(
                target=self._worker,
                name="replikers-world-live-bounded",
                daemon=True,
            )

            self._thread.start()
            return True

    def stop(self, timeout=10):
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not 0 <= timeout <= 120
        ):
            raise LiveSupervisorError(
                "Tiempo de parada invalido."
            )

        with self._lock:
            thread = self._thread
            self._stop.set()

        if (
            thread is not None
            and thread is not current_thread()
        ):
            thread.join(timeout=timeout)

        return (
            thread is None
            or not thread.is_alive()
        )

    def snapshot(self):
        with self._lock:
            running = (
                self._thread is not None
                and self._thread.is_alive()
            )

            return {
                "status": self._state,
                "running": running,
                "stop_requested": self._stop.is_set(),
                "executions_completed": self._completed,
                "executions_failed": self._failed,
                "last_error_type": self._last_error_type,
                "owner_id": self.config.owner_id,
                "max_rounds": self.config.max_rounds,
                "scope": "current_process",
            }
