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
from app.models.task import Task


TERMINAL_PROJECT_STATUSES = {
    "completed",
    "delivered",
    "cancelled",
    "failed",
}


@dataclass(
    frozen=True,
    slots=True,
)
class SpecialistCoverageSnapshot:
    project_id: int

    mandatory_total: int
    mandatory_covered: int

    ready: bool

    missing_specialties: tuple[
        str,
        ...
    ]


def normalize_specialty(
    value: str | None,
) -> str:
    return " ".join(
        str(
            value or ""
        )
        .strip()
        .casefold()
        .split()
    )


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


def _reserved_offer_repliker_ids(
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


def _contract_specialists(
    *,
    db: Session,
    project_id: int,
) -> dict[str, Repliker]:
    rows = db.execute(
        select(
            TaskContract,
            Repliker,
        )
        .join(
            Repliker,
            Repliker.id
            == TaskContract.repliker_id,
        )
        .where(
            TaskContract.project_id
            == project_id,
            TaskContract.status.in_(
                ACTIVE_CONTRACT_STATUSES
            ),
            Repliker.is_active
            .is_(True),
        )
        .order_by(
            TaskContract.id
        )
    ).all()

    result: dict[
        str,
        Repliker,
    ] = {}

    for _contract, repliker in rows:
        specialty = normalize_specialty(
            repliker.specialty
        )

        if (
            specialty
            and specialty not in result
        ):
            result[specialty] = (
                repliker
            )

    return result


def _accepted_offer(
    *,
    db: Session,
    requirement_id: int,
) -> ProjectSpecialistOffer | None:
    return db.scalar(
        select(
            ProjectSpecialistOffer
        )
        .where(
            ProjectSpecialistOffer
            .requirement_id
            == requirement_id,
            ProjectSpecialistOffer.status
            == "accepted",
        )
        .order_by(
            ProjectSpecialistOffer.id
        )
        .limit(1)
    )


def _valid_offer_assignment(
    *,
    project: Project,
    requirement:
        ProjectSpecialistRequirement,
    repliker: Repliker | None,
    busy_ids: set[int],
    reserved_ids: set[int],
) -> bool:
    if repliker is None:
        return False

    if not repliker.is_active:
        return False

    if (
        repliker.owner_id
        == project.client_id
    ):
        return False

    if repliker.id in busy_ids:
        return False

    if repliker.id in reserved_ids:
        return False

    if (
        normalize_specialty(
            repliker.status
        )
        != "available"
    ):
        return False

    return (
        normalize_specialty(
            repliker.specialty
        )
        ==
        normalize_specialty(
            requirement.specialty
        )
    )


def _snapshot(
    *,
    project_id: int,
    requirements: list[
        ProjectSpecialistRequirement
    ],
) -> SpecialistCoverageSnapshot:
    mandatory = [
        requirement
        for requirement in requirements
        if requirement.is_mandatory
    ]

    covered = [
        requirement
        for requirement in mandatory
        if (
            requirement.coverage_status
            == "covered"
            and requirement
            .assigned_repliker_id
            is not None
        )
    ]

    missing = tuple(
        requirement.specialty
        for requirement in mandatory
        if requirement not in covered
    )

    return SpecialistCoverageSnapshot(
        project_id=project_id,
        mandatory_total=
            len(mandatory),
        mandatory_covered=
            len(covered),
        ready=(
            len(missing) == 0
        ),
        missing_specialties=
            missing,
    )


def sync_project_specialist_coverage(
    *,
    db: Session,
    project_id: int,
) -> SpecialistCoverageSnapshot:
    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise ValueError(
            "Proyecto no encontrado."
        )

    requirements = list(
        db.scalars(
            select(
                ProjectSpecialistRequirement
            )
            .where(
                ProjectSpecialistRequirement
                .project_id
                == project.id
            )
            .order_by(
                ProjectSpecialistRequirement
                .id
            )
        ).all()
    )

    if not requirements:
        # Compatibilidad con proyectos creados
        # antes de Fase 13A2.2.2.
        return SpecialistCoverageSnapshot(
            project_id=project.id,
            mandatory_total=0,
            mandatory_covered=0,
            ready=True,
            missing_specialties=(),
        )

    contract_specialists = (
        _contract_specialists(
            db=db,
            project_id=project.id,
        )
    )

    busy_ids = _busy_repliker_ids(
        db=db
    )

    reserved_ids = (
        _reserved_offer_repliker_ids(
            db=db,
            project_id=project.id,
        )
    )

    for requirement in requirements:
        specialty = normalize_specialty(
            requirement.specialty
        )

        # Los puestos normales pueden quedar
        # cubiertos por un contrato de tarea.
        # El Revisor Final no: necesita una
        # aceptación explícita del puesto.
        if not requirement.is_final_gate:
            contracted = (
                contract_specialists.get(
                    specialty
                )
            )

            if contracted is not None:
                requirement\
                    .assigned_repliker_id = (
                        contracted.id
                    )

                requirement\
                    .coverage_status = (
                        "covered"
                    )

                continue

        offer = _accepted_offer(
            db=db,
            requirement_id=requirement.id,
        )

        offered_repliker = None

        if offer is not None:
            offered_repliker = db.get(
                Repliker,
                offer.repliker_id,
            )

        if (
            offer is not None
            and _valid_offer_assignment(
                project=project,
                requirement=requirement,
                repliker=offered_repliker,
                busy_ids=busy_ids,
                reserved_ids=reserved_ids,
            )
        ):
            requirement\
                .assigned_repliker_id = (
                    offered_repliker.id
                )

            requirement\
                .coverage_status = (
                    "covered"
                )

            reserved_ids.add(
                offered_repliker.id
            )

        else:
            requirement\
                .assigned_repliker_id = (
                    None
                )

            requirement\
                .coverage_status = (
                    "pending"
                )

    db.flush()

    return _snapshot(
        project_id=project.id,
        requirements=requirements,
    )


def get_project_specialist_coverage(
    *,
    db: Session,
    project_id: int,
) -> SpecialistCoverageSnapshot:
    requirements = list(
        db.scalars(
            select(
                ProjectSpecialistRequirement
            )
            .where(
                ProjectSpecialistRequirement
                .project_id
                == project_id
            )
            .order_by(
                ProjectSpecialistRequirement
                .id
            )
        ).all()
    )

    return _snapshot(
        project_id=project_id,
        requirements=requirements,
    )


def enforce_project_specialist_gate(
    *,
    db: Session,
    project_id: int,
) -> SpecialistCoverageSnapshot:
    """
    Sincroniza la cobertura y mantiene el estado
    contractual del proyecto coherente.

    Un proyecto nuevo solo puede quedar
    'contracted' si:
    - todas sus tareas tienen contrato activo;
    - todas las especialidades obligatorias
      están cubiertas.
    """

    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise ValueError(
            "Proyecto no encontrado."
        )

    snapshot = (
        sync_project_specialist_coverage(
            db=db,
            project_id=project.id,
        )
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

    contracted_tasks = int(
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
        project.status
        not in TERMINAL_PROJECT_STATUSES
    ):
        if (
            total_tasks > 0
            and contracted_tasks
            >= total_tasks
            and snapshot.ready
        ):
            project.status = (
                "contracted"
            )

        elif (
            contracted_tasks > 0
            or not snapshot.ready
        ):
            project.status = (
                "partially_contracted"
            )

    db.flush()

    return snapshot
