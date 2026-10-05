from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contract import TaskContract
from app.models.economy import (
    LedgerTransaction,
)
from app.models.ecosystem import (
    AgentActivityEvent,
)
from app.models.project import Project
from app.models.project_specialist import (
    ProjectFinalReview,
)
from app.models.qa import QAReview
from app.models.repliker import Repliker
from app.models.task import Task
from app.services.project_report_service import (
    build_project_report_delivery,
)


VALID_CONTRACT_STATUSES = {
    "awarded",
    "active",
    "completed",
}


STAGE_LABELS = {
    "planning":
        "Planificación",

    "market":
        "Búsqueda de especialistas",

    "contracting":
        "Contratación",

    "execution":
        "Ejecución",

    "qa":
        "Pruebas y control de calidad",

    "final_review":
        "Revisión final de Vera",

    "corrections":
        "Correcciones",

    "completed":
        "Completado",

    "blocked":
        "Bloqueado",

    "failed":
        "Fallido",

    "cancelled":
        "Cancelado",
}


NEXT_ACTIONS = {
    "planning": (
        "Completar la planificación "
        "y definir las tareas."
    ),

    "market": (
        "Encontrar los Repliker "
        "necesarios para las tareas."
    ),

    "contracting": (
        "Completar la contratación "
        "del equipo necesario."
    ),

    "execution": (
        "Continuar la ejecución "
        "de las tareas pendientes."
    ),

    "qa": (
        "Completar las pruebas "
        "y verificaciones pendientes."
    ),

    "final_review": (
        "Esperar la revisión final "
        "de Vera."
    ),

    "corrections": (
        "Resolver las correcciones "
        "solicitadas por Vera."
    ),

    "completed": (
        "El proyecto está listo "
        "para la entrega al cliente."
    ),

    "blocked": (
        "Resolver el bloqueo "
        "antes de continuar."
    ),

    "failed": (
        "Revisar la incidencia "
        "que detuvo el proyecto."
    ),

    "cancelled": (
        "El proyecto fue cancelado."
    ),
}


def _normalize(
    value: str | None,
) -> str:
    return (
        value
        or ""
    ).strip().lower()


def _current_stage(
    project: Project,
) -> str:
    status = _normalize(
        project.status
    )

    if status == "completed":
        return "completed"

    if status in {
        "corrections_requested",
        "client_corrections_requested",
        "correcting",
    }:
        return "corrections"

    if status in {
        "awaiting_final_review",
        "final_review",
    }:
        return "final_review"

    if status in {
        "qa",
        "testing",
    }:
        return "qa"

    if status in {
        "executing",
        "running",
        "execution",
        "contracted",
    }:
        return "execution"

    if status in {
        "partially_contracted",
        "contracting",
    }:
        return "contracting"

    if status in {
        "planned",
        "market",
        "market_open",
        "open",
    }:
        return "market"

    if status == "blocked":
        return "blocked"

    if status == "failed":
        return "failed"

    if status in {
        "cancelled",
        "canceled",
    }:
        return "cancelled"

    return "planning"


def _latest_qa_by_contract(
    reviews: list[QAReview],
) -> dict[int, QAReview]:
    latest: dict[int, QAReview] = {}

    for review in reviews:
        current = latest.get(
            review.contract_id
        )

        if (
            current is None
            or review.attempt_number
            > current.attempt_number
        ):
            latest[
                review.contract_id
            ] = review

    return latest


def _progress_percent(
    *,
    project: Project,
    tasks: list[Task],
    contracts: list[TaskContract],
    latest_qa: dict[int, QAReview],
    final_review: ProjectFinalReview | None,
) -> tuple[int, dict[str, float]]:
    total_tasks = len(tasks)

    planning = (
        1.0
        if total_tasks > 0
        else 0.0
    )

    contracted_task_ids = {
        contract.task_id
        for contract in contracts
        if _normalize(
            contract.status
        )
        in VALID_CONTRACT_STATUSES
    }

    if total_tasks > 0:
        contracting = min(
            1.0,
            (
                len(
                    contracted_task_ids
                )
                / total_tasks
            ),
        )
    else:
        contracting = 0.0

    completed_task_ids = {
        task.id
        for task in tasks
        if _normalize(
            task.status
        )
        == "completed"
    }

    if total_tasks > 0:
        execution = (
            len(
                completed_task_ids
            )
            / total_tasks
        )
    else:
        execution = 0.0

    passed_task_ids = {
        review.task_id
        for review
        in latest_qa.values()
        if _normalize(
            review.status
        )
        == "passed"
    }

    if total_tasks > 0:
        qa = min(
            1.0,
            (
                len(
                    passed_task_ids
                )
                / total_tasks
            ),
        )
    else:
        qa = 0.0

    final_review_value = (
        1.0
        if (
            final_review is not None
            and _normalize(
                final_review.status
            )
            == "approved"
        )
        else 0.0
    )

    parts = {
        "planning":
            round(
                planning,
                4,
            ),

        "contracting":
            round(
                contracting,
                4,
            ),

        "execution":
            round(
                execution,
                4,
            ),

        "qa":
            round(
                qa,
                4,
            ),

        "final_review":
            round(
                final_review_value,
                4,
            ),
    }

    progress = round(
        (
            sum(
                parts.values()
            )
            / len(parts)
        )
        * 100
    )

    return (
        max(
            0,
            min(
                100,
                progress,
            ),
        ),
        parts,
    )


def build_project_tracking(
    *,
    db: Session,
    project: Project,
) -> dict:
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

    contracts = list(
        db.scalars(
            select(
                TaskContract
            )
            .where(
                TaskContract.project_id
                == project.id
            )
            .order_by(
                TaskContract.id
            )
        ).all()
    )

    qa_reviews = list(
        db.scalars(
            select(
                QAReview
            )
            .join(
                Task,
                Task.id
                == QAReview.task_id,
            )
            .where(
                Task.project_id
                == project.id
            )
            .order_by(
                QAReview.contract_id,
                QAReview.attempt_number,
            )
        ).all()
    )

    latest_qa = (
        _latest_qa_by_contract(
            qa_reviews
        )
    )

    final_review = db.scalar(
        select(
            ProjectFinalReview
        )
        .where(
            ProjectFinalReview.project_id
            == project.id
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

    activity = list(
        db.scalars(
            select(
                AgentActivityEvent
            )
            .where(
                AgentActivityEvent
                .project_id
                == project.id
            )
            .order_by(
                AgentActivityEvent
                .created_at
                .desc(),
                AgentActivityEvent
                .id
                .desc(),
            )
            .limit(20)
        ).all()
    )

    ledger = list(
        db.scalars(
            select(
                LedgerTransaction
            )
            .where(
                LedgerTransaction
                .project_id
                == project.id
            )
            .order_by(
                LedgerTransaction
                .created_at
                .desc(),
                LedgerTransaction
                .id
                .desc(),
            )
        ).all()
    )

    stage = _current_stage(
        project
    )

    (
        progress_percent,
        progress_parts,
    ) = _progress_percent(
        project=project,
        tasks=tasks,
        contracts=contracts,
        latest_qa=latest_qa,
        final_review=final_review,
    )

    completed_tasks = sum(
        1
        for task in tasks
        if _normalize(
            task.status
        )
        == "completed"
    )

    active_tasks = sum(
        1
        for task in tasks
        if _normalize(
            task.status
        )
        in {
            "executing",
            "running",
            "active",
            "in_progress",
        }
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

    qa_pending = sum(
        1
        for review
        in latest_qa.values()
        if _normalize(
            review.status
        )
        in {
            "prepared",
            "running",
            "needs_review",
        }
    )

    contracted_cents = sum(
        contract.amount_cents
        for contract in contracts
        if _normalize(
            contract.status
        )
        in VALID_CONTRACT_STATUSES
    )

    funded_cents = sum(
        transaction.amount_cents
        for transaction in ledger
        if _normalize(
            transaction.transaction_type
        )
        == "funding"
    )

    earnings_cents = sum(
        transaction.amount_cents
        for transaction in ledger
        if _normalize(
            transaction.transaction_type
        )
        == "earning"
    )

    commission_cents = sum(
        transaction.amount_cents
        for transaction in ledger
        if _normalize(
            transaction.transaction_type
        )
        == "commission"
    )

    budget_limit = (
        project.budget_limit_cents
        or 0
    )

    if budget_limit > 0:
        remaining_budget = max(
            0,
            budget_limit
            - contracted_cents,
        )
    else:
        remaining_budget = None

    team_ids = {
        contract.repliker_id
        for contract in contracts
        if _normalize(
            contract.status
        )
        in VALID_CONTRACT_STATUSES
    }

    if final_review is not None:
        team_ids.add(
            final_review
            .reviewer_repliker_id
        )

    if team_ids:
        team_rows = list(
            db.scalars(
                select(
                    Repliker
                )
                .where(
                    Repliker.id.in_(
                        team_ids
                    )
                )
                .order_by(
                    Repliker.id
                )
            ).all()
        )
    else:
        team_rows = []

    contract_counts: dict[int, int] = {}

    for contract in contracts:
        if (
            _normalize(
                contract.status
            )
            not in VALID_CONTRACT_STATUSES
        ):
            continue

        contract_counts[
            contract.repliker_id
        ] = (
            contract_counts.get(
                contract.repliker_id,
                0,
            )
            + 1
        )

    if final_review is not None:
        final_reviewer_id = (
            final_review
            .reviewer_repliker_id
        )
    else:
        final_reviewer_id = None

    team = [
        {
            "repliker_id":
                repliker.id,

            "name":
                repliker.name,

            "specialty":
                repliker.specialty,

            "status":
                repliker.status,

            "active_contracts":
                contract_counts.get(
                    repliker.id,
                    0,
                ),

            "is_final_reviewer":
                (
                    repliker.id
                    == final_reviewer_id
                ),
        }
        for repliker in team_rows
    ]

    corrections_count = 0

    if final_review is not None:
        try:
            corrections = json.loads(
                final_review
                .corrections_json
                or "[]"
            )

            if isinstance(
                corrections,
                list,
            ):
                corrections_count = (
                    len(corrections)
                )

        except (
            json.JSONDecodeError,
            TypeError,
        ):
            corrections_count = 0

    reviewer_name = None

    if final_reviewer_id is not None:
        reviewer = next(
            (
                repliker
                for repliker
                in team_rows
                if (
                    repliker.id
                    == final_reviewer_id
                )
            ),
            None,
        )

        if reviewer is not None:
            reviewer_name = (
                reviewer.name
            )

    report_delivery = (
        build_project_report_delivery(
            db=db,
            project=project,
            tasks=tasks,
            latest_qa=latest_qa,
            final_review=final_review,
            progress_percent=
                progress_percent,
            stage_label=
                STAGE_LABELS.get(
                    stage,
                    "En proceso",
                ),
        )
    )

    return {
        "project_id":
            project.id,

        "project_title":
            project.title,

        "project_status":
            project.status,

        "stage":
            stage,

        "stage_label":
            STAGE_LABELS.get(
                stage,
                "En proceso",
            ),

        "next_action":
            NEXT_ACTIONS.get(
                stage,
                "Continuar con el proyecto.",
            ),

        "progress_percent":
            progress_percent,

        "progress_basis":
            progress_parts,

        "tasks": {
            "total":
                len(tasks),

            "completed":
                completed_tasks,

            "active":
                active_tasks,

            "pending":
                max(
                    0,
                    len(tasks)
                    - completed_tasks
                    - active_tasks,
                ),

            "items": [
                {
                    "id":
                        task.id,

                    "title":
                        task.title,

                    "status":
                        task.status,

                    "required_specialty":
                        task.required_specialty,

                    "max_budget_cents":
                        task.max_budget_cents,
                }
                for task in tasks
            ],
        },

        "qa": {
            "reviews_total":
                len(qa_reviews),

            "latest_reviews":
                len(latest_qa),

            "passed":
                qa_passed,

            "failed":
                qa_failed,

            "pending":
                qa_pending,
        },

        "team": {
            "total":
                len(team),

            "members":
                team,
        },

        "budget": {
            "currency":
                project.currency,

            "budget_limit_cents":
                project.budget_limit_cents,

            "quoted_amount_cents":
                project.quoted_amount_cents,

            "contracted_cents":
                contracted_cents,

            "funded_cents":
                funded_cents,

            "earnings_cents":
                earnings_cents,

            "commission_cents":
                commission_cents,

            "remaining_budget_cents":
                remaining_budget,

            "payment_status":
                project.payment_status,

            "is_admin_free":
                bool(
                    getattr(
                        project,
                        "is_admin_free",
                        False,
                    )
                ),
        },

        "final_review": (
            {
                "id":
                    final_review.id,

                "attempt_number":
                    final_review
                    .attempt_number,

                "status":
                    final_review.status,

                "score":
                    final_review.score,

                "summary":
                    final_review.summary,

                "corrections_count":
                    corrections_count,

                "reviewer_repliker_id":
                    final_reviewer_id,

                "reviewer_name":
                    reviewer_name,

                "completed_at":
                    final_review.completed_at,
            }
            if final_review is not None
            else None
        ),

        "report":
            report_delivery[
                "report"
            ],

        "delivery":
            report_delivery[
                "delivery"
            ],

        "recent_activity": [
            {
                "id":
                    event.id,

                "task_id":
                    event.task_id,

                "repliker_id":
                    event.repliker_id,

                "actor_type":
                    event.actor_type,

                "event_type":
                    event.event_type,

                "title":
                    event.title,

                "description":
                    event.description,

                "created_at":
                    event.created_at,
            }
            for event in activity
        ],
    }
