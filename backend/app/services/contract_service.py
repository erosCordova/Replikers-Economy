from dataclasses import dataclass
import unicodedata

from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import (
    Session,
    selectinload,
)

from app.models.contract import (
    ACTIVE_CONTRACT_STATUSES,
    TaskContract,
)
from app.models.project import Project
from app.models.repliker import Repliker
from app.models.task import (
    Task,
    TaskBid,
)
from app.services.activity_service import (
    record_activity,
)
from app.services.message_service import (
    record_message,
)


SELECTION_POLICY_VERSION = "r00-selection-v1"

MINIMUM_SKILL_SCORE = 45


class ContractSelectionError(Exception):
    pass


@dataclass
class CandidateEvaluation:
    bid: TaskBid
    repliker: Repliker

    skill_score: int
    reputation_score: int
    confidence_score: int
    price_score: int
    time_score: int
    risk_score: int

    selection_score: int


@dataclass
class SelectionTaskOutcome:
    task: Task
    contract: TaskContract | None
    reason: str | None


@dataclass
class SelectionOutcome:
    project: Project

    contracts_created: list[TaskContract]
    task_results: list[SelectionTaskOutcome]

    reserved_budget_cents: int
    remaining_budget_cents: int


def _normalize_skill(
    value: str,
) -> str:
    value = value.strip().lower()

    normalized = unicodedata.normalize(
        "NFKD",
        value,
    )

    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(
            character
        )
    )

    return " ".join(
        normalized
        .replace("_", " ")
        .replace("-", " ")
        .split()
    )


def _skill_score(
    *,
    task: Task,
    repliker: Repliker,
) -> int:
    requirements = list(
        task.required_skills
    )

    if not requirements:
        return 100

    repliker_skills = {
        _normalize_skill(
            skill.name
        ): skill.level
        for skill in repliker.skills
    }

    scores: list[float] = []

    for requirement in requirements:
        required_level = max(
            requirement.minimum_level,
            1,
        )

        actual_level = repliker_skills.get(
            _normalize_skill(
                requirement.skill_name
            ),
            0,
        )

        ratio = min(
            actual_level / required_level,
            1.0,
        )

        scores.append(
            ratio * 100
        )

    return round(
        sum(scores) / len(scores)
    )


def _price_score(
    *,
    amount_cents: int,
    task_budget_cents: int | None,
) -> int:
    if (
        task_budget_cents is None
        or task_budget_cents <= 0
    ):
        return 60

    ratio = (
        amount_cents
        / task_budget_cents
    )

    if ratio > 1:
        return 0

    return max(
        25,
        min(
            100,
            round(
                100
                - ratio * 50
            ),
        ),
    )


def _time_score(
    *,
    estimated_minutes: int | None,
    complexity: int,
) -> int:
    if (
        estimated_minutes is None
        or estimated_minutes <= 0
    ):
        return 40

    expected_minutes = max(
        30,
        complexity * 5,
    )

    ratio = (
        estimated_minutes
        / expected_minutes
    )

    if ratio <= 1:
        return 100

    return max(
        20,
        round(
            100
            - (ratio - 1) * 50
        ),
    )


def _risk_score(
    *,
    skill_score: int,
    reputation_score: int,
    confidence_score: int,
    jobs_completed: int,
) -> int:
    experience_score = min(
        100,
        40
        + jobs_completed * 12,
    )

    score = (
        reputation_score * 0.30
        + confidence_score * 0.30
        + skill_score * 0.25
        + experience_score * 0.15
    )

    return max(
        0,
        min(
            100,
            round(score),
        ),
    )


def evaluate_bid(
    *,
    task: Task,
    bid: TaskBid,
    repliker: Repliker,
) -> CandidateEvaluation:
    skill = _skill_score(
        task=task,
        repliker=repliker,
    )

    reputation = max(
        0,
        min(
            100,
            repliker.reputation_score,
        ),
    )

    confidence = max(
        0,
        min(
            100,
            bid.confidence_score,
        ),
    )

    price = _price_score(
        amount_cents=bid.amount_cents,
        task_budget_cents=
            task.max_budget_cents,
    )

    time = _time_score(
        estimated_minutes=
            bid.estimated_minutes,
        complexity=task.complexity,
    )

    risk = _risk_score(
        skill_score=skill,
        reputation_score=reputation,
        confidence_score=confidence,
        jobs_completed=
            repliker.jobs_completed,
    )

    total = round(
        skill * 0.30
        + reputation * 0.15
        + confidence * 0.15
        + price * 0.15
        + time * 0.10
        + risk * 0.15
    )

    return CandidateEvaluation(
        bid=bid,
        repliker=repliker,
        skill_score=skill,
        reputation_score=reputation,
        confidence_score=confidence,
        price_score=price,
        time_score=time,
        risk_score=risk,
        selection_score=total,
    )


def _selection_summary(
    evaluation: CandidateEvaluation,
) -> str:
    return (
        f"R00 selecciono esta oferta con "
        f"{evaluation.selection_score}/100. "
        f"Habilidades: "
        f"{evaluation.skill_score}/100; "
        f"reputacion: "
        f"{evaluation.reputation_score}/100; "
        f"confianza: "
        f"{evaluation.confidence_score}/100; "
        f"precio: "
        f"{evaluation.price_score}/100; "
        f"tiempo: "
        f"{evaluation.time_score}/100; "
        f"confiabilidad operativa: "
        f"{evaluation.risk_score}/100."
    )


def _reserved_budget(
    *,
    db: Session,
    project_id: int,
) -> int:
    value = db.scalar(
        select(
            func.coalesce(
                func.sum(
                    TaskContract.reserved_cents
                ),
                0,
            )
        )
        .where(
            TaskContract.project_id
            == project_id,
            TaskContract.status.in_(
                ACTIVE_CONTRACT_STATUSES
            ),
        )
    )

    return int(
        value or 0
    )


def _busy_repliker_ids(
    *,
    db: Session,
) -> set[int]:
    return set(
        db.scalars(
            select(
                TaskContract.repliker_id
            )
            .where(
                TaskContract.status.in_(
                    ACTIVE_CONTRACT_STATUSES
                )
            )
        ).all()
    )


def select_contracts_for_project(
    *,
    db: Session,
    project_id: int,
) -> SelectionOutcome:
    project = db.scalar(
        select(Project)
        .where(
            Project.id == project_id
        )
        .with_for_update()
    )

    if project is None:
        raise ContractSelectionError(
            "Proyecto no encontrado."
        )

    if project.status not in {
        "market_open",
        "partially_contracted",
        "contracted",
    }:
        raise ContractSelectionError(
            "El proyecto debe haber pasado "
            "por el mercado antes de contratar."
        )

    if project.payment_status not in {
        "paid",
        "funded",
        "escrowed",
    }:
        raise ContractSelectionError(
            "El proyecto debe estar financiado "
            "antes de formalizar contratos."
        )

    if (
        project.budget_limit_cents
        is None
        or project.budget_limit_cents <= 0
    ):
        raise ContractSelectionError(
            "El proyecto no tiene un "
            "presupuesto valido."
        )

    reserved = _reserved_budget(
        db=db,
        project_id=project.id,
    )

    remaining = (
        project.budget_limit_cents
        - reserved
    )

    if remaining < 0:
        raise ContractSelectionError(
            "El presupuesto reservado supera "
            "el limite del proyecto."
        )

    busy_replikers = (
        _busy_repliker_ids(
            db=db,
        )
    )

    tasks = list(
        db.scalars(
            select(Task)
            .options(
                selectinload(
                    Task.required_skills
                ),
                selectinload(
                    Task.acceptance_criteria
                ),
            )
            .where(
                Task.project_id
                == project.id,
                Task.status == "open",
            )
            .order_by(
                Task.id
            )
            .with_for_update()
        ).all()
    )

    created: list[
        TaskContract
    ] = []

    results: list[
        SelectionTaskOutcome
    ] = []

    for task in tasks:
        existing_contract = db.scalar(
            select(TaskContract)
            .where(
                TaskContract.task_id
                == task.id,
                TaskContract.status.in_(
                    ACTIVE_CONTRACT_STATUSES
                ),
            )
            .with_for_update()
        )

        if existing_contract:
            results.append(
                SelectionTaskOutcome(
                    task=task,
                    contract=None,
                    reason=(
                        "La tarea ya tiene "
                        "un contrato activo."
                    ),
                )
            )

            continue

        bids = list(
            db.scalars(
                select(TaskBid)
                .options(
                    selectinload(
                        TaskBid.repliker
                    ).selectinload(
                        Repliker.skills
                    )
                )
                .where(
                    TaskBid.task_id
                    == task.id,
                    TaskBid.status
                    == "pending",
                )
                .order_by(
                    TaskBid.id
                )
                .with_for_update()
            ).all()
        )

        candidates: list[
            CandidateEvaluation
        ] = []

        for bid in bids:
            repliker = bid.repliker

            if repliker is None:
                continue

            if not repliker.is_active:
                continue

            # Anti auto-contratacion.
            if (
                repliker.owner_id
                == project.client_id
            ):
                continue

            # Hasta que exista un scheduler de capacidad,
            # un Repliker solo mantiene un contrato activo.
            if (
                repliker.id
                in busy_replikers
            ):
                continue

            if bid.amount_cents <= 0:
                continue

            if (
                task.max_budget_cents
                is not None
                and bid.amount_cents
                > task.max_budget_cents
            ):
                continue

            if (
                bid.amount_cents
                > remaining
            ):
                continue

            evaluation = evaluate_bid(
                task=task,
                bid=bid,
                repliker=repliker,
            )

            if (
                evaluation.skill_score
                < MINIMUM_SKILL_SCORE
            ):
                continue

            candidates.append(
                evaluation
            )

        if not candidates:
            results.append(
                SelectionTaskOutcome(
                    task=task,
                    contract=None,
                    reason=(
                        "No existe una oferta "
                        "elegible dentro del "
                        "presupuesto y las "
                        "reglas de contratacion."
                    ),
                )
            )

            continue

        winner = max(
            candidates,
            key=lambda candidate: (
                candidate.selection_score,
                candidate.skill_score,
                candidate.risk_score,
                candidate.confidence_score,
                -candidate.bid.amount_cents,
                -(
                    candidate.bid
                    .estimated_minutes
                    or 10**9
                ),
                -candidate.bid.id,
            ),
        )

        summary = (
            _selection_summary(
                winner
            )
        )

        contract = TaskContract(
            project_id=project.id,
            task_id=task.id,
            bid_id=winner.bid.id,
            repliker_id=
                winner.repliker.id,
            status="awarded",
            currency=project.currency,
            amount_cents=
                winner.bid.amount_cents,
            reserved_cents=
                winner.bid.amount_cents,
            skill_score=
                winner.skill_score,
            reputation_score=
                winner.reputation_score,
            confidence_score=
                winner.confidence_score,
            price_score=
                winner.price_score,
            time_score=
                winner.time_score,
            risk_score=
                winner.risk_score,
            selection_score=
                winner.selection_score,
            selected_by="r00",
            selection_policy_version=(
                SELECTION_POLICY_VERSION
            ),
            selection_summary=summary,
        )

        db.add(
            contract
        )

        db.flush()

        for bid in bids:
            if (
                bid.id
                == winner.bid.id
            ):
                bid.status = "accepted"

            elif bid.status == "pending":
                bid.status = "rejected"

        task.status = "assigned"

        winner.repliker.status = (
            "assigned"
        )

        busy_replikers.add(
            winner.repliker.id
        )

        reserved += (
            winner.bid.amount_cents
        )

        remaining -= (
            winner.bid.amount_cents
        )

        record_activity(
            db=db,
            actor_type="r00",
            event_type="contract_awarded",
            project_id=project.id,
            task_id=task.id,
            repliker_id=
                winner.repliker.id,
            title=(
                f"R00 contrato a "
                f"{winner.repliker.name}"
            ),
            description=(
                f"Contrato #{contract.id} "
                f"asignado a '{task.title}' "
                f"por {project.currency} "
                f"{contract.amount_cents / 100:.2f}. "
                f"Score de seleccion: "
                f"{contract.selection_score}/100."
            ),
        )

        record_message(
            db=db,
            project_id=project.id,
            task_id=task.id,
            sender_type="r00",
            receiver_type="repliker",
            receiver_repliker_id=
                winner.repliker.id,
            message_type="contract_award",
            content=(
                f"Has sido seleccionado para "
                f"la tarea '{task.title}'. "
                f"Contrato #{contract.id}. "
                f"Importe reservado: "
                f"{project.currency} "
                f"{contract.amount_cents / 100:.2f}. "
                f"{summary}"
            ),
        )

        created.append(
            contract
        )

        results.append(
            SelectionTaskOutcome(
                task=task,
                contract=contract,
                reason=None,
            )
        )

    db.flush()

    total_tasks = (
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

    contracted_tasks = (
        db.scalar(
            select(
                func.count(
                    func.distinct(
                        TaskContract.task_id
                    )
                )
            )
            .where(
                TaskContract.project_id
                == project.id,
                TaskContract.status.in_(
                    ACTIVE_CONTRACT_STATUSES
                ),
            )
        )
        or 0
    )

    if (
        total_tasks > 0
        and contracted_tasks
        >= total_tasks
    ):
        project.status = "contracted"

    elif contracted_tasks > 0:
        project.status = (
            "partially_contracted"
        )

    if created:
        record_activity(
            db=db,
            actor_type="r00",
            event_type=(
                "selection_cycle_completed"
            ),
            project_id=project.id,
            title=(
                "R00 completo la seleccion "
                "de contratistas"
            ),
            description=(
                f"{len(created)} contratos "
                f"creados. Presupuesto "
                f"reservado acumulado: "
                f"{project.currency} "
                f"{reserved / 100:.2f}. "
                f"Presupuesto restante: "
                f"{project.currency} "
                f"{remaining / 100:.2f}."
            ),
        )

        record_message(
            db=db,
            project_id=project.id,
            sender_type="r00",
            receiver_type="project",
            message_type=(
                "selection_summary"
            ),
            content=(
                f"Finalice el ciclo de "
                f"seleccion. Se crearon "
                f"{len(created)} contratos. "
                f"El presupuesto reservado "
                f"es {project.currency} "
                f"{reserved / 100:.2f} y "
                f"quedan {project.currency} "
                f"{remaining / 100:.2f}."
            ),
        )

    db.flush()

    return SelectionOutcome(
        project=project,
        contracts_created=created,
        task_results=results,
        reserved_budget_cents=
            reserved,
        remaining_budget_cents=
            remaining,
    )
