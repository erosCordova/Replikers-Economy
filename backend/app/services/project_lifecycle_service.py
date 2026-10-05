from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import Session

from app.models.contract import (
    ACTIVE_CONTRACT_STATUSES,
    TaskContract,
)
from app.models.execution import (
    ExecutionArtifact,
    ExecutionWorkspace,
)
from app.models.project import Project
from app.models.project_specialist import (
    ProjectFinalReview,
    ProjectSpecialistOffer,
    ProjectSpecialistRequirement,
)
from app.models.qa import QAReview
from app.models.repliker import Repliker
from app.models.task import Task
from app.models.user import User
from app.services.activity_service import (
    record_activity,
)
from app.services.contract_service import (
    select_contracts_for_project,
)
from app.services.economy_service import (
    finalize_project_economy,
    project_has_sufficient_custody,
    settle_contract_earnings,
    sync_project_payment_status,
)
from app.services.delegation_service import (
    run_delegation_cycle_for_contract,
)
from app.services.execution_agent_service import (
    run_contract_execution,
)
from app.services.message_service import (
    record_message,
)
from app.services.specialist_coverage_service import (
    enforce_project_specialist_gate,
)
from app.services.qa_evaluation_service import (
    evaluate_contract_qa,
)
from app.services.qa_service import (
    get_latest_qa_review,
    prepare_qa_review,
)
from app.services.qa_workflow_service import (
    build_followup,
)


FUNDED_STATUSES = {
    "paid",
    "funded",
    "escrowed",
    "admin_free",
}


class ProjectLifecycleError(
    ValueError
):
    pass


@dataclass
class ExecutionStageResult:
    review_ids: list[int]

    execution_attempts: int

    failed_contract_ids: list[int]


@dataclass
class QAStageResult:
    qa_attempts: int

    retry_execution_attempts: int

    qa_passed: int

    qa_failed: int

    completed_contract_ids: list[int]

    failed_contract_ids: list[int]


def get_project(
    *,
    db: Session,
    project_id: int,
) -> Project:
    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise ProjectLifecycleError(
            "Proyecto no encontrado."
        )

    return project


def _project_client(
    *,
    db: Session,
    project: Project,
) -> User:
    client = db.get(
        User,
        project.client_id,
    )

    if client is None:
        raise ProjectLifecycleError(
            "El cliente del proyecto "
            "no existe."
        )

    return client


def project_is_funded(
    *,
    db: Session,
    project: Project,
) -> bool:
    sync_project_payment_status(
        db=db,
        project=project,
    )

    return (
        project_has_sufficient_custody(
            db=db,
            project=project,
        )
    )


def run_planning_stage(
    *,
    db: Session,
    project_id: int,
) -> dict:
    project = get_project(
        db=db,
        project_id=project_id,
    )

    task_count = int(
        db.scalar(
            select(
                func.count(
                    Task.id
                )
            )
            .where(
                Task.project_id
                == project.id
            )
        )
        or 0
    )

    if task_count > 0:
        return {
            "tasks_created": 0,
            "task_count": task_count,
            "skipped": True,
        }

    client = _project_client(
        db=db,
        project=project,
    )

    # Adaptador sobre la etapa ya validada.
    # Evita duplicar la logica R00 existente.
    from app.api.routes.coordinator import (
        plan_project,
    )

    response = plan_project(
        project_id=project.id,
        db=db,
        current_user=client,
    )

    db.expire_all()

    return {
        "tasks_created":
            len(response.tasks),
        "task_count":
            len(response.tasks),
        "skipped":
            False,
    }


def _eligible_market_task_count(
    *,
    db: Session,
    project_id: int,
) -> int:
    return int(
        db.scalar(
            select(
                func.count(
                    Task.id
                )
            )
            .where(
                Task.project_id
                == project_id,
                Task.status.in_(
                    [
                        "planned",
                        "open",
                    ]
                ),
            )
        )
        or 0
    )


def _official_iris_id(
    *,
    db: Session,
) -> int | None:
    """
    Busca la instancia oficial de Iris.

    Devuelve None en bases antiguas o pruebas
    aisladas que todavía no tengan cargado el
    catálogo oficial.
    """

    from app.replikers.catalogo_web import (
        get_web_repliker,
    )
    from app.services.web_repliker_registry_service import (
        ECOSYSTEM_OWNER_EMAIL,
    )

    definition = get_web_repliker(
        "product_requirements"
    )

    if definition is None:
        return None

    owner_id = db.scalar(
        select(
            User.id
        )
        .where(
            User.email
            == ECOSYSTEM_OWNER_EMAIL
        )
    )

    if owner_id is None:
        return None

    iris_id = db.scalar(
        select(
            Repliker.id
        )
        .where(
            Repliker.owner_id
            == owner_id,
            Repliker.name
            == definition.name,
            Repliker.specialty
            == definition.specialty,
            Repliker.is_active
            .is_(True),
        )
    )

    if iris_id is None:
        return None

    return int(
        iris_id
    )


def _run_specialist_recruitment_stage(
    *,
    db: Session,
    project_id: int,
) -> dict:
    """
    Ejecuta el reclutamiento de puestos que
    requieren aceptación explícita.

    Actualmente cubre el puesto independiente
    de Revisor Final.
    """

    from app.services.specialist_recruitment_service import (
        run_project_specialist_recruitment,
    )

    iris_id = _official_iris_id(
        db=db
    )

    result = (
        run_project_specialist_recruitment(
            db=db,
            project_id=project_id,
            iris_id=iris_id,
        )
    )

    db.expire_all()

    return {
        "requirements_processed":
            result.requirements_processed,
        "candidates_considered":
            result.candidates_considered,
        "offers_sent":
            result.offers_sent,
        "accepted":
            result.accepted,
        "rejected":
            result.rejected,
        "errors":
            list(
                result.errors
            ),
    }



def run_market_stage(
    *,
    db: Session,
    project_id: int,
) -> dict:
    project = get_project(
        db=db,
        project_id=project_id,
    )

    eligible_count = (
        _eligible_market_task_count(
            db=db,
            project_id=project.id,
        )
    )

    tasks_processed = 0
    new_decisions = 0
    bid_count = 0
    pass_count = 0

    errors: list[str] = []

    # El mercado de tareas se ejecuta solamente
    # si todavía existen tareas abiertas o
    # planificadas.
    if eligible_count > 0:
        client = _project_client(
            db=db,
            project=project,
        )

        # Conservamos el mercado de tareas
        # validado en fases anteriores.
        from app.api.routes.market import (
            run_autonomous_market,
        )

        response = run_autonomous_market(
            project_id=project.id,
            db=db,
            current_user=client,
        )

        db.expire_all()

        tasks_processed = (
            response.tasks_processed
        )

        new_decisions = (
            response.new_decisions
        )

        bid_count = (
            response.bid_count
        )

        pass_count = (
            response.pass_count
        )

        errors.extend(
            response.errors
        )

    # Los puestos independientes del proyecto
    # se reclutan aunque ya no existan tareas
    # abiertas. Esto permite que Iris complete
    # la cobertura obligatoria antes de ejecutar.
    specialist = (
        _run_specialist_recruitment_stage(
            db=db,
            project_id=project.id,
        )
    )

    errors.extend(
        specialist["errors"]
    )

    specialist_attempted = (
        specialist[
            "requirements_processed"
        ]
        > 0
    )

    return {
        "tasks_processed":
            tasks_processed,
        "new_decisions":
            new_decisions,
        "bid_count":
            bid_count,
        "pass_count":
            pass_count,
        "errors":
            errors,
        "skipped": (
            eligible_count == 0
            and not specialist_attempted
        ),
        "specialist_requirements":
            specialist[
                "requirements_processed"
            ],
        "specialist_candidates":
            specialist[
                "candidates_considered"
            ],
        "specialist_offers":
            specialist[
                "offers_sent"
            ],
        "specialist_accepted":
            specialist[
                "accepted"
            ],
        "specialist_rejected":
            specialist[
                "rejected"
            ],
    }

def active_contract_ids(
    *,
    db: Session,
    project_id: int,
) -> list[int]:
    return list(
        db.scalars(
            select(
                TaskContract.id
            )
            .where(
                TaskContract.project_id
                == project_id,
                TaskContract.status.in_(
                    ACTIVE_CONTRACT_STATUSES
                ),
            )
            .order_by(
                TaskContract.id
            )
        ).all()
    )


def run_contracting_stage(
    *,
    db: Session,
    project_id: int,
) -> dict:
    project = get_project(
        db=db,
        project_id=project_id,
    )

    if not project_is_funded(
        db=db,
        project=project,
    ):
        raise ProjectLifecycleError(
            "El proyecto debe estar "
            "financiado antes de contratar."
        )

    # Si el proyecto se reanuda mientras
    # espera una especialidad obligatoria,
    # Iris vuelve a buscar candidatos nuevos.
    _run_specialist_recruitment_stage(
        db=db,
        project_id=project.id,
    )

    open_tasks = int(
        db.scalar(
            select(
                func.count(
                    Task.id
                )
            )
            .where(
                Task.project_id
                == project.id,
                Task.status == "open",
            )
        )
        or 0
    )

    created_count = 0

    if open_tasks > 0:
        outcome = (
            select_contracts_for_project(
                db=db,
                project_id=project.id,
            )
        )

        created_count = len(
            outcome.contracts_created
        )

        db.commit()

    ids = active_contract_ids(
        db=db,
        project_id=project.id,
    )

    coverage = (
        enforce_project_specialist_gate(
            db=db,
            project_id=project.id,
        )
    )

    db.commit()

    return {
        "contracts_created":
            created_count,
        "contract_ids":
            ids,
        "specialist_coverage_ready":
            coverage.ready,
        "mandatory_specialists":
            coverage.mandatory_total,
        "covered_specialists":
            coverage.mandatory_covered,
        "missing_specialties":
            list(
                coverage.missing_specialties
            ),
    }


def run_delegation_stage(
    *,
    db: Session,
    contract_ids: list[int],
) -> dict:
    processed = 0

    delegated = 0

    decisions = []

    for contract_id in contract_ids:
        outcome = (
            run_delegation_cycle_for_contract(
                db=db,
                contract_id=contract_id,
            )
        )

        db.commit()

        processed += 1

        if outcome.decision == "delegate":
            delegated += 1

        decisions.append(
            {
                "contract_id":
                    contract_id,
                "decision":
                    outcome.decision,
                "reason":
                    outcome.reason,
            }
        )

    return {
        "processed":
            processed,
        "delegated":
            delegated,
        "decisions":
            decisions,
    }


def _workspace_artifact_count(
    *,
    db: Session,
    contract_id: int,
) -> int:
    workspace_id = db.scalar(
        select(
            ExecutionWorkspace.id
        )
        .where(
            ExecutionWorkspace.contract_id
            == contract_id
        )
        .order_by(
            ExecutionWorkspace.id.desc()
        )
        .limit(1)
    )

    if workspace_id is None:
        return 0

    return int(
        db.scalar(
            select(
                func.count(
                    ExecutionArtifact.id
                )
            )
            .where(
                ExecutionArtifact.workspace_id
                == workspace_id
            )
        )
        or 0
    )


def run_execution_stage(
    *,
    db: Session,
    contract_ids: list[int],
) -> ExecutionStageResult:
    review_ids: list[int] = []

    failed_contract_ids: list[int] = []

    execution_attempts = 0

    for contract_id in contract_ids:
        review = get_latest_qa_review(
            db=db,
            contract_id=contract_id,
        )

        if review is not None:
            review_ids.append(
                review.id
            )

            continue

        artifact_count = (
            _workspace_artifact_count(
                db=db,
                contract_id=contract_id,
            )
        )

        if artifact_count <= 0:
            state = (
                run_contract_execution(
                    db=db,
                    contract_id=contract_id,
                )
            )

            execution_attempts += 1

            status = str(
                state.get(
                    "status",
                    "unknown",
                )
            )

            produced = int(
                state.get(
                    "artifact_count",
                    0,
                )
            )

            if (
                status != "completed"
                or produced <= 0
            ):
                failed_contract_ids.append(
                    contract_id
                )

                continue

        review = prepare_qa_review(
            db=db,
            contract_id=contract_id,
        )

        db.commit()

        review_ids.append(
            review.id
        )

    return ExecutionStageResult(
        review_ids=
            review_ids,
        execution_attempts=
            execution_attempts,
        failed_contract_ids=
            failed_contract_ids,
    )


def _mark_contract_completed(
    *,
    db: Session,
    contract_id: int,
):
    contract = db.get(
        TaskContract,
        contract_id,
    )

    if contract is None:
        raise ProjectLifecycleError(
            "Contrato no encontrado "
            "al finalizar QA."
        )

    if contract.status == "completed":
        return

    task = db.get(
        Task,
        contract.task_id,
    )

    repliker = db.get(
        Repliker,
        contract.repliker_id,
    )

    contract.status = "completed"

    db.flush()

    settle_contract_earnings(
        db=db,
        contract_id=contract.id,
    )

    if task is not None:
        task.status = "completed"

    db.flush()

    if repliker is not None:
        other_active = int(
            db.scalar(
                select(
                    func.count(
                        TaskContract.id
                    )
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
            )
            or 0
        )

        if other_active == 0:
            repliker.status = (
                "available"
            )

    record_activity(
        db=db,
        actor_type="system",
        event_type="qa_delivery_accepted",
        project_id=contract.project_id,
        task_id=contract.task_id,
        repliker_id=contract.repliker_id,
        title=(
            "Entrega aprobada por QA"
        ),
        description=(
            f"El contrato #{contract.id} "
            "cumplio los criterios "
            "verificables y fue completado."
        ),
    )

    record_message(
        db=db,
        project_id=contract.project_id,
        task_id=contract.task_id,
        sender_type="qa",
        receiver_type="project",
        message_type="qa_approved",
        content=(
            f"La entrega del contrato "
            f"#{contract.id} fue aprobada "
            "por QA."
        ),
    )

    db.commit()


def run_qa_stage(
    *,
    db: Session,
    contract_ids: list[int],
) -> QAStageResult:
    qa_attempts = 0

    retry_execution_attempts = 0

    qa_passed = 0

    qa_failed = 0

    completed_contract_ids: list[int] = []

    failed_contract_ids: list[int] = []

    for contract_id in contract_ids:
        review = get_latest_qa_review(
            db=db,
            contract_id=contract_id,
        )

        if review is None:
            failed_contract_ids.append(
                contract_id
            )

            qa_failed += 1

            continue

        loop_guard = 0

        while loop_guard < 8:
            loop_guard += 1

            if review.status in {
                "prepared",
                "running",
            }:
                review = (
                    evaluate_contract_qa(
                        db=db,
                        contract_id=
                            contract_id,
                    )
                )

                db.commit()

                qa_attempts += 1

            followup = build_followup(
                db=db,
                review=review,
                run_retry=True,
            )

            action = str(
                followup["action"]
            )

            if action == "complete":
                _mark_contract_completed(
                    db=db,
                    contract_id=
                        contract_id,
                )

                qa_passed += 1

                completed_contract_ids.append(
                    contract_id
                )

                break

            if action == "retry":
                retry = (
                    followup["retry"]
                )

                if (
                    retry is not None
                    and retry.status
                    == "completed"
                    and retry.next_review_id
                    is not None
                ):
                    retry_execution_attempts += 1

                    next_review = db.get(
                        QAReview,
                        retry.next_review_id,
                    )

                    if next_review is None:
                        failed_contract_ids.append(
                            contract_id
                        )

                        qa_failed += 1

                        break

                    review = next_review

                    continue

                failed_contract_ids.append(
                    contract_id
                )

                qa_failed += 1

                break

            # exhausted / manual_review /
            # cualquier estado no automatico.
            failed_contract_ids.append(
                contract_id
            )

            qa_failed += 1

            break

        else:
            failed_contract_ids.append(
                contract_id
            )

            qa_failed += 1

    return QAStageResult(
        qa_attempts=
            qa_attempts,
        retry_execution_attempts=
            retry_execution_attempts,
        qa_passed=
            qa_passed,
        qa_failed=
            qa_failed,
        completed_contract_ids=
            completed_contract_ids,
        failed_contract_ids=
            failed_contract_ids,
    )


def finalize_project_if_ready(
    *,
    db: Session,
    project_id: int,
) -> dict:
    project = get_project(
        db=db,
        project_id=project_id,
    )

    total_tasks = int(
        db.scalar(
            select(
                func.count(
                    Task.id
                )
            )
            .where(
                Task.project_id
                == project.id
            )
        )
        or 0
    )

    completed_tasks = int(
        db.scalar(
            select(
                func.count(
                    Task.id
                )
            )
            .where(
                Task.project_id
                == project.id,
                Task.status == "completed",
            )
        )
        or 0
    )

    tasks_ready = (
        total_tasks > 0
        and completed_tasks
        == total_tasks
    )

    final_requirement = db.scalar(
        select(
            ProjectSpecialistRequirement
        )
        .where(
            ProjectSpecialistRequirement
            .project_id
            == project.id,
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

    # Compatibilidad:
    # los proyectos antiguos creados antes
    # de la compuerta final conservan el
    # comportamiento histórico.
    final_review_required = (
        final_requirement is not None
    )

    final_review = None
    final_review_status = (
        "not_required"
    )

    reviewer_accepted = False

    if final_requirement is not None:
        assigned_id = (
            final_requirement
            .assigned_repliker_id
        )

        if assigned_id is not None:
            reviewer_accepted = (
                db.scalar(
                    select(
                        ProjectSpecialistOffer.id
                    )
                    .where(
                        ProjectSpecialistOffer
                        .requirement_id
                        == final_requirement.id,
                        ProjectSpecialistOffer
                        .repliker_id
                        == assigned_id,
                        ProjectSpecialistOffer
                        .status
                        == "accepted",
                    )
                    .limit(1)
                )
                is not None
            )

        if reviewer_accepted:
            final_review = db.scalar(
                select(
                    ProjectFinalReview
                )
                .where(
                    ProjectFinalReview
                    .project_id
                    == project.id,
                    ProjectFinalReview
                    .requirement_id
                    == final_requirement.id,
                    ProjectFinalReview
                    .reviewer_repliker_id
                    == assigned_id,
                )
                .order_by(
                    ProjectFinalReview
                    .attempt_number
                    .desc(),
                    ProjectFinalReview
                    .id
                    .desc(),
                )
                .limit(1)
            )

        if not reviewer_accepted:
            final_review_status = (
                "reviewer_missing"
            )

        elif final_review is None:
            final_review_status = (
                "pending"
            )

        else:
            final_review_status = (
                final_review.status
            )

    final_approved = (
        not final_review_required
        or (
            reviewer_accepted
            and final_review is not None
            and final_review.status
            == "approved"
        )
    )

    completed = (
        tasks_ready
        and final_approved
    )

    if (
        tasks_ready
        and final_review_required
        and not final_approved
    ):
        if (
            final_review_status
            == "corrections_requested"
        ):
            project.status = (
                "corrections_requested"
            )
        else:
            project.status = (
                "awaiting_final_review"
            )

        db.commit()

    if completed:
        was_completed = (
            project.status
            == "completed"
        )

        project.status = "completed"

        # La economía solo puede liquidarse
        # después de la aprobación final.
        finalize_project_economy(
            db=db,
            project_id=project.id,
        )

        if not was_completed:
            record_activity(
                db=db,
                actor_type="system",
                event_type=(
                    "project_completed"
                ),
                project_id=
                    project.id,
                title=(
                    "Proyecto completado"
                ),
                description=(
                    f"Las {total_tasks} tareas "
                    "fueron aprobadas y la "
                    "revisión final autorizó "
                    "la entrega."
                    if final_review_required
                    else (
                        f"Las {total_tasks} tareas "
                        "fueron ejecutadas y "
                        "aprobadas por QA."
                    )
                ),
            )

            record_message(
                db=db,
                project_id=
                    project.id,
                sender_type="system",
                receiver_type="client",
                message_type=(
                    "project_completed"
                ),
                content=(
                    f"El proyecto "
                    f"'{project.title}' "
                    "ha completado todas "
                    "sus verificaciones y "
                    "está aprobado para entrega."
                    if final_review_required
                    else (
                        f"El proyecto "
                        f"'{project.title}' "
                        "ha completado todas "
                        "sus tareas verificadas."
                    )
                ),
            )

        db.commit()

    return {
        "completed":
            completed,
        "total_tasks":
            total_tasks,
        "completed_tasks":
            completed_tasks,
        "project_status":
            project.status,
        "final_review_required":
            final_review_required,
        "final_review_status":
            final_review_status,
        "final_review_id": (
            final_review.id
            if final_review is not None
            else None
        ),
        "final_reviewer_id": (
            final_requirement
            .assigned_repliker_id
            if final_requirement
            is not None
            else None
        ),
    }
