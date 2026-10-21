"""Registro opcional del supervisor en FastAPI.

Desactivado por defecto. Solo desarrollo y SQLite
de ensayo. Nunca inicia rondas automaticamente.
"""

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy.engine import URL

from app.agentic.world_autonomy_runtime import available_agents
from app.agentic.world_autonomous_scheduler import (
    WorldAutonomousScheduler,
    WorldScheduleConfig,
)
from app.agentic.world_scheduler_bridge import GovernedSQLiteRunner
from app.agentic.world_scheduler_status import (
    register_owner_scheduler,
    unregister_owner_scheduler,
)


class WorldSchedulerLifecycleError(ValueError):
    pass


@contextmanager
def configured_world_scheduler_lifecycle(engine, environment):
    """Registrar el controlador durante la vida del servidor."""

    if os.getenv("RW_SUPERVISOR_BIND", "") != "1":
        yield None
        return

    if str(environment).lower() not in (
        "development", "local", "test"
    ):
        raise WorldSchedulerLifecycleError(
            "Supervisor de ensayo prohibido fuera de desarrollo."
        )

    if os.getenv("ECONOMY_MODE", "simulation") != "simulation":
        raise WorldSchedulerLifecycleError(
            "La economia debe estar en simulacion."
        )

    if os.getenv("REAL_PAYMENTS_ENABLED", "false").lower() != "false":
        raise WorldSchedulerLifecycleError(
            "Los pagos reales deben estar desactivados."
        )

    raw_owner = os.getenv("RW_SUPERVISOR_OWNER_ID", "")

    if not re.fullmatch(r"[1-9][0-9]{0,14}", raw_owner):
        raise WorldSchedulerLifecycleError(
            "Propietario de ensayo no configurado."
        )

    owner_id = int(raw_owner)

    url = engine.url

    if (
        url.get_backend_name() != "sqlite"
        or not url.database
        or url.query
    ):
        raise WorldSchedulerLifecycleError(
            "No se permite PostgreSQL ni SQLite con parametros."
        )

    path = Path(url.database).resolve()
    folder = path.parent

    if (
        folder.name != "replikers-world-backups"
        or not re.fullmatch(r"rw_bridge_[0-9a-f]{16}\.db", path.name)
        or not path.is_file()
        or path.is_symlink()
    ):
        raise WorldSchedulerLifecycleError(
            "Solo se admite una copia World de ensayo."
        )

    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as con:
        con.execute("PRAGMA query_only=ON")

        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise WorldSchedulerLifecycleError(
                "Base de ensayo corrupta."
            )

        if con.execute("PRAGMA foreign_key_check").fetchall():
            raise WorldSchedulerLifecycleError(
                "Claves foraneas invalidas."
            )

        tables = {
            row[0] for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

        required = {
            "users",
            "replikers",
            "world_agent_events",
            "world_agent_memories",
            "world_agent_autonomy_policies",
            "ledger_transactions",
        }

        if not required.issubset(tables):
            raise WorldSchedulerLifecycleError(
                "Esquema de ensayo incompleto."
            )

        exists = con.execute(
            "SELECT 1 FROM users WHERE id = ? LIMIT 1",
            (owner_id,),
        ).fetchone()

        if exists is None:
            raise WorldSchedulerLifecycleError(
                "Propietario inexistente en la copia."
            )

        agents = con.execute(
            "SELECT id, owner_id FROM replikers "
            "WHERE is_active = 1 ORDER BY id"
        ).fetchall()

    owned_ids = {
        int(agent_id)
        for agent_id, actual_owner in agents
        if int(actual_owner) == owner_id
    }

    all_ids = [
        int(agent_id)
        for agent_id, _ in agents
    ]

    if not owned_ids:
        raise WorldSchedulerLifecycleError(
            "El propietario no tiene Replikers activos."
        )

    config = WorldScheduleConfig(
        database_url=str(
            URL.create("sqlite", database=str(path))
        ),
        enabled=True,
        economy_mode="simulation",
        real_payments_enabled=False,
        external_ai_enabled=False,
        max_agents=1,
        interval_seconds=600,
    )

    # Los siguientes motores son exclusivamente de ensayo.
    # No llaman a Gemini ni simulan pagos.
    def demo_idea(context):
        actor_id = context["repliker_id"]

        if actor_id not in owned_ids:
            raise WorldSchedulerLifecycleError(
                "No se permite iniciar propuestas de otro propietario."
            )

        target = next(
            (value for value in all_ids if value != actor_id),
            None,
        )

        if target is None:
            raise WorldSchedulerLifecycleError(
                "No hay contraparte de ensayo."
            )

        return {
            "title": "Servicio digital experimental",
            "description": (
                "Propuesta ficticia para comprobar "
                "el ciclo economico de Replikers World."
            ),
            "target_repliker_id": target,
            "price_cents": 2500,
            "estimated_cost_cents": 300,
            "inspired_by_strategy_ids": [],
        }

    def demo_response(context):
        return {
            "decision": "reject",
            "message": (
                "Decision automatica de ensayo, sin pago."
            ),
        }

    bridge = None
    scheduler = None
    registered = False

    try:
        bridge = GovernedSQLiteRunner(
            config=config,
            db_path=path,
            allowed_directory=folder,
            idea_engine=demo_idea,
            response_engine=demo_response,
            initiator_owner_id=owner_id,
        )

        def owned_runner(*, round_id, max_agents):
            # La seleccion heredada es global.
            # Bloquear si incluye iniciadores de otros propietarios.
            with bridge.sessions() as db:
                selected = available_agents(
                    db,
                    limit=max_agents,
                    initiator_owner_id=owner_id,
                )

                if not selected:
                    raise WorldSchedulerLifecycleError(
                        "No hay agentes economicos disponibles."
                    )

                if any(
                    agent_id not in owned_ids
                    for agent_id in selected
                ):
                    raise WorldSchedulerLifecycleError(
                        "La ronda incluiria otro propietario."
                    )

            return bridge(
                round_id=round_id,
                max_agents=max_agents,
            )

        scheduler = WorldAutonomousScheduler(
            config=config,
            runner=owned_runner,
        )

        register_owner_scheduler(
            owner_id=owner_id,
            scheduler=scheduler,
        )
        registered = True

        # Solo registro. NUNCA scheduler.start().
        yield scheduler

    finally:
        if registered:
            if scheduler.running:
                stopped = scheduler.stop(timeout=15)

                if not stopped:
                    raise WorldSchedulerLifecycleError(
                        "El controlador no pudo detenerse."
                    )

            unregister_owner_scheduler(owner_id=owner_id)

        if bridge is not None:
            bridge.close()
