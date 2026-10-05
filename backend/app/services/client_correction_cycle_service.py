from __future__ import annotations

from typing import Callable

from sqlalchemy.orm import Session

from app.agentic.project_graph import (
    run_project_lifecycle,
)
from app.models.project import Project
from app.services.activity_service import (
    record_activity,
)
from app.services.message_service import (
    record_message,
)


LifecycleRunner = Callable[..., dict]


PROCESSABLE_STATUSES = {
    "corrections_requested",
    "awaiting_final_review",
}


class ClientCorrectionCycleError(
    ValueError
):
    pass


def run_client_correction_cycle(
    *,
    db: Session,
    project_id: int,
    runner: LifecycleRunner | None = None,
    max_cycles: int = 3,
) -> dict:
    if max_cycles < 1:
        raise ClientCorrectionCycleError(
            "max_cycles debe ser mayor "
            "o igual a 1."
        )

    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise ClientCorrectionCycleError(
            "Proyecto no encontrado."
        )

    lifecycle_runner = (
        runner
        or run_project_lifecycle
    )

    cycles: list[dict] = []

    for cycle_number in range(
        1,
        max_cycles + 1,
    ):
        db.expire_all()

        project = db.get(
            Project,
            project_id,
        )

        if project is None:
            raise ClientCorrectionCycleError(
                "Proyecto no encontrado "
                "durante el ciclo."
            )

        if project.status == "completed":
            return {
                "status":
                    "completed",

                "completed":
                    True,

                "cycles":
                    cycles,

                "cycles_count":
                    len(cycles),

                "project_status":
                    project.status,
            }

        if (
            project.status
            not in PROCESSABLE_STATUSES
        ):
            return {
                "status":
                    "blocked",

                "completed":
                    False,

                "cycles":
                    cycles,

                "cycles_count":
                    len(cycles),

                "project_status":
                    project.status,
            }

        try:
            state = lifecycle_runner(
                db=db,
                project_id=project.id,
            )

        except Exception as exc:
            db.rollback()

            project = db.get(
                Project,
                project_id,
            )

            if project is not None:
                record_activity(
                    db=db,
                    actor_type="system",
                    event_type=(
                        "client_correction_cycle_failed"
                    ),
                    project_id=
                        project.id,
                    title=(
                        "El ciclo automático "
                        "de corrección se detuvo"
                    ),
                    description=(
                        "No fue posible completar "
                        "el ciclo automático. "
                        f"Detalle: {str(exc)[:1500]}"
                    ),
                )

                record_message(
                    db=db,
                    project_id=
                        project.id,
                    sender_type=
                        "system",
                    receiver_type=
                        "project",
                    message_type=(
                        "client_correction_cycle_failed"
                    ),
                    content=(
                        "El ciclo automático "
                        "de corrección encontró "
                        "un problema y requiere "
                        "una nueva ejecución."
                    ),
                )

                db.commit()

            return {
                "status":
                    "failed",

                "completed":
                    False,

                "cycles":
                    cycles,

                "cycles_count":
                    len(cycles),

                "project_status":
                    (
                        project.status
                        if project is not None
                        else "unknown"
                    ),

                "error":
                    str(exc)[:1500],
            }

        db.expire_all()

        project = db.get(
            Project,
            project_id,
        )

        if project is None:
            raise ClientCorrectionCycleError(
                "Proyecto no encontrado "
                "después de ejecutar "
                "el ciclo."
            )

        cycle = {
            "cycle":
                cycle_number,

            "current_stage":
                str(
                    state.get(
                        "current_stage",
                        "",
                    )
                ),

            "next_action":
                str(
                    state.get(
                        "next_action",
                        "",
                    )
                ),

            "project_status":
                project.status,

            "final_review_status":
                state.get(
                    "final_review_status"
                ),

            "final_review_id":
                state.get(
                    "final_review_id"
                ),
        }

        cycles.append(
            cycle
        )

        if project.status == "completed":
            record_activity(
                db=db,
                actor_type="system",
                event_type=(
                    "client_correction_cycle_completed"
                ),
                project_id=project.id,
                title=(
                    "Corrección del cliente "
                    "completada"
                ),
                description=(
                    "Los cambios solicitados "
                    "por el cliente fueron "
                    "ejecutados, verificados "
                    "por QA y revisados "
                    "nuevamente por Vera."
                ),
            )

            record_message(
                db=db,
                project_id=project.id,
                sender_type="system",
                receiver_type="project",
                message_type=(
                    "client_correction_cycle_completed"
                ),
                content=(
                    "La nueva versión del "
                    "proyecto terminó su ciclo "
                    "de corrección, pruebas "
                    "y revisión final."
                ),
            )

            db.commit()

            return {
                "status":
                    "completed",

                "completed":
                    True,

                "cycles":
                    cycles,

                "cycles_count":
                    len(cycles),

                "project_status":
                    project.status,
            }

        if (
            project.status
            not in PROCESSABLE_STATUSES
        ):
            return {
                "status":
                    "blocked",

                "completed":
                    False,

                "cycles":
                    cycles,

                "cycles_count":
                    len(cycles),

                "project_status":
                    project.status,
            }

    project = db.get(
        Project,
        project_id,
    )

    if project is not None:
        record_activity(
            db=db,
            actor_type="system",
            event_type=(
                "client_correction_cycle_attention"
            ),
            project_id=project.id,
            title=(
                "La corrección necesita "
                "más revisión"
            ),
            description=(
                "El ciclo alcanzó el límite "
                "automático de revisiones. "
                "El proyecto conserva todos "
                "los avances realizados."
            ),
        )

        db.commit()

    return {
        "status":
            "needs_attention",

        "completed":
            False,

        "cycles":
            cycles,

        "cycles_count":
            len(cycles),

        "project_status":
            (
                project.status
                if project is not None
                else "unknown"
            ),
    }
