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

from app.agentic.final_review_runtime import (
    run_final_review_agent,
)
from app.models.project import (
    Project,
    ProjectRequirement,
)
from app.models.project_specialist import (
    ProjectFinalReview,
    ProjectSpecialistOffer,
    ProjectSpecialistRequirement,
)
from app.models.qa import (
    QACriterionResult,
    QAReview,
)
from app.models.repliker import Repliker
from app.models.task import (
    Task,
    TaskAcceptanceCriterion,
)
from app.schemas.final_review import (
    FinalReviewDecisionAI,
)
from app.services.project_delivery_snapshot_service import (
    DeliverySnapshotError,
    ensure_delivery_snapshot,
)
from app.services.activity_service import (
    record_activity,
)
from app.services.message_service import (
    record_message,
)


FinalReviewEvaluator = Callable[
    ...,
    FinalReviewDecisionAI,
]


class FinalReviewError(
    ValueError
):
    pass


def _final_requirement(
    *,
    db: Session,
    project_id: int,
) -> ProjectSpecialistRequirement | None:
    return db.scalar(
        select(
            ProjectSpecialistRequirement
        )
        .where(
            ProjectSpecialistRequirement
            .project_id
            == project_id,
            ProjectSpecialistRequirement
            .is_mandatory
            .is_(True),
            ProjectSpecialistRequirement
            .is_final_gate
            .is_(True),
        )
        .order_by(
            ProjectSpecialistRequirement.id
        )
        .limit(1)
    )


def _accepted_reviewer(
    *,
    db: Session,
    requirement:
        ProjectSpecialistRequirement,
) -> Repliker | None:
    repliker_id = (
        requirement
        .assigned_repliker_id
    )

    if repliker_id is None:
        return None

    accepted = db.scalar(
        select(
            ProjectSpecialistOffer.id
        )
        .where(
            ProjectSpecialistOffer
            .requirement_id
            == requirement.id,
            ProjectSpecialistOffer
            .repliker_id
            == repliker_id,
            ProjectSpecialistOffer
            .status
            == "accepted",
        )
        .limit(1)
    )

    if accepted is None:
        return None

    return db.get(
        Repliker,
        repliker_id,
    )


def _latest_final_review(
    *,
    db: Session,
    project_id: int,
) -> ProjectFinalReview | None:
    return db.scalar(
        select(
            ProjectFinalReview
        )
        .where(
            ProjectFinalReview.project_id
            == project_id
        )
        .order_by(
            ProjectFinalReview
            .attempt_number
            .desc(),
            ProjectFinalReview.id.desc(),
        )
        .limit(1)
    )


def _review_result(
    *,
    project: Project,
    review: ProjectFinalReview,
) -> dict:
    try:
        corrections = json.loads(
            review.corrections_json
            or "[]"
        )
    except json.JSONDecodeError:
        corrections = []

    return {
        "review_id":
            review.id,
        "reviewer_id":
            review.reviewer_repliker_id,
        "attempt_number":
            review.attempt_number,
        "status":
            review.status,
        "score":
            review.score,
        "summary":
            review.summary,
        "corrections":
            corrections,
        "completed": (
            project.status
            == "completed"
        ),
        "project_status":
            project.status,
    }


def _project_context(
    *,
    db: Session,
    project: Project,
) -> dict:
    requirements = list(
        db.scalars(
            select(
                ProjectRequirement
            )
            .where(
                ProjectRequirement.project_id
                == project.id
            )
            .order_by(
                ProjectRequirement.id
            )
        ).all()
    )

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

    task_context: list[dict] = []

    for task in tasks:
        criteria = list(
            db.scalars(
                select(
                    TaskAcceptanceCriterion
                )
                .where(
                    TaskAcceptanceCriterion.task_id
                    == task.id
                )
                .order_by(
                    TaskAcceptanceCriterion.id
                )
            ).all()
        )

        latest_qa = db.scalar(
            select(
                QAReview
            )
            .where(
                QAReview.task_id
                == task.id
            )
            .order_by(
                QAReview.attempt_number.desc(),
                QAReview.id.desc(),
            )
            .limit(1)
        )

        qa_criteria: list[dict] = []

        if latest_qa is not None:
            rows = list(
                db.scalars(
                    select(
                        QACriterionResult
                    )
                    .where(
                        QACriterionResult.review_id
                        == latest_qa.id
                    )
                    .order_by(
                        QACriterionResult.id
                    )
                ).all()
            )

            qa_criteria = [
                {
                    "criterion_id":
                        row.criterion_id,
                    "status":
                        row.status,
                    "score":
                        row.score,
                    "reason":
                        row.reason,
                    "evidence_summary":
                        row.evidence_summary,
                }
                for row in rows
            ]

        task_context.append(
            {
                "id":
                    task.id,
                "titulo":
                    task.title,
                "descripcion":
                    task.description,
                "especialidad":
                    task.required_specialty,
                "estado":
                    task.status,
                "criterios_aceptacion": [
                    {
                        "id":
                            criterion.id,
                        "descripcion":
                            criterion.description,
                        "estado":
                            criterion.status,
                        "evidencia":
                            criterion.evidence,
                        "obligatorio":
                            criterion.is_mandatory,
                    }
                    for criterion in criteria
                ],
                "ultima_revision_qa": (
                    {
                        "id":
                            latest_qa.id,
                        "estado":
                            latest_qa.status,
                        "puntaje":
                            latest_qa.score,
                        "resumen":
                            latest_qa.summary,
                        "criterios":
                            qa_criteria,
                    }
                    if latest_qa is not None
                    else None
                ),
            }
        )

    return {
        "id":
            project.id,
        "titulo":
            project.title,
        "descripcion":
            project.description,
        "estado":
            project.status,
        "requisitos": [
            {
                "id":
                    requirement.id,
                "titulo":
                    requirement.title,
                "descripcion":
                    requirement.description,
                "obligatorio":
                    requirement.is_mandatory,
                "estado_verificacion":
                    requirement
                    .verification_status,
            }
            for requirement
            in requirements
        ],
        "tareas":
            task_context,
    }


def run_project_final_review(
    *,
    db: Session,
    project_id: int,
    evaluator:
        FinalReviewEvaluator | None = None,
) -> dict:
    if evaluator is None:
        evaluator = (
            run_final_review_agent
        )

    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise FinalReviewError(
            "Proyecto no encontrado."
        )

    requirement = _final_requirement(
        db=db,
        project_id=project.id,
    )

    if requirement is None:
        return {
            "review_id": None,
            "reviewer_id": None,
            "attempt_number": 0,
            "status": "not_required",
            "score": None,
            "summary": (
                "El proyecto no requiere "
                "revisión final."
            ),
            "corrections": [],
            "completed": (
                project.status
                == "completed"
            ),
            "project_status":
                project.status,
        }

    reviewer = _accepted_reviewer(
        db=db,
        requirement=requirement,
    )

    if reviewer is None:
        raise FinalReviewError(
            "El proyecto no tiene un Repliker "
            "aceptado para la revisión final."
        )

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
        raise FinalReviewError(
            "El proyecto no contiene tareas."
        )

    if any(
        task.status != "completed"
        for task in tasks
    ):
        raise FinalReviewError(
            "La revisión final no puede comenzar "
            "hasta que todas las tareas hayan "
            "sido aprobadas."
        )

    latest = _latest_final_review(
        db=db,
        project_id=project.id,
    )

    if (
        latest is not None
        and latest.status
        == "approved"
    ):
        from app.services.project_lifecycle_service import (
            finalize_project_if_ready,
        )

        finalize_project_if_ready(
            db=db,
            project_id=project.id,
        )

        db.refresh(
            project
        )

        return _review_result(
            project=project,
            review=latest,
        )

    # No repetimos la revisión sobre exactamente
    # la misma entrega si Vera ya pidió cambios.
    # El flujo de correcciones abrirá un nuevo
    # intento cuando los cambios estén listos.
    if (
        latest is not None
        and latest.status
        == "corrections_requested"
        and project.status
        == "corrections_requested"
    ):
        return _review_result(
            project=project,
            review=latest,
        )

    project_context = _project_context(
        db=db,
        project=project,
    )

    reviewer_data = {
        "id":
            reviewer.id,
        "nombre":
            reviewer.name,
        "especialidad":
            "Revisor Final",
        "descripcion":
            reviewer.description,
        "reputacion":
            reviewer.reputation_score,
        "trabajos_completados":
            reviewer.jobs_completed,
        "habilidades": [
            {
                "nombre":
                    skill.name,
                "nivel":
                    skill.level,
            }
            for skill
            in reviewer.skills
        ],
    }

    if (
        latest is not None
        and latest.status
        in {
            "pending",
            "running",
        }
    ):
        review = latest
        review.status = "running"

    else:
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

        review = ProjectFinalReview(
            project_id=
                project.id,
            requirement_id=
                requirement.id,
            reviewer_repliker_id=
                reviewer.id,
            attempt_number=
                max_attempt + 1,
            status="running",
        )

        db.add(
            review
        )

        db.flush()

    review_id = review.id

    record_activity(
        db=db,
        actor_type="repliker",
        event_type=(
            "final_review_started"
        ),
        project_id=project.id,
        repliker_id=reviewer.id,
        title=(
            f"{reviewer.name} inició "
            "la revisión final"
        ),
        description=(
            "La entrega completa está siendo "
            "revisada antes de autorizar "
            "su entrega al cliente."
        ),
    )

    record_message(
        db=db,
        project_id=project.id,
        sender_type="repliker",
        sender_repliker_id=
            reviewer.id,
        receiver_type="project",
        message_type=(
            "final_review_started"
        ),
        content=(
            "Estoy revisando la entrega completa, "
            "sus requisitos y los resultados "
            "de calidad antes de decidir."
        ),
    )

    # La transacción debe cerrarse ANTES
    # de esperar una respuesta de IA.
    db.commit()

    try:
        decision = evaluator(
            reviewer_data=
                reviewer_data,
            project_context=
                project_context,
        )

        valid_task_ids = {
            task.id
            for task in tasks
        }

        if (
            decision.decision
            == "approve"
            and decision.corrections
        ):
            raise FinalReviewError(
                "Una aprobación final no puede "
                "contener correcciones pendientes."
            )

        if (
            decision.decision
            == "request_corrections"
            and not decision.corrections
        ):
            raise FinalReviewError(
                "La solicitud de correcciones "
                "debe indicar al menos un cambio."
            )

        invalid_task_ids = {
            correction.task_id
            for correction
            in decision.corrections
            if correction.task_id
            not in valid_task_ids
        }

        if invalid_task_ids:
            raise FinalReviewError(
                "La revisión final mencionó "
                "tareas que no pertenecen "
                "al proyecto."
            )

        review = db.get(
            ProjectFinalReview,
            review_id,
        )

        if review is None:
            raise FinalReviewError(
                "La revisión final desapareció "
                "durante la evaluación."
            )

        review.score = (
            decision.score
        )

        review.summary = (
            decision.summary
        )

        review.reasoning = (
            decision.reasoning
        )

        review.completed_at = (
            datetime.now(
                timezone.utc
            )
        )

        review.corrections_json = (
            json.dumps(
                [
                    {
                        "task_id":
                            correction.task_id,
                        "instruction":
                            correction.instruction,
                        "severity":
                            correction.severity,
                    }
                    for correction
                    in decision.corrections
                ],
                ensure_ascii=False,
            )
        )

        if (
            decision.decision
            == "approve"
        ):
            review.status = "approved"

            db.flush()

            try:
                ensure_delivery_snapshot(
                    db=db,
                    project_id=project.id,
                    final_review_id=review.id,
                )

            except DeliverySnapshotError as exc:
                record_activity(
                    db=db,
                    actor_type="system",
                    event_type=(
                        "delivery_snapshot_pending"
                    ),
                    project_id=project.id,
                    title=(
                        "Paquete de entrega pendiente"
                    ),
                    description=(
                        "Vera aprobó la versión, "
                        "pero todavía no se pudo "
                        "crear su paquete de archivos. "
                        f"Detalle: {str(exc)[:500]}"
                    ),
                )

            record_activity(
                db=db,
                actor_type="repliker",
                event_type=(
                    "final_review_approved"
                ),
                project_id=project.id,
                repliker_id=reviewer.id,
                title=(
                    f"{reviewer.name} aprobó "
                    "la entrega final"
                ),
                description=
                    decision.summary,
            )

            record_message(
                db=db,
                project_id=project.id,
                sender_type="repliker",
                sender_repliker_id=
                    reviewer.id,
                receiver_type="client",
                message_type=(
                    "final_review_approved"
                ),
                content=(
                    decision.summary
                ),
            )

        else:
            review.status = (
                "corrections_requested"
            )

            project.status = (
                "corrections_requested"
            )

            record_activity(
                db=db,
                actor_type="repliker",
                event_type=(
                    "final_review_corrections"
                ),
                project_id=project.id,
                repliker_id=reviewer.id,
                title=(
                    f"{reviewer.name} solicitó "
                    "correcciones"
                ),
                description=(
                    decision.summary
                ),
            )

            record_message(
                db=db,
                project_id=project.id,
                sender_type="repliker",
                sender_repliker_id=
                    reviewer.id,
                receiver_type="project",
                message_type=(
                    "final_review_corrections"
                ),
                content=(
                    decision.summary
                ),
            )

        db.commit()

    except Exception as exc:
        db.rollback()

        failed = db.get(
            ProjectFinalReview,
            review_id,
        )

        if (
            failed is not None
            and failed.status
            not in {
                "approved",
                "corrections_requested",
            }
        ):
            failed.status = "failed"
            failed.summary = (
                "No fue posible completar "
                "la revisión final."
            )
            failed.reasoning = (
                str(exc)[:4000]
            )
            failed.completed_at = (
                datetime.now(
                    timezone.utc
                )
            )

            db.commit()

        raise

    if (
        review.status
        == "approved"
    ):
        from app.services.project_lifecycle_service import (
            finalize_project_if_ready,
        )

        finalize_project_if_ready(
            db=db,
            project_id=project.id,
        )

        db.refresh(
            project
        )

    return _review_result(
        project=project,
        review=review,
    )
