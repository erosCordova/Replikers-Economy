from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.execution import (
    ExecutionArtifact,
    ExecutionWorkspace,
)
from app.models.project import Project
from app.models.project_specialist import (
    ProjectFinalCorrectionRun,
    ProjectFinalReview,
)
from app.models.qa import QAReview
from app.models.task import Task
from app.services.project_delivery_service import (
    latest_delivery_decision,
    parse_delivery_message,
)


def _normalize(
    value: str | None,
) -> str:
    return (
        value
        or ""
    ).strip().lower()


def _correction_count(
    final_review: ProjectFinalReview | None,
) -> int:
    if final_review is None:
        return 0

    try:
        payload = json.loads(
            final_review.corrections_json
            or "[]"
        )
    except (
        json.JSONDecodeError,
        TypeError,
    ):
        return 0

    if not isinstance(
        payload,
        list,
    ):
        return 0

    return len(payload)


def build_project_report_delivery(
    *,
    db: Session,
    project: Project,
    tasks: list[Task],
    latest_qa: dict[int, QAReview],
    final_review: ProjectFinalReview | None,
    progress_percent: int,
    stage_label: str,
) -> dict:
    workspaces = list(
        db.scalars(
            select(
                ExecutionWorkspace
            )
            .where(
                ExecutionWorkspace.project_id
                == project.id
            )
            .order_by(
                ExecutionWorkspace.id
            )
        ).all()
    )

    workspace_ids = [
        workspace.id
        for workspace in workspaces
    ]

    workspace_by_id = {
        workspace.id:
            workspace
        for workspace
        in workspaces
    }

    if workspace_ids:
        artifacts = list(
            db.scalars(
                select(
                    ExecutionArtifact
                )
                .where(
                    ExecutionArtifact.workspace_id
                    .in_(
                        workspace_ids
                    )
                )
                .order_by(
                    ExecutionArtifact.id
                )
            ).all()
        )
    else:
        artifacts = []

    correction_runs = list(
        db.scalars(
            select(
                ProjectFinalCorrectionRun
            )
            .where(
                ProjectFinalCorrectionRun
                .project_id
                == project.id
            )
            .order_by(
                ProjectFinalCorrectionRun.id
            )
        ).all()
    )

    task_by_id = {
        task.id:
            task
        for task in tasks
    }

    incidents: list[dict] = []

    for review in latest_qa.values():
        review_status = _normalize(
            review.status
        )

        if review_status not in {
            "failed",
            "needs_review",
        }:
            continue

        task = task_by_id.get(
            review.task_id
        )

        incidents.append(
            {
                "kind":
                    "qa",

                "severity":
                    (
                        "alta"
                        if review_status
                        == "failed"
                        else "media"
                    ),

                "title":
                    (
                        "Prueba fallida"
                        if review_status
                        == "failed"
                        else
                        "Prueba requiere revisión"
                    ),

                "detail":
                    (
                        review.summary
                        or
                        "La revisión QA requiere atención."
                    ),

                "task_id":
                    review.task_id,

                "task_title":
                    (
                        task.title
                        if task is not None
                        else None
                    ),
            }
        )

    for run in correction_runs:
        if _normalize(
            run.status
        ) != "failed":
            continue

        task = task_by_id.get(
            run.task_id
        )

        incidents.append(
            {
                "kind":
                    "correction",

                "severity":
                    "alta",

                "title":
                    "Corrección fallida",

                "detail":
                    (
                        run.error_summary
                        or
                        "La corrección no pudo completarse."
                    ),

                "task_id":
                    run.task_id,

                "task_title":
                    (
                        task.title
                        if task is not None
                        else None
                    ),
            }
        )

    corrections_requested = (
        _correction_count(
            final_review
        )
    )

    if (
        final_review is not None
        and _normalize(
            final_review.status
        )
        == "corrections_requested"
    ):
        incidents.append(
            {
                "kind":
                    "final_review",

                "severity":
                    "media",

                "title":
                    "Vera solicitó correcciones",

                "detail":
                    (
                        f"Hay "
                        f"{corrections_requested} "
                        "corrección(es) pendientes "
                        "antes de la entrega."
                    ),

                "task_id":
                    None,

                "task_title":
                    None,
            }
        )

    completed_tasks = sum(
        1
        for task in tasks
        if _normalize(
            task.status
        )
        == "completed"
    )

    qa_passed = sum(
        1
        for review
        in latest_qa.values()
        if _normalize(
            review.status
        )
        == "passed"
    )

    qa_failed = sum(
        1
        for review
        in latest_qa.values()
        if _normalize(
            review.status
        )
        == "failed"
    )

    report_status = (
        "requiere_atencion"
        if incidents
        else "estable"
    )

    report_summary = (
        f"El proyecto se encuentra en "
        f"{stage_label.lower()}. "
        f"{completed_tasks} de "
        f"{len(tasks)} tarea(s) "
        f"están completadas, "
        f"{qa_passed} prueba(s) "
        f"han sido aprobadas y "
        f"hay {len(incidents)} "
        f"incidencia(s) abierta(s)."
    )

    vera_approved = (
        final_review is not None
        and _normalize(
            final_review.status
        )
        == "approved"
    )

    version_number = (
        final_review.attempt_number
        if final_review is not None
        else 1
    )

    client_message = (
        latest_delivery_decision(
            db=db,
            project_id=project.id,
        )
    )

    client_data = (
        parse_delivery_message(
            client_message
        )
    )

    client_decision = (
        client_data["decision"]
    )

    client_comment = (
        client_data["comment"]
    )

    client_decision_review_attempt = (
        client_data[
            "review_attempt"
        ]
    )

    technical_ready = (
        progress_percent == 100
        and vera_approved
    )

    unresolved_client_correction = (
        client_decision
        == "corrections_requested"
        and (
            client_decision_review_attempt
            is None
            or client_decision_review_attempt
            >= version_number
        )
    )

    delivery_ready = (
        technical_ready
        and not unresolved_client_correction
    )

    client_action_required = (
        delivery_ready
        and client_decision
        != "accepted"
    )

    if client_decision == "accepted":
        delivery_status = "accepted"
    elif unresolved_client_correction:
        delivery_status = (
            "corrections_requested"
        )
    elif delivery_ready:
        delivery_status = "ready"
    else:
        delivery_status = "pending"

    files = []

    for artifact in artifacts:
        workspace = (
            workspace_by_id.get(
                artifact.workspace_id
            )
        )

        files.append(
            {
                "artifact_id":
                    artifact.id,

                "workspace_id":
                    artifact.workspace_id,

                "task_id":
                    (
                        workspace.task_id
                        if workspace
                        is not None
                        else None
                    ),

                "relative_path":
                    artifact.relative_path,

                "media_type":
                    artifact.media_type,

                "size_bytes":
                    artifact.size_bytes,

                "sha256":
                    artifact.sha256,
            }
        )

    total_size = sum(
        artifact.size_bytes
        for artifact in artifacts
    )

    if client_decision == "accepted":
        delivery_message = (
            "El cliente aceptó "
            "la entrega final."
        )

    elif unresolved_client_correction:
        delivery_message = (
            "El cliente solicitó "
            "correcciones sobre "
            "la versión actual."
        )

    elif (
        client_decision
        == "corrections_requested"
        and delivery_ready
    ):
        delivery_message = (
            "Hay una nueva versión "
            "revisada por Vera lista "
            "para que el cliente "
            "vuelva a evaluarla."
        )

    elif delivery_ready:
        delivery_message = (
            "La entrega está lista. "
            "Vera aprobó la versión final "
            "y espera la decisión "
            "del cliente."
        )

    elif (
        final_review is not None
        and _normalize(
            final_review.status
        )
        == "corrections_requested"
    ):
        delivery_message = (
            "La entrega está detenida "
            "hasta completar las "
            "correcciones solicitadas "
            "por Vera."
        )

    else:
        delivery_message = (
            "La entrega todavía no está lista. "
            "El proyecto debe completar "
            "sus etapas y obtener "
            "la aprobación final de Vera."
        )

    return {
        "report": {
            "status":
                report_status,

            "summary":
                report_summary,

            "progress_percent":
                progress_percent,

            "tasks_total":
                len(tasks),

            "tasks_completed":
                completed_tasks,

            "qa_passed":
                qa_passed,

            "qa_failed":
                qa_failed,

            "incidents_total":
                len(incidents),

            "incidents":
                incidents,
        },

        "delivery": {
            "version":
                f"v{version_number}",

            "ready":
                delivery_ready,

            "technical_ready":
                technical_ready,

            "status":
                delivery_status,

            "client_decision":
                client_decision,

            "client_comment":
                client_comment,

            "client_decision_review_attempt":
                client_decision_review_attempt,

            "client_decided_at":
                (
                    client_message.created_at
                    if client_message
                    is not None
                    else None
                ),

            "client_action_required":
                client_action_required,

            "vera_approved":
                vera_approved,

            "vera_status":
                (
                    final_review.status
                    if final_review
                    is not None
                    else "pending"
                ),

            "corrections_requested":
                corrections_requested,

            "files_count":
                len(files),

            "total_size_bytes":
                total_size,

            "files":
                files,

            "message":
                delivery_message,
        },
    }
