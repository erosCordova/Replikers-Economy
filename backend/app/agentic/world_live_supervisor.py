"""Supervisor acotado de rondas World en PostgreSQL.

No se inicia al importar. No activa permisos de agentes.
No ejecuta pagos ni transferencias.
"""

import argparse
import os
import re
from dataclasses import dataclass
from threading import Event
from uuid import uuid4


class LiveSupervisorError(RuntimeError):
    pass


@dataclass(frozen=True)
class LiveSupervisorConfig:
    owner_id: int = 1
    agent_ids: tuple[int, int] = (18, 19)
    max_rounds: int = 2
    interval_seconds: int = 300
    max_agents: int = 1
    model_name: str = "gemini-3.5-flash-lite"

    def __post_init__(self):
        if type(self.owner_id) is not int or self.owner_id <= 0:
            raise LiveSupervisorError("Propietario invalido.")

        if (
            len(self.agent_ids) != 2
            or len(set(self.agent_ids)) != 2
            or any(type(i) is not int or i <= 0 for i in self.agent_ids)
        ):
            raise LiveSupervisorError("Agentes invalidos.")

        if type(self.max_rounds) is not int or not 1 <= self.max_rounds <= 3:
            raise LiveSupervisorError("Se admiten de 1 a 3 rondas.")

        if (
            type(self.interval_seconds) is not int
            or not 60 <= self.interval_seconds <= 86400
        ):
            raise LiveSupervisorError("Intervalo fuera de limites.")

        if type(self.max_agents) is not int or self.max_agents != 1:
            raise LiveSupervisorError("Solo un iniciador por ronda.")

        if not re.fullmatch(r"gemini-[A-Za-z0-9._-]{3,80}", self.model_name):
            raise LiveSupervisorError("Modelo invalido.")


def verify_environment():
    if os.getenv("ECONOMY_MODE", "simulation").lower() != "simulation":
        raise LiveSupervisorError("Se requiere economia simulada.")

    if os.getenv("REAL_PAYMENTS_ENABLED", "false").lower() != "false":
        raise LiveSupervisorError("Pagos reales prohibidos.")

    if os.getenv("RW_SUPERVISOR_BIND", "0") == "1":
        raise LiveSupervisorError(
            "Supervisor anterior habilitado: revisar coexistencia."
        )


def verify_agents(db, config):
    from app.models.user import User
    from app.models.repliker import Repliker
    from app.services.world_autonomy_policy import get_policy

    owner = db.get(User, config.owner_id)

    if owner is None or not owner.is_active:
        raise LiveSupervisorError("Propietario inactivo.")

    for agent_id in config.agent_ids:
        agent = db.get(Repliker, agent_id)

        if (
            agent is None
            or not agent.is_active
            or agent.owner_id != config.owner_id
            or agent.status != "available"
        ):
            raise LiveSupervisorError(
                "Agente no disponible: " + str(agent_id)
            )

        policy = get_policy(
            db,
            owner_id=config.owner_id,
            repliker_id=agent_id,
        )

        if not policy["enabled"]:
            raise LiveSupervisorError(
                "Autonomia desactivada: " + str(agent_id)
            )

        if not (
            0 < policy["max_price_cents"] <= 10000
            and 0 <= policy["max_cost_cents"] <= 5000
            and policy["max_proposals_per_round"] == 1
        ):
            raise LiveSupervisorError(
                "Politica fuera de limites: " + str(agent_id)
            )


def run_bounded(config, *, stop_event=None):
    """Rondas acotadas con bloqueo transaccional por ronda."""

    if not isinstance(config, LiveSupervisorConfig):
        raise LiveSupervisorError(
            "Configuracion invalida."
        )

    if os.getenv("RW_LIVE_SUPERVISOR_OPT_IN") != "1":
        raise LiveSupervisorError(
            "Autorizacion explicita requerida."
        )

    if stop_event is not None and not all(
        callable(getattr(stop_event, method, None))
        for method in ("wait", "is_set", "set")
    ):
        raise LiveSupervisorError(
            "Control de parada invalido."
        )

    from dotenv import load_dotenv
    from sqlalchemy import text
    from app.database.session import SessionLocal
    from app.services.economy_service import ensure_simulation_mode
    from app.agentic.world_event_runtime import run_logged_governed_round
    from app.agentic.world_idea_graph import make_gemini_idea_engine
    from app.agentic.world_negotiation_graph import make_gemini_response_engine

    load_dotenv(override=False)
    verify_environment()
    ensure_simulation_mode()

    stop = (
        stop_event if stop_event is not None
        else Event()
    )

    ideas = None
    responses = None

    try:
        for number in range(config.max_rounds):
            if stop.is_set():
                break

            round_id = "rw-bounded-" + uuid4().hex

            # Un bloqueo por ronda. Nunca mantenerlo
            # durante el intervalo de espera.
            with SessionLocal() as lock_db:
                if (
                    lock_db.get_bind().dialect.name
                    != "postgresql"
                ):
                    raise LiveSupervisorError(
                        "Solo PostgreSQL."
                    )

                lock_db.execute(
                    text("SET TRANSACTION READ ONLY")
                )

                acquired = lock_db.execute(
                    text(
                        "SELECT pg_try_advisory_xact_lock("
                        ":namespace, :owner)"
                    ),
                    {
                        "namespace": 20261021,
                        "owner": config.owner_id,
                    },
                ).scalar_one()

                if not acquired:
                    lock_db.rollback()
                    raise LiveSupervisorError(
                        "Ya existe otra ejecucion de este supervisor."
                    )

                try:
                    # Autorizacion antes de construir
                    # motores externos.
                    with SessionLocal() as check_db:
                        verify_agents(check_db, config)
                        check_db.rollback()

                    if ideas is None:
                        ideas = make_gemini_idea_engine(
                            config.model_name
                        )

                    if responses is None:
                        responses = make_gemini_response_engine(
                            config.model_name
                        )

                    with SessionLocal() as db:
                        try:
                            # Revalidacion inmediatamente
                            # antes de ejecutar cada ronda.
                            verify_agents(db, config)

                            output = run_logged_governed_round(
                                db,
                                round_id=round_id,
                                idea_engine=ideas,
                                response_engine=responses,
                                max_agents=config.max_agents,
                                initiator_owner_id=config.owner_id,
                            )

                            if (
                                not isinstance(output, dict)
                                or output.get("payments_executed") is not False
                                or output.get("real_money_used") is not False
                            ):
                                raise LiveSupervisorError(
                                    "Resultado economico inesperado."
                                )

                            print(
                                "RONDA=" + str(number + 1)
                            )
                            print("RONDA_ID=" + round_id)
                            print(
                                "EVENTOS_INSERTADOS="
                                + str(
                                    output.get(
                                        "events_inserted", 0
                                    )
                                )
                            )
                            print(
                                "RESULTADOS="
                                + str(
                                    len(
                                        output.get(
                                            "results", []
                                        )
                                    )
                                )
                            )

                        except Exception:
                            db.rollback()
                            raise

                finally:
                    # PostgreSQL libera automaticamente
                    # pg_try_advisory_xact_lock al
                    # finalizar esta transaccion.
                    lock_db.rollback()

            # El bloqueo ya fue liberado.
            if number + 1 < config.max_rounds:
                if stop.wait(config.interval_seconds):
                    break

        print(
            "RESULTADO_GENERAL="
            "RONDAS_ACOTADAS_FINALIZADAS"
        )

    except KeyboardInterrupt:
        stop.set()
        print(
            "RESULTADO_GENERAL=DETENIDO_POR_USUARIO"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--interval", type=int, default=300)

    args = parser.parse_args()

    try:
        config = LiveSupervisorConfig(
            max_rounds=args.rounds,
            interval_seconds=args.interval,
        )

        print("MODELO=" + config.model_name)
        print("AGENTES=18,19")
        print("RONDA_MAXIMA=" + str(config.max_rounds))
        print("INTERVALO_SEGUNDOS=" + str(config.interval_seconds))
        print("PAGOS_REALES=PROHIBIDOS")
        print("AUTORIZACION_AUTOMATICA=NO")

        if not args.run:
            print("RESULTADO_GENERAL=PLAN_SEGURO")
            return

        if os.getenv("RW_LIVE_SUPERVISOR_OPT_IN") != "1":
            print("RESULTADO_GENERAL=EJECUCION_SIN_AUTORIZACION_BLOQUEADA")
            return

        run_bounded(config)

    except Exception as error:
        print("ERROR_TIPO=" + type(error).__name__)
        if isinstance(error, LiveSupervisorError):
            print("ERROR_DETALLE=" + str(error))
        print("RESULTADO_GENERAL=SUPERVISOR_NO_EJECUTADO")


if __name__ == "__main__":
    main()
