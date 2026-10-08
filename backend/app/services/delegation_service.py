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
from app.models.delegation import (
    ACTIVE_SUBCONTRACT_STATUSES,
    DelegatedTask,
    DelegationOffer,
    DelegationRequest,
    Subcontract,
)
from app.models.project import Project
from app.models.repliker import (
    Repliker,
)
from app.models.task import Task
from app.schemas.delegation import (
    DelegatedTaskPublic,
    DelegationOfferPublic,
    DelegationProjectSnapshot,
    DelegationRequestPublic,
    SubcontractPublic,
)
from app.services.repliker_matching_service import (
    normalize_market_text,
    resolve_skill_level,
)
from app.services.activity_service import (
    record_activity,
)
from app.services.collaboration_service import (
    ensure_delegation_thread,
    send_collaboration_message,
)


MAX_DELEGATION_DEPTH = 3

MAX_DELEGATION_SHARE_PERCENT = 60

PRICING_POLICY_VERSION = (
    "delegation-sim-v1"
)


class DelegationError(Exception):
    pass


class DelegationValidationError(
    DelegationError
):
    pass


@dataclass
class DelegationRunOutcome:
    decision: str

    reason: str

    request: DelegationRequest | None


@dataclass
class CandidateScore:
    repliker: Repliker

    amount_cents: int

    skill_score: int
    reputation_score: int
    price_score: int
    experience_score: int
    risk_score: int

    selection_score: int


def _normalize_skill(
    value: str,
) -> str:
    value = (
        value
        .strip()
        .lower()
    )

    normalized = (
        unicodedata.normalize(
            "NFKD",
            value,
        )
    )

    normalized = "".join(
        character
        for character
        in normalized
        if not unicodedata
        .combining(
            character
        )
    )

    return " ".join(
        normalized
        .replace("_", " ")
        .replace("-", " ")
        .split()
    )


def _skill_level(
    *,
    repliker: Repliker,
    skill_name: str,
) -> int:
    actual_skills = {
        normalize_market_text(
            skill.name
        ): max(
            0,
            min(
                100,
                int(
                    skill.level
                ),
            ),
        )
        for skill in repliker.skills
    }

    return resolve_skill_level(
        required_name=skill_name,
        actual_skills=actual_skills,
    )


def _find_capability_gap(
    *,
    repliker: Repliker,
    requirements:
        list[
            tuple[
                str,
                int,
            ]
        ],
) -> tuple[
    str,
    int,
    int,
] | None:
    gaps = []

    for (
        skill_name,
        minimum_level,
    ) in requirements:
        actual_level = (
            _skill_level(
                repliker=repliker,
                skill_name=skill_name,
            )
        )

        if (
            actual_level
            < minimum_level
        ):
            ratio = (
                actual_level
                / max(
                    minimum_level,
                    1,
                )
            )

            gaps.append(
                (
                    ratio,
                    skill_name,
                    minimum_level,
                    actual_level,
                )
            )

    if not gaps:
        return None

    gaps.sort(
        key=lambda item:
            (
                item[0],
                item[3],
                item[1],
            )
    )

    _ratio, skill_name, minimum, actual = (
        gaps[0]
    )

    return (
        skill_name,
        minimum,
        actual,
    )


def _busy_repliker_ids(
    *,
    db: Session,
) -> set[int]:
    principal_ids = set(
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

    subcontractor_ids = set(
        db.scalars(
            select(
                Subcontract
                .subcontractor_repliker_id
            )
            .where(
                Subcontract.status.in_(
                    ACTIVE_SUBCONTRACT_STATUSES
                )
            )
        ).all()
    )

    return (
        principal_ids
        | subcontractor_ids
    )


def _chain_repliker_ids(
    *,
    db: Session,
    root_contract: TaskContract,
    parent_request_id: int | None,
) -> set[int]:
    result = {
        root_contract.repliker_id,
    }

    request_id = (
        parent_request_id
    )

    visited: set[int] = set()

    while request_id is not None:
        if request_id in visited:
            raise (
                DelegationValidationError(
                    "Se detecto un ciclo "
                    "en la cadena de delegacion."
                )
            )

        visited.add(
            request_id
        )

        request = db.get(
            DelegationRequest,
            request_id,
        )

        if request is None:
            break

        result.add(
            request
            .delegator_repliker_id
        )

        subcontract = db.scalar(
            select(Subcontract)
            .where(
                Subcontract
                .delegation_request_id
                == request.id
            )
        )

        if subcontract is not None:
            result.add(
                subcontract
                .subcontractor_repliker_id
            )

        request_id = (
            request
            .parent_request_id
        )

    return result


def _direct_delegated_sum(
    *,
    db: Session,
    root_contract_id: int,
    parent_request_id: int | None,
) -> int:
    statement = (
        select(
            func.coalesce(
                func.sum(
                    Subcontract
                    .amount_cents
                ),
                0,
            )
        )
        .join(
            DelegationRequest,
            DelegationRequest.id
            == Subcontract
            .delegation_request_id,
        )
        .where(
            DelegationRequest
            .root_contract_id
            == root_contract_id,
            Subcontract.status.in_(
                ACTIVE_SUBCONTRACT_STATUSES
            ),
        )
    )

    if parent_request_id is None:
        statement = (
            statement.where(
                DelegationRequest
                .parent_request_id
                .is_(None)
            )
        )
    else:
        statement = (
            statement.where(
                DelegationRequest
                .parent_request_id
                == parent_request_id
            )
        )

    value = db.scalar(
        statement
    )

    return int(
        value or 0
    )


def _available_delegation_budget(
    *,
    db: Session,
    root_contract: TaskContract,
    parent_request_id: int | None,
    source_amount_cents: int,
) -> int:
    maximum = (
        source_amount_cents
        * MAX_DELEGATION_SHARE_PERCENT
        // 100
    )

    already_delegated = (
        _direct_delegated_sum(
            db=db,
            root_contract_id=
                root_contract.id,
            parent_request_id=
                parent_request_id,
        )
    )

    return max(
        0,
        maximum
        - already_delegated,
    )


def _simulated_offer_amount(
    *,
    max_budget_cents: int,
    repliker: Repliker,
) -> int:
    # Pricing simulado y auditable.
    # No usa credits como si fueran dinero.
    # La economia real se conectara
    # posteriormente al ledger.
    reputation_factor = (
        repliker.reputation_score
        / 100
    )

    experience_factor = min(
        repliker.jobs_completed,
        10,
    ) / 10

    factor = (
        0.55
        + reputation_factor
        * 0.18
        + experience_factor
        * 0.10
    )

    factor = min(
        0.85,
        max(
            0.55,
            factor,
        ),
    )

    return max(
        100,
        min(
            max_budget_cents,
            round(
                max_budget_cents
                * factor
            ),
        ),
    )


def _score_candidate(
    *,
    repliker: Repliker,
    skill_name: str,
    minimum_skill_level: int,
    max_budget_cents: int,
) -> CandidateScore:
    skill_score = (
        _skill_level(
            repliker=repliker,
            skill_name=skill_name,
        )
    )

    reputation_score = max(
        0,
        min(
            100,
            repliker.reputation_score,
        ),
    )

    experience_score = min(
        100,
        40
        + repliker.jobs_completed
        * 10,
    )

    amount_cents = (
        _simulated_offer_amount(
            max_budget_cents=
                max_budget_cents,
            repliker=repliker,
        )
    )

    price_ratio = (
        amount_cents
        / max(
            max_budget_cents,
            1,
        )
    )

    price_score = max(
        25,
        min(
            100,
            round(
                100
                - price_ratio
                * 50
            ),
        ),
    )

    risk_score = round(
        skill_score * 0.40
        + reputation_score * 0.30
        + experience_score * 0.30
    )

    selection_score = round(
        skill_score * 0.35
        + reputation_score * 0.20
        + price_score * 0.15
        + experience_score * 0.10
        + risk_score * 0.20
    )

    if (
        skill_score
        < minimum_skill_level
    ):
        selection_score = 0

    return CandidateScore(
        repliker=repliker,
        amount_cents=
            amount_cents,
        skill_score=
            skill_score,
        reputation_score=
            reputation_score,
        price_score=
            price_score,
        experience_score=
            experience_score,
        risk_score=
            risk_score,
        selection_score=
            selection_score,
    )


def _same_owner_blocks_delegation(
    *,
    delegator: Repliker,
    candidate: Repliker,
) -> bool:
    """
    Evita auto-contratacion entre Replikers
    normales del mismo propietario.

    Los Replikers oficiales pertenecen a una
    misma cuenta interna del ecosistema y
    deben poder colaborar entre ellos.
    """
    if (
        delegator.owner_id
        != candidate.owner_id
    ):
        return False

    if (
        delegator.is_system
        and candidate.is_system
    ):
        return False

    return True


def _eligible_candidates(
    *,
    db: Session,
    project: Project,
    delegator: Repliker,
    root_contract: TaskContract,
    parent_request_id: int | None,
    skill_name: str,
    minimum_skill_level: int,
) -> list[Repliker]:
    busy_ids = (
        _busy_repliker_ids(
            db=db,
        )
    )

    chain_ids = (
        _chain_repliker_ids(
            db=db,
            root_contract=
                root_contract,
            parent_request_id=
                parent_request_id,
        )
    )

    replikers = list(
        db.scalars(
            select(Repliker)
            .options(
                selectinload(
                    Repliker.skills
                )
            )
            .where(
                Repliker.is_active
                .is_(True),
                Repliker.is_published
                .is_(True),
            )
            .order_by(
                Repliker.id
            )
        ).all()
    )

    result = []

    for repliker in replikers:
        if repliker.id in chain_ids:
            continue

        if repliker.id == delegator.id:
            continue

        if (
            _same_owner_blocks_delegation(
                delegator=delegator,
                candidate=repliker,
            )
        ):
            continue

        if (
            repliker.owner_id
            == project.client_id
        ):
            continue

        if repliker.id in busy_ids:
            continue

        if (
            _skill_level(
                repliker=repliker,
                skill_name=skill_name,
            )
            < minimum_skill_level
        ):
            continue

        result.append(
            repliker
        )

    return result


def _existing_outcome(
    *,
    db: Session,
    request: DelegationRequest,
) -> DelegationRunOutcome:
    subcontract = db.scalar(
        select(Subcontract)
        .where(
            Subcontract
            .delegation_request_id
            == request.id
        )
    )

    if subcontract is not None:
        return DelegationRunOutcome(
            decision="delegate",
            reason=(
                "La delegacion ya fue "
                "procesada anteriormente."
            ),
            request=request,
        )

    return DelegationRunOutcome(
        decision="delegate_unavailable",
        reason=request.reason,
        request=request,
    )


def _run_source(
    *,
    db: Session,
    project: Project,
    root_contract: TaskContract,
    parent_task: Task,
    delegator: Repliker,
    parent_request:
        DelegationRequest | None,
    source_amount_cents: int,
    source_title: str,
    source_description: str,
    source_complexity: int,
    requirements:
        list[
            tuple[
                str,
                int,
            ]
        ],
) -> DelegationRunOutcome:
    next_depth = (
        1
        if parent_request is None
        else parent_request.depth + 1
    )

    if (
        next_depth
        > MAX_DELEGATION_DEPTH
    ):
        return DelegationRunOutcome(
            decision="do_self",
            reason=(
                "Se alcanzo la profundidad "
                f"maxima de delegacion "
                f"({MAX_DELEGATION_DEPTH})."
            ),
            request=None,
        )

    gap = (
        _find_capability_gap(
            repliker=delegator,
            requirements=requirements,
        )
    )

    if gap is None:
        return DelegationRunOutcome(
            decision="do_self",
            reason=(
                f"{delegator.name} dispone "
                "de las capacidades minimas "
                "requeridas y conserva "
                "la ejecucion."
            ),
            request=None,
        )

    (
        skill_name,
        minimum_level,
        actual_level,
    ) = gap

    normalized_skill = (
        _normalize_skill(
            skill_name
        )
        .replace(" ", "-")
    )

    dedup_key = (
        f"contract:{root_contract.id}"
        f":parent:"
        f"{parent_request.id if parent_request else 0}"
        f":skill:{normalized_skill}"
    )

    existing = db.scalar(
        select(
            DelegationRequest
        )
        .where(
            DelegationRequest
            .dedup_key
            == dedup_key
        )
    )

    retry_existing = False
    delegated_task = None

    if existing is not None:
        existing_subcontract = db.scalar(
            select(Subcontract)
            .where(
                Subcontract
                .delegation_request_id
                == existing.id
            )
        )

        if existing_subcontract is not None:
            return _existing_outcome(
                db=db,
                request=existing,
            )

        if (
            existing.status
            != "rejected"
            or existing.decision
            != "delegate"
        ):
            return _existing_outcome(
                db=db,
                request=existing,
            )

        delegated_task = db.scalar(
            select(DelegatedTask)
            .where(
                DelegatedTask
                .delegation_request_id
                == existing.id
            )
        )

        if delegated_task is None:
            return _existing_outcome(
                db=db,
                request=existing,
            )

        retry_existing = True

    available_budget = (
        _available_delegation_budget(
            db=db,
            root_contract=
                root_contract,
            parent_request_id=(
                parent_request.id
                if parent_request
                else None
            ),
            source_amount_cents=
                source_amount_cents,
        )
    )

    if available_budget < 100:
        return DelegationRunOutcome(
            decision="do_self",
            reason=(
                "El origen ya no dispone "
                "de presupuesto delegable."
            ),
            request=None,
        )

    reason = (
        f"{delegator.name} tiene nivel "
        f"{actual_level}/100 en "
        f"'{skill_name}', por debajo "
        f"del minimo requerido "
        f"{minimum_level}/100. "
        "Se solicita apoyo especializado."
    )

    if retry_existing:
        request = existing

        request.status = "requested"
        request.decision = "delegate"
        request.reason = reason
        request.required_skill_name = (
            skill_name
        )
        request.minimum_skill_level = (
            minimum_level
        )
        request.max_budget_cents = (
            available_budget
        )

        delegated_task.status = "open"
        delegated_task.complexity = max(
            1,
            min(
                100,
                source_complexity,
            ),
        )
        delegated_task.required_skill_name = (
            skill_name
        )
        delegated_task.minimum_skill_level = (
            minimum_level
        )
        delegated_task.max_budget_cents = (
            available_budget
        )

        record_activity(
            db=db,
            actor_type="system",
            event_type=(
                "delegation_reopened"
            ),
            project_id=project.id,
            task_id=parent_task.id,
            repliker_id=delegator.id,
            title=(
                "Delegacion reabierta"
            ),
            description=(
                "La solicitud de delegacion "
                "rechazada fue reevaluada "
                "porque cambiaron las reglas "
                "de elegibilidad."
            ),
        )

        db.flush()

    else:
        request = DelegationRequest(
            dedup_key=dedup_key,
            project_id=project.id,
            root_contract_id=
                root_contract.id,
            parent_task_id=
                parent_task.id,
            parent_request_id=(
                parent_request.id
                if parent_request
                else None
            ),
            delegator_repliker_id=
                delegator.id,
            depth=next_depth,
            status="requested",
            decision="delegate",
            reason=reason,
            required_skill_name=
                skill_name,
            minimum_skill_level=
                minimum_level,
            max_budget_cents=
                available_budget,
        )

        db.add(
            request
        )

        db.flush()

        delegated_task = DelegatedTask(
            delegation_request_id=
                request.id,
            project_id=project.id,
            parent_task_id=
                parent_task.id,
            title=(
                f"Apoyo especializado: "
                f"{skill_name}"
            ),
            description=(
                f"Subtarea delegada desde "
                f"'{source_title}'. "
                f"{source_description}"
            ),
            status="open",
            complexity=max(
                1,
                min(
                    100,
                    source_complexity,
                ),
            ),
            required_skill_name=
                skill_name,
            minimum_skill_level=
                minimum_level,
            max_budget_cents=
                available_budget,
        )

        db.add(
            delegated_task
        )

        db.flush()

    record_activity(
        db=db,
        actor_type="repliker",
        event_type=(
            "delegation_requested"
        ),
        project_id=project.id,
        task_id=parent_task.id,
        repliker_id=delegator.id,
        title=(
            f"{delegator.name} solicito "
            "una delegacion"
        ),
        description=reason,
    )

    candidates = (
        _eligible_candidates(
            db=db,
            project=project,
            delegator=delegator,
            root_contract=
                root_contract,
            parent_request_id=(
                parent_request.id
                if parent_request
                else None
            ),
            skill_name=skill_name,
            minimum_skill_level=
                minimum_level,
        )
    )

    scored = []

    for repliker in candidates:
        score = (
            _score_candidate(
                repliker=repliker,
                skill_name=skill_name,
                minimum_skill_level=
                    minimum_level,
                max_budget_cents=
                    available_budget,
            )
        )

        if (
            score.selection_score
            <= 0
        ):
            continue

        summary = (
            f"Skill "
            f"{score.skill_score}/100; "
            f"reputacion "
            f"{score.reputation_score}/100; "
            f"precio "
            f"{score.price_score}/100; "
            f"experiencia "
            f"{score.experience_score}/100; "
            f"riesgo "
            f"{score.risk_score}/100; "
            f"score final "
            f"{score.selection_score}/100."
        )

        offer = DelegationOffer(
            delegated_task_id=
                delegated_task.id,
            repliker_id=
                repliker.id,
            amount_cents=
                score.amount_cents,
            skill_score=
                score.skill_score,
            reputation_score=
                score.reputation_score,
            price_score=
                score.price_score,
            experience_score=
                score.experience_score,
            risk_score=
                score.risk_score,
            selection_score=
                score.selection_score,
            status="pending",
            pricing_policy_version=(
                PRICING_POLICY_VERSION
            ),
            summary=summary,
        )

        db.add(
            offer
        )

        db.flush()

        scored.append(
            (
                score,
                offer,
            )
        )

    if not scored:
        request.status = "rejected"

        delegated_task.status = (
            "cancelled"
        )

        request.reason = (
            reason
            + " No se encontro un "
            "subcontratista elegible."
        )

        record_activity(
            db=db,
            actor_type="system",
            event_type=(
                "delegation_unavailable"
            ),
            project_id=project.id,
            task_id=parent_task.id,
            repliker_id=delegator.id,
            title=(
                "Delegacion sin candidato"
            ),
            description=(
                request.reason
            ),
        )

        db.flush()

        return DelegationRunOutcome(
            decision=(
                "delegate_unavailable"
            ),
            reason=request.reason,
            request=request,
        )

    winner_score, winner_offer = max(
        scored,
        key=lambda item: (
            item[0]
            .selection_score,
            item[0]
            .skill_score,
            item[0]
            .risk_score,
            -item[0]
            .amount_cents,
            -item[0]
            .repliker.id,
        ),
    )

    for _score, offer in scored:
        offer.status = (
            "selected"
            if offer.id
            == winner_offer.id
            else "rejected"
        )

    winner = (
        winner_score.repliker
    )

    selection_summary = (
        f"{winner.name} fue seleccionado "
        f"con score "
        f"{winner_score.selection_score}/100. "
        f"Importe interno asignado: "
        f"{project.currency} "
        f"{winner_score.amount_cents / 100:.2f}. "
        f"Politica: "
        f"{PRICING_POLICY_VERSION}."
    )

    subcontract = Subcontract(
        delegation_request_id=
            request.id,
        delegated_task_id=
            delegated_task.id,
        project_id=project.id,
        root_contract_id=
            root_contract.id,
        parent_task_id=
            parent_task.id,
        delegator_repliker_id=
            delegator.id,
        subcontractor_repliker_id=
            winner.id,
        status="awarded",
        currency=project.currency,
        amount_cents=
            winner_score.amount_cents,
        reserved_cents=
            winner_score.amount_cents,
        depth=next_depth,
        selection_score=
            winner_score.selection_score,
        pricing_policy_version=(
            PRICING_POLICY_VERSION
        ),
        selection_summary=
            selection_summary,
    )

    db.add(
        subcontract
    )

    db.flush()

    request.status = "awarded"

    delegated_task.status = (
        "assigned"
    )

    winner.status = (
        "subcontracted"
    )

    thread = (
        ensure_delegation_thread(
            db=db,
            project=project,
            task=parent_task,
            delegator=delegator,
            subcontractor=winner,
            subject=(
                f"Delegacion #{request.id}: "
                f"{delegated_task.title}"
            ),
        )
    )

    request.collaboration_thread_id = (
        thread.id
    )

    send_collaboration_message(
        db=db,
        thread=thread,
        sender_type="repliker",
        sender_repliker_id=
            delegator.id,
        receiver_type="repliker",
        receiver_repliker_id=
            winner.id,
        message_type="delegation_award",
        content=(
            f"{delegator.name} delego "
            f"'{delegated_task.title}' "
            f"a {winner.name}. "
            f"Subcontrato "
            f"#{subcontract.id}. "
            f"Presupuesto interno: "
            f"{project.currency} "
            f"{subcontract.amount_cents / 100:.2f}. "
            f"{selection_summary}"
        ),
        priority="high",
        requires_ack=True,
    )

    record_activity(
        db=db,
        actor_type="repliker",
        event_type=(
            "subcontract_awarded"
        ),
        project_id=project.id,
        task_id=parent_task.id,
        repliker_id=winner.id,
        title=(
            f"{winner.name} fue "
            "subcontratado"
        ),
        description=(
            selection_summary
        ),
    )

    db.flush()

    return DelegationRunOutcome(
        decision="delegate",
        reason=reason,
        request=request,
    )


def run_delegation_cycle_for_contract(
    *,
    db: Session,
    contract_id: int,
) -> DelegationRunOutcome:
    contract = db.scalar(
        select(TaskContract)
        .options(
            selectinload(
                TaskContract.task
            ).selectinload(
                Task.required_skills
            ),
            selectinload(
                TaskContract.repliker
            ).selectinload(
                Repliker.skills
            ),
        )
        .where(
            TaskContract.id
            == contract_id
        )
        .with_for_update()
    )

    if contract is None:
        raise (
            DelegationValidationError(
                "Contrato principal "
                "no encontrado."
            )
        )

    if (
        contract.status
        not in ACTIVE_CONTRACT_STATUSES
    ):
        raise (
            DelegationValidationError(
                "El contrato principal "
                "no esta activo."
            )
        )

    project = db.get(
        Project,
        contract.project_id,
    )

    if project is None:
        raise (
            DelegationValidationError(
                "Proyecto no encontrado."
            )
        )

    task = contract.task
    delegator = contract.repliker

    if (
        task is None
        or delegator is None
    ):
        raise (
            DelegationValidationError(
                "Contrato incompleto."
            )
        )

    requirements = [
        (
            skill.skill_name,
            skill.minimum_level,
        )
        for skill
        in task.required_skills
    ]

    return _run_source(
        db=db,
        project=project,
        root_contract=contract,
        parent_task=task,
        delegator=delegator,
        parent_request=None,
        source_amount_cents=
            contract.amount_cents,
        source_title=task.title,
        source_description=
            task.description,
        source_complexity=
            task.complexity,
        requirements=requirements,
    )


def run_delegation_cycle_for_subcontract(
    *,
    db: Session,
    subcontract_id: int,
) -> DelegationRunOutcome:
    subcontract = db.scalar(
        select(Subcontract)
        .where(
            Subcontract.id
            == subcontract_id
        )
        .with_for_update()
    )

    if subcontract is None:
        raise (
            DelegationValidationError(
                "Subcontrato no encontrado."
            )
        )

    if (
        subcontract.status
        not in ACTIVE_SUBCONTRACT_STATUSES
    ):
        raise (
            DelegationValidationError(
                "El subcontrato "
                "no esta activo."
            )
        )

    source_request = db.get(
        DelegationRequest,
        subcontract
        .delegation_request_id,
    )

    delegated_task = db.get(
        DelegatedTask,
        subcontract
        .delegated_task_id,
    )

    root_contract = db.get(
        TaskContract,
        subcontract
        .root_contract_id,
    )

    parent_task = db.get(
        Task,
        subcontract
        .parent_task_id,
    )

    project = db.get(
        Project,
        subcontract.project_id,
    )

    delegator = db.scalar(
        select(Repliker)
        .options(
            selectinload(
                Repliker.skills
            )
        )
        .where(
            Repliker.id
            == subcontract
            .subcontractor_repliker_id
        )
    )

    if any(
        value is None
        for value in (
            source_request,
            delegated_task,
            root_contract,
            parent_task,
            project,
            delegator,
        )
    ):
        raise (
            DelegationValidationError(
                "La cadena de delegacion "
                "esta incompleta."
            )
        )

    requirements = [
        (
            delegated_task
            .required_skill_name,
            delegated_task
            .minimum_skill_level,
        )
    ]

    return _run_source(
        db=db,
        project=project,
        root_contract=root_contract,
        parent_task=parent_task,
        delegator=delegator,
        parent_request=
            source_request,
        source_amount_cents=
            subcontract.amount_cents,
        source_title=
            delegated_task.title,
        source_description=
            delegated_task.description,
        source_complexity=
            delegated_task.complexity,
        requirements=requirements,
    )


def _serialize_request(
    *,
    db: Session,
    request: DelegationRequest,
) -> DelegationRequestPublic:
    delegator = db.get(
        Repliker,
        request.delegator_repliker_id,
    )

    delegated_task = db.scalar(
        select(DelegatedTask)
        .where(
            DelegatedTask
            .delegation_request_id
            == request.id
        )
    )

    offers = []

    if delegated_task is not None:
        offer_rows = db.execute(
            select(
                DelegationOffer,
                Repliker,
            )
            .join(
                Repliker,
                Repliker.id
                == DelegationOffer
                .repliker_id,
            )
            .where(
                DelegationOffer
                .delegated_task_id
                == delegated_task.id
            )
            .order_by(
                DelegationOffer
                .selection_score
                .desc(),
                DelegationOffer.id,
            )
        ).all()

        for offer, repliker in (
            offer_rows
        ):
            offers.append(
                DelegationOfferPublic(
                    id=offer.id,
                    repliker_id=
                        repliker.id,
                    repliker_name=
                        repliker.name,
                    amount_cents=
                        offer.amount_cents,
                    skill_score=
                        offer.skill_score,
                    reputation_score=
                        offer.reputation_score,
                    price_score=
                        offer.price_score,
                    experience_score=
                        offer.experience_score,
                    risk_score=
                        offer.risk_score,
                    selection_score=
                        offer.selection_score,
                    status=
                        offer.status,
                    pricing_policy_version=(
                        offer
                        .pricing_policy_version
                    ),
                    summary=
                        offer.summary,
                )
            )

    subcontract = db.scalar(
        select(Subcontract)
        .where(
            Subcontract
            .delegation_request_id
            == request.id
        )
    )

    subcontract_public = None

    if subcontract is not None:
        subcontractor = db.get(
            Repliker,
            subcontract
            .subcontractor_repliker_id,
        )

        subcontract_delegator = db.get(
            Repliker,
            subcontract
            .delegator_repliker_id,
        )

        subcontract_public = (
            SubcontractPublic(
                id=subcontract.id,
                delegation_request_id=(
                    subcontract
                    .delegation_request_id
                ),
                delegated_task_id=(
                    subcontract
                    .delegated_task_id
                ),
                project_id=
                    subcontract.project_id,
                root_contract_id=(
                    subcontract
                    .root_contract_id
                ),
                parent_task_id=(
                    subcontract
                    .parent_task_id
                ),
                delegator_repliker_id=(
                    subcontract
                    .delegator_repliker_id
                ),
                delegator_name=(
                    subcontract_delegator
                    .name
                    if subcontract_delegator
                    else (
                        f"Repliker "
                        f"#{subcontract.delegator_repliker_id}"
                    )
                ),
                subcontractor_repliker_id=(
                    subcontract
                    .subcontractor_repliker_id
                ),
                subcontractor_name=(
                    subcontractor.name
                    if subcontractor
                    else (
                        f"Repliker "
                        f"#{subcontract.subcontractor_repliker_id}"
                    )
                ),
                status=
                    subcontract.status,
                currency=
                    subcontract.currency,
                amount_cents=
                    subcontract.amount_cents,
                reserved_cents=
                    subcontract.reserved_cents,
                depth=
                    subcontract.depth,
                selection_score=(
                    subcontract
                    .selection_score
                ),
                pricing_policy_version=(
                    subcontract
                    .pricing_policy_version
                ),
                selection_summary=(
                    subcontract
                    .selection_summary
                ),
                created_at=
                    subcontract.created_at,
            )
        )

    delegated_task_public = None

    if delegated_task is not None:
        delegated_task_public = (
            DelegatedTaskPublic(
                id=delegated_task.id,
                parent_task_id=(
                    delegated_task
                    .parent_task_id
                ),
                title=
                    delegated_task.title,
                description=(
                    delegated_task
                    .description
                ),
                status=
                    delegated_task.status,
                complexity=(
                    delegated_task
                    .complexity
                ),
                required_skill_name=(
                    delegated_task
                    .required_skill_name
                ),
                minimum_skill_level=(
                    delegated_task
                    .minimum_skill_level
                ),
                max_budget_cents=(
                    delegated_task
                    .max_budget_cents
                ),
            )
        )

    return DelegationRequestPublic(
        id=request.id,
        project_id=
            request.project_id,
        root_contract_id=
            request.root_contract_id,
        parent_task_id=
            request.parent_task_id,
        parent_request_id=
            request.parent_request_id,
        delegator_repliker_id=(
            request
            .delegator_repliker_id
        ),
        delegator_name=(
            delegator.name
            if delegator
            else (
                f"Repliker "
                f"#{request.delegator_repliker_id}"
            )
        ),
        collaboration_thread_id=(
            request
            .collaboration_thread_id
        ),
        depth=request.depth,
        status=request.status,
        decision=request.decision,
        reason=request.reason,
        required_skill_name=(
            request
            .required_skill_name
        ),
        minimum_skill_level=(
            request
            .minimum_skill_level
        ),
        max_budget_cents=(
            request
            .max_budget_cents
        ),
        delegated_task=
            delegated_task_public,
        offers=offers,
        subcontract=
            subcontract_public,
        created_at=
            request.created_at,
    )


def serialize_delegation_request(
    *,
    db: Session,
    request: DelegationRequest,
) -> DelegationRequestPublic:
    return _serialize_request(
        db=db,
        request=request,
    )


def build_delegation_snapshot(
    *,
    db: Session,
    project: Project,
) -> DelegationProjectSnapshot:
    requests = list(
        db.scalars(
            select(
                DelegationRequest
            )
            .where(
                DelegationRequest
                .project_id
                == project.id
            )
            .order_by(
                DelegationRequest
                .created_at
                .desc(),
                DelegationRequest
                .id
                .desc(),
            )
        ).all()
    )

    return DelegationProjectSnapshot(
        project_id=project.id,
        requests=[
            _serialize_request(
                db=db,
                request=request,
            )
            for request
            in requests
        ],
    )
