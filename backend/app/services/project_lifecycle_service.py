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
from app.services.delegation_service import (
    run_delegation_cycle_for_contract,
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
    project: Project,
) -> bool:
    return (
        project.payment_status
        in FUNDED_STATUSES
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

    if eligible_count == 0:
        return {
            "tasks_processed": 0,
            "new_decisions": 0,
            "bid_count": 0,
            "pass_count": 0,
            "errors": [],
            "skipped": True,
        }

    client = _project_client(
        db=db,
        project=project,
    )

    # Conservamos la implementacion del
    # mercado que ya fue validada en fases
    # anteriores.
    from app.api.routes.market import (
        run_autonomous_market,
    )

    response = run_autonomous_market(
        project_id=project.id,
        db=db,
        current_user=client,
    )

    db.expire_all()

    return {
        "tasks_processed":
            response.tasks_processed,
        "new_decisions":
            response.new_decisions,
        "bid_count":
            response.bid_count,
        "pass_count":
            response.pass_count,
        "errors":
            list(response.errors),
        "skipped":
            False,
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
        project
    ):
        raise ProjectLifecycleError(
            "El proyecto debe estar "
            "financiado antes de contratar."
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

    return {
        "contracts_created":
            created_count,
        "contract_ids":
            ids,
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

    completed = (
        total_tasks > 0
        and completed_tasks
        == total_tasks
    )

    if completed:
        was_completed = (
            project.status
            == "completed"
        )

        project.status = "completed"

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
                    "fueron ejecutadas y "
                    "aprobadas por QA."
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
                    "sus tareas verificadas."
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
    }
