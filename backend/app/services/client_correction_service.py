from __future__ import annotations

import json

from datetime import (
    datetime,
    timezone,
)
from typing import Callable

from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import Session

from app.agentic.client_correction_runtime import (
    ClientCorrectionPlan,
    run_client_correction_planner,
)
from app.models.project import Project
from app.models.project_specialist import (
    ProjectFinalReview,
)
from app.models.task import Task
from app.services.activity_service import (
    record_activity,
)
from app.services.message_service import (
    record_message,
)


ClientCorrectionPlanner = Callable[
    ...,
    ClientCorrectionPlan,
]


class ClientCorrectionPreparationError(
    ValueError
):
    pass


def _source_review(
    *,
    db: Session,
    project_id: int,
    attempt_number: int,
) -> ProjectFinalReview:
    review = db.scalar(
        select(
            ProjectFinalReview
        )
        .where(
            ProjectFinalReview.project_id
            == project_id,
            ProjectFinalReview.attempt_number
            == attempt_number,
        )
        .limit(1)
    )

    if review is None:
        raise ClientCorrectionPreparationError(
            "No se encontró la versión "
            "aprobada que revisó el cliente."
        )

    if review.status != "approved":
        raise ClientCorrectionPreparationError(
            "La versión indicada todavía "
            "no está aprobada por Vera."
        )

    return review


def _existing_bridge(
    *,
    db: Session,
    project_id: int,
    source_review_id: int,
) -> ProjectFinalReview | None:
    marker = (
        "client_correction_source_review_id="
        f"{source_review_id};"
    )

    return db.scalar(
        select(
            ProjectFinalReview
        )
        .where(
            ProjectFinalReview.project_id
            == project_id,
            ProjectFinalReview.status
            == "corrections_requested",
            ProjectFinalReview.reasoning.like(
                f"{marker}%"
            ),
        )
        .order_by(
            ProjectFinalReview
            .attempt_number
            .desc()
        )
        .limit(1)
    )


def prepare_client_correction_review(
    *,
    db: Session,
    project: Project,
    client_request: str,
    source_review_attempt: int,
    planner:
        ClientCorrectionPlanner | None
        = None,
) -> dict:
    request_text = (
        client_request
        .strip()
    )

    if len(request_text) < 5:
        raise ClientCorrectionPreparationError(
            "La solicitud de corrección "
            "es demasiado breve."
        )

    source = _source_review(
        db=db,
        project_id=project.id,
        attempt_number=
            source_review_attempt,
    )

    existing = _existing_bridge(
        db=db,
        project_id=project.id,
        source_review_id=source.id,
    )

    if existing is not None:
        project.status = (
            "corrections_requested"
        )

        return {
            "review_id":
                existing.id,

            "attempt_number":
                existing.attempt_number,

            "corrections":
                json.loads(
                    existing.corrections_json
                    or "[]"
                ),

            "created":
                False,
        }

    tasks = list(
        db.scalars(
            select(
                Task
            )
            .where(
                Task.project_id
                == project.id
            )
            .order_by(
                Task.id
            )
        ).all()
    )

    if not tasks:
        raise ClientCorrectionPreparationError(
            "El proyecto no contiene "
            "tareas corregibles."
        )

    project_data = {
        "id":
            project.id,

        "titulo":
            project.title,

        "descripcion":
            project.description,

        "estado":
            project.status,

        "moneda":
            project.currency,
    }

    task_data = [
        {
            "task_id":
                task.id,

            "titulo":
                task.title,

            "descripcion":
                task.description,

            "estado":
                task.status,

            "especialidad_requerida":
                task.required_specialty,
        }
        for task in tasks
    ]

    planner_callable = (
        planner
        or run_client_correction_planner
    )

    try:
        plan = planner_callable(
            project_data=project_data,
            tasks=task_data,
            client_request=request_text,
        )

    except Exception as exc:
        raise (
            ClientCorrectionPreparationError(
                "R00 no pudo preparar "
                "las correcciones solicitadas "
                "por el cliente."
            )
        ) from exc

    allowed_task_ids = {
        task.id
        for task in tasks
    }

    normalized: list[dict] = []

    seen: set[
        tuple[int, str]
    ] = set()

    for correction in (
        plan.corrections
    ):
        task_id = (
            correction.task_id
        )

        if (
            task_id
            not in allowed_task_ids
        ):
            raise (
                ClientCorrectionPreparationError(
                    "R00 indicó una tarea "
                    "que no pertenece "
                    "al proyecto."
                )
            )

        instruction = (
            correction.instruction
            .strip()
        )

        if len(instruction) < 5:
            raise (
                ClientCorrectionPreparationError(
                    "Una corrección no contiene "
                    "una instrucción válida."
                )
            )

        key = (
            task_id,
            instruction,
        )

        if key in seen:
            continue

        seen.add(key)

        normalized.append(
            {
                "task_id":
                    task_id,

                "instruction":
                    instruction,

                "severity":
                    correction.severity,
            }
        )

    if not normalized:
        raise ClientCorrectionPreparationError(
            "R00 no identificó ninguna "
            "corrección ejecutable."
        )

    max_attempt = int(
        db.scalar(
            select(
                func.max(
                    ProjectFinalReview
                    .attempt_number
                )
            )
            .where(
                ProjectFinalReview.project_id
                == project.id
            )
        )
        or 0
    )

    reasoning_marker = (
        "client_correction_source_review_id="
        f"{source.id};"
        " structured_by=r00;"
        " source=client"
    )

    bridge = ProjectFinalReview(
        project_id=
            project.id,

        requirement_id=
            source.requirement_id,

        reviewer_repliker_id=
            source.reviewer_repliker_id,

        attempt_number=
            max_attempt + 1,

        status=
            "corrections_requested",

        score=None,

        summary=(
            "R00 convirtió la solicitud "
            "de corrección del cliente "
            "en tareas ejecutables."
        ),

        corrections_json=
            json.dumps(
                normalized,
                ensure_ascii=False,
            ),

        reasoning=
            reasoning_marker,

        completed_at=
            datetime.now(
                timezone.utc
            ),
    )

    db.add(
        bridge
    )

    project.status = (
        "corrections_requested"
    )

    db.flush()

    record_activity(
        db=db,
        actor_type="r00",
        event_type=(
            "client_corrections_prepared"
        ),
        project_id=project.id,
        title=(
            "R00 preparó las correcciones "
            "solicitadas por el cliente"
        ),
        description=(
            f"Se identificaron "
            f"{len(normalized)} "
            "corrección(es) ejecutables "
            "para el proyecto."
        ),
    )

    record_message(
        db=db,
        project_id=project.id,
        sender_type="r00",
        receiver_type="project",
        message_type=(
            "client_corrections_prepared"
        ),
        content=(
            "La solicitud del cliente "
            "fue analizada y convertida "
            "en correcciones concretas. "
            "El proyecto volverá ahora "
            "al ciclo de ejecución, "
            "pruebas y revisión de Vera."
        ),
    )

    db.flush()

    return {
        "review_id":
            bridge.id,

        "attempt_number":
            bridge.attempt_number,

        "corrections":
            normalized,

        "created":
            True,
    }
