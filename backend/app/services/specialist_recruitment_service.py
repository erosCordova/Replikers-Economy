from __future__ import annotations

from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)
from typing import Callable

from sqlalchemy import select
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
    Subcontract,
)
from app.models.project import Project
from app.models.project_specialist import (
    ProjectSpecialistOffer,
    ProjectSpecialistRequirement,
)
from app.models.repliker import Repliker
from app.orchestration.specialist_market import (
    evaluate_repliker_for_specialist_role,
)
from app.schemas.market import (
    SpecialistOfferDecisionAI,
)
from app.services.activity_service import (
    record_activity,
)
from app.services.gemini_client import (
    GeminiResponseError,
)
from app.services.message_service import (
    record_message,
)
from app.services.specialist_coverage_service import (
    TERMINAL_PROJECT_STATUSES,
    normalize_specialty,
    sync_project_specialist_coverage,
)
from app.services.specialty_localization_service import (
    specialty_label_es,
)


SpecialistEvaluator = Callable[
    ...,
    SpecialistOfferDecisionAI,
]


@dataclass(
    frozen=True,
    slots=True,
)
class SpecialistRecruitmentResult:
    requirements_processed: int
    candidates_considered: int

    offers_sent: int
    accepted: int
    rejected: int

    errors: tuple[
        str,
        ...
    ]


def _busy_repliker_ids(
    *,
    db: Session,
) -> set[int]:
    principal = set(
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

    delegated = set(
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

    return principal | delegated


def _reserved_repliker_ids(
    *,
    db: Session,
    project_id: int,
) -> set[int]:
    rows = db.scalars(
        select(
            ProjectSpecialistOffer
            .repliker_id
        )
        .join(
            Project,
            Project.id
            ==
            ProjectSpecialistOffer
            .project_id,
        )
        .where(
            ProjectSpecialistOffer.project_id
            != project_id,
            ProjectSpecialistOffer.status
            == "accepted",
            ~Project.status.in_(
                TERMINAL_PROJECT_STATUSES
            ),
        )
    ).all()

    return {
        int(item)
        for item in rows
        if item is not None
    }


def _candidate_replikers(
    *,
    db: Session,
    project: Project,
    requirement:
        ProjectSpecialistRequirement,
) -> list[Repliker]:
    busy_ids = _busy_repliker_ids(
        db=db
    )

    reserved_ids = (
        _reserved_repliker_ids(
            db=db,
            project_id=project.id,
        )
    )

    rejected_ids = set(
        db.scalars(
            select(
                ProjectSpecialistOffer
                .repliker_id
            )
            .where(
                ProjectSpecialistOffer
                .requirement_id
                == requirement.id,
                ProjectSpecialistOffer.status
                == "rejected",
            )
        ).all()
    )

    required = normalize_specialty(
        requirement.specialty
    )

    candidates = list(
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
                Repliker.owner_id
                != project.client_id,
                Repliker.status
                == "available",
            )
            .order_by(
                Repliker
                .reputation_score
                .desc(),
                Repliker
                .jobs_completed
                .desc(),
                Repliker.id,
            )
        ).all()
    )

    return [
        repliker
        for repliker
        in candidates
        if (
            repliker.id
            not in busy_ids
            and repliker.id
            not in reserved_ids
            and repliker.id
            not in rejected_ids
            and normalize_specialty(
                repliker.specialty
            )
            == required
        )
    ]


def _offer_for_candidate(
    *,
    db: Session,
    requirement_id: int,
    repliker_id: int,
) -> ProjectSpecialistOffer | None:
    return db.scalar(
        select(
            ProjectSpecialistOffer
        )
        .where(
            ProjectSpecialistOffer
            .requirement_id
            == requirement_id,
            ProjectSpecialistOffer
            .repliker_id
            == repliker_id,
        )
    )


def _expire_invalid_acceptances(
    *,
    db: Session,
    requirement:
        ProjectSpecialistRequirement,
):
    rows = list(
        db.scalars(
            select(
                ProjectSpecialistOffer
            )
            .where(
                ProjectSpecialistOffer
                .requirement_id
                == requirement.id,
                ProjectSpecialistOffer.status
                == "accepted",
            )
        ).all()
    )

    if (
        requirement.coverage_status
        == "covered"
        and requirement
        .assigned_repliker_id
        is not None
    ):
        return

    for offer in rows:
        offer.status = "expired"


def run_project_specialist_recruitment(
    *,
    db: Session,
    project_id: int,
    iris_id: int | None = None,
    evaluator:
        SpecialistEvaluator | None = None,
) -> SpecialistRecruitmentResult:
    """
    Recluta puestos de proyecto que requieren una
    aceptación explícita.

    En Fase 13A2.2.3 esto se utiliza para el
    Revisor Final, que no posee una TaskContract.
    """

    if evaluator is None:
        evaluator = (
            evaluate_repliker_for_specialist_role
        )

    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise ValueError(
            "Proyecto no encontrado."
        )

    if (
        project.status
        in TERMINAL_PROJECT_STATUSES
    ):
        return SpecialistRecruitmentResult(
            requirements_processed=0,
            candidates_considered=0,
            offers_sent=0,
            accepted=0,
            rejected=0,
            errors=(),
        )

    sync_project_specialist_coverage(
        db=db,
        project_id=project.id,
    )

    requirements = list(
        db.scalars(
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
                ProjectSpecialistRequirement
                .id
            )
        ).all()
    )

    requirements_processed = 0
    candidates_considered = 0

    offers_sent = 0
    accepted = 0
    rejected = 0

    errors: list[str] = []

    project_data = {
        "id":
            project.id,
        "titulo":
            project.title,
        "descripcion":
            project.description,
        "estado":
            project.status,
    }

    for requirement in requirements:
        requirements_processed += 1

        if (
            requirement.coverage_status
            == "covered"
            and requirement
            .assigned_repliker_id
            is not None
        ):
            continue

        _expire_invalid_acceptances(
            db=db,
            requirement=requirement,
        )

        candidates = _candidate_replikers(
            db=db,
            project=project,
            requirement=requirement,
        )

        visible_specialty = (
            specialty_label_es(
                requirement.specialty
            )
        )

        for repliker in candidates:
            existing = (
                _offer_for_candidate(
                    db=db,
                    requirement_id=
                        requirement.id,
                    repliker_id=
                        repliker.id,
                )
            )

            if (
                existing is not None
                and existing.status
                == "accepted"
            ):
                continue

            if (
                existing is not None
                and existing.status
                == "rejected"
            ):
                continue

            if existing is None:
                offer = (
                    ProjectSpecialistOffer(
                        project_id=
                            project.id,
                        requirement_id=
                            requirement.id,
                        repliker_id=
                            repliker.id,
                        status="pending",
                    )
                )

                db.add(
                    offer
                )

                db.flush()

            else:
                offer = existing
                offer.status = "pending"
                offer.responded_at = None

            repliker_data = {
                "id":
                    repliker.id,
                "nombre":
                    repliker.name,
                "especialidad":
                    specialty_label_es(
                        repliker.specialty
                    ),
                "descripcion":
                    repliker.description,
                "reputacion":
                    repliker
                    .reputation_score,
                "trabajos_completados":
                    repliker
                    .jobs_completed,
                "habilidades": [
                    {
                        "nombre":
                            skill.name,
                        "nivel":
                            skill.level,
                    }
                    for skill
                    in repliker.skills
                ],
            }

            requirement_data = {
                "id":
                    requirement.id,
                "especialidad":
                    visible_specialty,
                "motivo":
                    requirement.reason,
                "obligatorio":
                    requirement
                    .is_mandatory,
                "revision_final":
                    requirement
                    .is_final_gate,
            }

            record_activity(
                db=db,
                actor_type=(
                    "repliker"
                    if iris_id is not None
                    else "system"
                ),
                event_type=(
                    "specialist_offer_sent"
                ),
                project_id=
                    project.id,
                repliker_id=(
                    iris_id
                    if iris_id is not None
                    else None
                ),
                title=(
                    "Iris envió una propuesta "
                    f"a {repliker.name}"
                    if iris_id is not None
                    else (
                        "Se envió una propuesta "
                        f"a {repliker.name}"
                    )
                ),
                description=(
                    f"Se propone el puesto de "
                    f"{visible_specialty}. "
                    "El Repliker puede aceptar "
                    "o rechazar libremente."
                ),
            )

            record_message(
                db=db,
                project_id=
                    project.id,
                sender_type=(
                    "repliker"
                    if iris_id is not None
                    else "market"
                ),
                sender_repliker_id=
                    iris_id,
                receiver_type=
                    "repliker",
                receiver_repliker_id=
                    repliker.id,
                message_type=(
                    "specialist_offer"
                ),
                content=(
                    f"Hay una propuesta para "
                    f"que participes como "
                    f"{visible_specialty}. "
                    "Revísala y decide con "
                    "libertad si deseas aceptar."
                ),
            )

            offer_id = offer.id
            repliker_id = repliker.id
            repliker_name = repliker.name

            # Muy importante: no mantener una
            # transacción abierta durante IA.
            db.commit()

            candidates_considered += 1
            offers_sent += 1

            try:
                decision = evaluator(
                    repliker_data=
                        repliker_data,
                    requirement_data=
                        requirement_data,
                    project_data=
                        project_data,
                )

            except GeminiResponseError as exc:
                failed_offer = db.get(
                    ProjectSpecialistOffer,
                    offer_id,
                )

                if failed_offer is not None:
                    failed_offer.status = (
                        "error"
                    )

                    failed_offer.reasoning = (
                        str(exc)
                    )

                record_activity(
                    db=db,
                    actor_type=
                        "repliker",
                    event_type=(
                        "specialist_evaluation_failed"
                    ),
                    project_id=
                        project.id,
                    repliker_id=
                        repliker_id,
                    title=(
                        f"{repliker_name} "
                        "no pudo evaluar "
                        "la propuesta"
                    ),
                    description=(
                        "Ocurrió un error temporal. "
                        "Iris continuará con otro "
                        "Repliker compatible."
                    ),
                )

                db.commit()

                errors.append(
                    f"Repliker {repliker_id}: "
                    "error temporal al evaluar "
                    "la propuesta."
                )

                continue

            offer = db.get(
                ProjectSpecialistOffer,
                offer_id,
            )

            if offer is None:
                raise RuntimeError(
                    "La propuesta desapareció "
                    "durante la evaluación."
                )

            offer.confidence_score = (
                decision.confidence_score
            )

            offer.message = (
                decision.message
                or (
                    "Acepto la propuesta."
                    if decision.decision
                    == "accept"
                    else (
                        "Prefiero no aceptar "
                        "esta propuesta."
                    )
                )
            )

            offer.reasoning = (
                decision.reasoning
            )

            offer.responded_at = (
                datetime.now(
                    timezone.utc
                )
            )

            if (
                decision.decision
                == "accept"
            ):
                offer.status = "accepted"
                accepted += 1

                record_activity(
                    db=db,
                    actor_type="repliker",
                    event_type=(
                        "specialist_offer_accepted"
                    ),
                    project_id=
                        project.id,
                    repliker_id=
                        repliker_id,
                    title=(
                        f"{repliker_name} "
                        "aceptó la propuesta"
                    ),
                    description=(
                        f"El Repliker aceptó "
                        f"participar como "
                        f"{visible_specialty}."
                    ),
                )

                record_message(
                    db=db,
                    project_id=
                        project.id,
                    sender_type=
                        "repliker",
                    sender_repliker_id=
                        repliker_id,
                    receiver_type=
                        "repliker"
                        if iris_id is not None
                        else "project",
                    receiver_repliker_id=
                        iris_id,
                    message_type=(
                        "specialist_offer_accepted"
                    ),
                    content=offer.message,
                )

                sync_project_specialist_coverage(
                    db=db,
                    project_id=
                        project.id,
                )

                db.commit()

                break

            offer.status = "rejected"
            rejected += 1

            record_activity(
                db=db,
                actor_type="repliker",
                event_type=(
                    "specialist_offer_rejected"
                ),
                project_id=
                    project.id,
                repliker_id=
                    repliker_id,
                title=(
                    f"{repliker_name} "
                    "rechazó la propuesta"
                ),
                description=(
                    "Iris continuará buscando "
                    "otro Repliker compatible."
                ),
            )

            record_message(
                db=db,
                project_id=
                    project.id,
                sender_type=
                    "repliker",
                sender_repliker_id=
                    repliker_id,
                receiver_type=
                    "repliker"
                    if iris_id is not None
                    else "project",
                receiver_repliker_id=
                    iris_id,
                message_type=(
                    "specialist_offer_rejected"
                ),
                content=offer.message,
            )

            db.commit()

    sync_project_specialist_coverage(
        db=db,
        project_id=project.id,
    )

    db.commit()

    return SpecialistRecruitmentResult(
        requirements_processed=
            requirements_processed,
        candidates_considered=
            candidates_considered,
        offers_sent=
            offers_sent,
        accepted=
            accepted,
        rejected=
            rejected,
        errors=tuple(
            errors
        ),
    )
