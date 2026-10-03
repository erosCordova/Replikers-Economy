from __future__ import annotations

import json

from datetime import (
    datetime,
    timezone,
)
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contract import (
    ACTIVE_CONTRACT_STATUSES,
    TaskContract,
)
from app.models.project import Project
from app.models.project_specialist import (
    ProjectFinalCorrectionRun,
    ProjectFinalReview,
)
from app.models.qa import QAReview
from app.models.repliker import Repliker
from app.models.task import Task
from app.services.activity_service import (
    record_activity,
)
from app.services.execution_agent_service import (
    run_contract_execution,
)
from app.services.message_service import (
    record_message,
)
from app.services.qa_evaluation_service import (
    evaluate_contract_qa,
)
from app.services.qa_service import (
    prepare_qa_review,
)
from app.services.qa_workflow_service import (
    MAX_QA_ATTEMPTS,
    retry_review,
)


CorrectionExecutor = Callable[..., dict]
QAEvaluator = Callable[..., QAReview]


class FinalCorrectionError(
    ValueError
):
    pass


def _latest_correction_review(
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
            == project_id,
            ProjectFinalReview.status
            == "corrections_requested",
        )
        .order_by(
            ProjectFinalReview
            .attempt_number
            .desc(),
            ProjectFinalReview.id.desc(),
        )
        .limit(1)
    )


def _parse_corrections(
    review: ProjectFinalReview,
) -> dict[int, list[dict]]:
    try:
        raw = json.loads(
            review.corrections_json
            or "[]"
        )

    except json.JSONDecodeError as exc:
        raise FinalCorrectionError(
            "Las correcciones de la revisión "
            "final no son válidas."
        ) from exc

    if not isinstance(
        raw,
        list,
    ):
        raise FinalCorrectionError(
            "Las correcciones de la revisión "
            "final deben ser una lista."
        )

    grouped: dict[
        int,
        list[dict],
    ] = {}

    for item in raw:
        if not isinstance(
            item,
            dict,
        ):
            continue

        try:
            task_id = int(
                item.get(
                    "task_id"
                )
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise FinalCorrectionError(
                "Una corrección no contiene "
                "una tarea válida."
            ) from exc

        instruction = str(
            item.get(
                "instruction",
                "",
            )
        ).strip()

        if not instruction:
            raise FinalCorrectionError(
                "Una corrección no contiene "
                "instrucciones."
            )

        severity = str(
            item.get(
                "severity",
                "medium",
            )
        ).strip().lower()

        grouped.setdefault(
            task_id,
            [],
        ).append(
            {
                "instruction":
                    instruction,
                "severity":
                    severity,
            }
        )

    if not grouped:
        raise FinalCorrectionError(
            "La revisión final no contiene "
            "correcciones ejecutables."
        )

    return grouped


def _task_contract(
    *,
    db: Session,
    project_id: int,
    task_id: int,
) -> TaskContract | None:
    active = db.scalar(
        select(
            TaskContract
        )
        .where(
            TaskContract.project_id
            == project_id,
            TaskContract.task_id
            == task_id,
            TaskContract.status.in_(
                ACTIVE_CONTRACT_STATUSES
            ),
        )
        .order_by(
            TaskContract.id.desc()
        )
        .limit(1)
    )

    if active is not None:
        return active

    return db.scalar(
        select(
            TaskContract
        )
        .where(
            TaskContract.project_id
            == project_id,
            TaskContract.task_id
            == task_id,
            TaskContract.status
            == "completed",
        )
        .order_by(
            TaskContract.id.desc()
        )
        .limit(1)
    )


def _build_instruction(
    *,
    project: Project,
    task: Task,
    corrections: list[dict],
) -> str:
    severity_labels = {
        "low":
            "leve",
        "medium":
            "media",
        "high":
            "alta",
    }

    lines = [
        (
            "Vera solicitó correcciones "
            "antes de aprobar la entrega final."
        ),
        "",
        (
            f"Proyecto: {project.title}"
        ),
        (
            f"Tarea: {task.title}"
        ),
        "",
        "CORRECCIONES OBLIGATORIAS:",
    ]

    for index, item in enumerate(
        corrections,
        start=1,
    ):
        severity = severity_labels.get(
            item["severity"],
            "media",
        )

        lines.append(
            (
                f"{index}. Prioridad {severity}: "
                f"{item['instruction']}"
            )
        )

    lines.extend(
        [
            "",
            (
                "Modifica la entrega existente "
                "en tu mismo espacio de trabajo."
            ),
            (
                "Conserva todo lo que ya está "
                "correcto y cambia únicamente "
                "lo necesario."
            ),
            (
                "La corrección volverá a pasar "
                "por control de calidad antes "
                "de regresar a Vera."
            ),
        ]
    )

    return "\n".join(
        lines
    )[:12000]


def _restore_completed_state(
    *,
    db: Session,
    contract: TaskContract,
    task: Task,
    repliker: Repliker,
):
    contract.status = "completed"

    task.status = "completed"

    other_active = int(
        db.scalar(
            select(
                TaskContract.id
            )
            .where(
                TaskContract.repliker_id
                == repliker.id,
                TaskContract.id
                != contract.id,
                TaskContract.status.in_(
                    ACTIVE_CONTRACT_STATUSES
                ),
            )
            .limit(1)
        )
        is not None
    )

    if other_active == 0:
        repliker.status = "available"


def _evaluate_correction_qa(
    *,
    db: Session,
    contract_id: int,
    qa_evaluator: QAEvaluator,
    retry_executor:
        CorrectionExecutor,
) -> tuple[
    QAReview,
    bool,
]:
    review = prepare_qa_review(
        db=db,
        contract_id=contract_id,
    )

    db.commit()

    guard = 0

    while guard < (
        MAX_QA_ATTEMPTS + 2
    ):
        guard += 1

        if review.status in {
            "prepared",
            "running",
        }:
            review = qa_evaluator(
                db=db,
                contract_id=contract_id,
            )

            db.commit()

        if review.status == "passed":
            return (
                review,
                True,
            )

        if review.status not in {
            "failed",
            "needs_review",
        }:
            return (
                review,
                False,
            )

        if (
            review.attempt_number
            >= MAX_QA_ATTEMPTS
        ):
            return (
                review,
                False,
            )

        retry = retry_review(
            db=db,
            review=review,
            executor=
                retry_executor,
        )

        if (
            retry.status
            != "completed"
            or retry.next_review_id
            is None
        ):
            return (
                review,
                False,
            )

        next_review = db.get(
            QAReview,
            retry.next_review_id,
        )

        if next_review is None:
            return (
                review,
                False,
            )

        review = next_review

    return (
        review,
        False,
    )


def run_final_review_corrections(
    *,
    db: Session,
    project_id: int,
    executor:
        CorrectionExecutor | None = None,
    qa_evaluator:
        QAEvaluator | None = None,
) -> dict:
    if executor is None:
        executor = (
            run_contract_execution
        )

    if qa_evaluator is None:
        qa_evaluator = (
            evaluate_contract_qa
        )

    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise FinalCorrectionError(
            "Proyecto no encontrado."
        )

    final_review = (
        _latest_correction_review(
            db=db,
            project_id=project.id,
        )
    )

    if final_review is None:
        raise FinalCorrectionError(
            "No existe una revisión final "
            "con correcciones pendientes."
        )

    grouped = _parse_corrections(
        final_review
    )

    completed_count = 0
    failed_count = 0

    run_ids: list[int] = []

    for (
        task_id,
        corrections,
    ) in grouped.items():
        task = db.get(
            Task,
            task_id,
        )

        if (
            task is None
            or task.project_id
            != project.id
        ):
            raise FinalCorrectionError(
                "Vera indicó una tarea que "
                "no pertenece al proyecto."
            )

        contract = _task_contract(
            db=db,
            project_id=project.id,
            task_id=task.id,
        )

        if contract is None:
            raise FinalCorrectionError(
                "No existe un contrato "
                "responsable de la tarea "
                f"#{task.id}."
            )

        repliker = db.get(
            Repliker,
            contract.repliker_id,
        )

        if repliker is None:
            raise FinalCorrectionError(
                "El Repliker responsable "
                "ya no existe."
            )

        run = db.scalar(
            select(
                ProjectFinalCorrectionRun
            )
            .where(
                ProjectFinalCorrectionRun
                .final_review_id
                == final_review.id,
                ProjectFinalCorrectionRun
                .task_id
                == task.id,
            )
        )

        if (
            run is not None
            and run.status
            == "completed"
        ):
            run_ids.append(
                run.id
            )

            completed_count += 1

            continue

        instruction = (
            _build_instruction(
                project=project,
                task=task,
                corrections=corrections,
            )
        )

        if run is None:
            run = (
                ProjectFinalCorrectionRun(
                    final_review_id=
                        final_review.id,
                    project_id=
                        project.id,
                    task_id=
                        task.id,
                    contract_id=
                        contract.id,
                    repliker_id=
                        repliker.id,
                    status="pending",
                    instruction=
                        instruction,
                )
            )

            db.add(
                run
            )

            db.flush()

        else:
            run.contract_id = (
                contract.id
            )

            run.repliker_id = (
                repliker.id
            )

            run.instruction = (
                instruction
            )

        run.status = "running"

        run.execution_status = (
            "running"
        )

        run.error_summary = ""

        run.qa_review_id = None

        run.completed_at = None

        contract.status = "active"

        task.status = "in_progress"

        repliker.status = "busy"

        project.status = (
            "corrections_requested"
        )

        record_activity(
            db=db,
            actor_type="repliker",
            event_type=(
                "final_correction_assigned"
            ),
            project_id=project.id,
            task_id=task.id,
            repliker_id=
                final_review
                .reviewer_repliker_id,
            title=(
                "Vera devolvió una tarea "
                "para corrección"
            ),
            description=(
                f"{repliker.name} debe "
                "corregir la entrega antes "
                "de una nueva revisión final."
            ),
        )

        record_message(
            db=db,
            project_id=project.id,
            task_id=task.id,
            sender_type="repliker",
            sender_repliker_id=
                final_review
                .reviewer_repliker_id,
            receiver_type="repliker",
            receiver_repliker_id=
                repliker.id,
            message_type=(
                "final_correction_request"
            ),
            content=instruction,
        )

        run_id = run.id
        contract_id = contract.id
        task_id_value = task.id
        repliker_id = repliker.id

        run_ids.append(
            run_id
        )

        # Fundamental:
        # no dejamos una transacción abierta
        # mientras el Repliker ejecuta IA.
        db.commit()

        try:
            state = executor(
                db=db,
                contract_id=
                    contract_id,
                instruction=
                    instruction,
            )

        except Exception as exc:
            db.rollback()

            run = db.get(
                ProjectFinalCorrectionRun,
                run_id,
            )

            contract = db.get(
                TaskContract,
                contract_id,
            )

            task = db.get(
                Task,
                task_id_value,
            )

            repliker = db.get(
                Repliker,
                repliker_id,
            )

            if run is not None:
                run.status = "failed"

                run.execution_status = (
                    "failed"
                )

                run.error_summary = (
                    str(exc)[:4000]
                )

                run.completed_at = (
                    datetime.now(
                        timezone.utc
                    )
                )

            if (
                contract is not None
                and task is not None
                and repliker is not None
            ):
                _restore_completed_state(
                    db=db,
                    contract=contract,
                    task=task,
                    repliker=repliker,
                )

            project = db.get(
                Project,
                project_id,
            )

            if project is not None:
                project.status = (
                    "corrections_requested"
                )

            db.commit()

            failed_count += 1

            continue

        status = str(
            state.get(
                "status",
                "",
            )
        )

        artifact_count = int(
            state.get(
                "artifact_count",
                0,
            )
        )

        run = db.get(
            ProjectFinalCorrectionRun,
            run_id,
        )

        contract = db.get(
            TaskContract,
            contract_id,
        )

        task = db.get(
            Task,
            task_id_value,
        )

        repliker = db.get(
            Repliker,
            repliker_id,
        )

        if (
            run is None
            or contract is None
            or task is None
            or repliker is None
        ):
            raise FinalCorrectionError(
                "El estado de la corrección "
                "se volvió inconsistente."
            )

        run.execution_status = (
            status
        )

        if (
            status != "completed"
            or artifact_count <= 0
        ):
            run.status = "failed"

            run.error_summary = (
                "El Repliker no produjo "
                "cambios verificables."
            )

            run.completed_at = (
                datetime.now(
                    timezone.utc
                )
            )

            _restore_completed_state(
                db=db,
                contract=contract,
                task=task,
                repliker=repliker,
            )

            project.status = (
                "corrections_requested"
            )

            db.commit()

            failed_count += 1

            continue

        run.status = "qa_running"

        db.commit()

        try:
            qa_review, qa_passed = (
                _evaluate_correction_qa(
                    db=db,
                    contract_id=
                        contract.id,
                    qa_evaluator=
                        qa_evaluator,
                    retry_executor=
                        executor,
                )
            )

        except Exception as exc:
            db.rollback()

            run = db.get(
                ProjectFinalCorrectionRun,
                run_id,
            )

            contract = db.get(
                TaskContract,
                contract_id,
            )

            task = db.get(
                Task,
                task_id_value,
            )

            repliker = db.get(
                Repliker,
                repliker_id,
            )

            if run is not None:
                run.status = "failed"

                run.error_summary = (
                    str(exc)[:4000]
                )

                run.completed_at = (
                    datetime.now(
                        timezone.utc
                    )
                )

            if (
                contract is not None
                and task is not None
                and repliker is not None
            ):
                _restore_completed_state(
                    db=db,
                    contract=contract,
                    task=task,
                    repliker=repliker,
                )

            project = db.get(
                Project,
                project_id,
            )

            if project is not None:
                project.status = (
                    "corrections_requested"
                )

            db.commit()

            failed_count += 1

            continue

        run = db.get(
            ProjectFinalCorrectionRun,
            run_id,
        )

        contract = db.get(
            TaskContract,
            contract_id,
        )

        task = db.get(
            Task,
            task_id_value,
        )

        repliker = db.get(
            Repliker,
            repliker_id,
        )

        if (
            run is None
            or contract is None
            or task is None
            or repliker is None
        ):
            raise FinalCorrectionError(
                "No fue posible cerrar "
                "la corrección."
            )

        run.qa_review_id = (
            qa_review.id
        )

        _restore_completed_state(
            db=db,
            contract=contract,
            task=task,
            repliker=repliker,
        )

        if qa_passed:
            run.status = "completed"

            run.completed_at = (
                datetime.now(
                    timezone.utc
                )
            )

            record_activity(
                db=db,
                actor_type="qa",
                event_type=(
                    "final_correction_verified"
                ),
                project_id=project.id,
                task_id=task.id,
                repliker_id=
                    repliker.id,
                title=(
                    "Corrección verificada"
                ),
                description=(
                    "La tarea corregida superó "
                    "nuevamente el control "
                    "de calidad."
                ),
            )

            record_message(
                db=db,
                project_id=project.id,
                task_id=task.id,
                sender_type="qa",
                receiver_type="project",
                message_type=(
                    "final_correction_verified"
                ),
                content=(
                    "La corrección solicitada "
                    "por Vera fue aplicada y "
                    "verificada correctamente."
                ),
            )

            completed_count += 1

        else:
            run.status = "failed"

            run.error_summary = (
                "La corrección no superó "
                "el control de calidad."
            )

            run.completed_at = (
                datetime.now(
                    timezone.utc
                )
            )

            failed_count += 1

        db.commit()

    total = len(
        grouped
    )

    ready = (
        completed_count == total
        and failed_count == 0
    )

    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise FinalCorrectionError(
            "Proyecto no encontrado "
            "al cerrar correcciones."
        )

    if ready:
        project.status = (
            "awaiting_final_review"
        )

        record_activity(
            db=db,
            actor_type="system",
            event_type=(
                "final_corrections_completed"
            ),
            project_id=project.id,
            title=(
                "Correcciones listas "
                "para nueva revisión"
            ),
            description=(
                "Todas las correcciones "
                "solicitadas por Vera fueron "
                "aplicadas y verificadas."
            ),
        )

        record_message(
            db=db,
            project_id=project.id,
            sender_type="system",
            receiver_type="repliker",
            receiver_repliker_id=
                final_review
                .reviewer_repliker_id,
            message_type=(
                "final_corrections_completed"
            ),
            content=(
                "Las correcciones que solicitaste "
                "ya fueron aplicadas y superaron "
                "el control de calidad. Puedes "
                "realizar una nueva revisión final."
            ),
        )

    else:
        project.status = (
            "corrections_requested"
        )

    db.commit()

    return {
        "final_review_id":
            final_review.id,
        "correction_run_ids":
            run_ids,
        "total":
            total,
        "completed":
            completed_count,
        "failed":
            failed_count,
        "ready_for_final_review":
            ready,
        "project_status":
            project.status,
        "summary": (
            "Todas las correcciones "
            "fueron verificadas."
            if ready
            else (
                "Todavía existen correcciones "
                "que no superaron el control "
                "de calidad."
            )
        ),
    }
