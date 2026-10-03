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


def _reserved_final_gate_ids(
    *,
    db: Session,
    project_id: int,
) -> set[int]:
    rows = db.scalars(
        select(
            ProjectSpecialistRequirement
            .assigned_repliker_id
        )
        .join(
            Project,
            Project.id
            ==
            ProjectSpecialistRequirement
            .project_id,
        )
        .where(
            ProjectSpecialistRequirement
            .project_id
            != project_id,
            ProjectSpecialistRequirement
            .is_final_gate
            .is_(True),
            ProjectSpecialistRequirement
            .coverage_status
            == "covered",
            ProjectSpecialistRequirement
            .assigned_repliker_id
            .is_not(None),
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


def _is_valid_final_gate_assignment(
    *,
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
        normalize_specialty(
            repliker.status
        )
        != "available"
    ):
        return False

    if repliker.id in busy_ids:
        return False

    if repliker.id in reserved_ids:
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


def _find_final_gate_candidate(
    *,
    db: Session,
    project: Project,
    requirement:
        ProjectSpecialistRequirement,
    busy_ids: set[int],
    reserved_ids: set[int],
) -> Repliker | None:
    candidates = list(
        db.scalars(
            select(Repliker)
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

    required = normalize_specialty(
        requirement.specialty
    )

    for repliker in candidates:
        if repliker.id in busy_ids:
            continue

        if repliker.id in reserved_ids:
            continue

        if (
            normalize_specialty(
                repliker.specialty
            )
            != required
        ):
            continue

        return repliker

    return None


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
        _reserved_final_gate_ids(
            db=db,
            project_id=project.id,
        )
    )

    for requirement in requirements:
        specialty = normalize_specialty(
            requirement.specialty
        )

        if requirement.is_final_gate:
            assigned = None

            if (
                requirement
                .assigned_repliker_id
                is not None
            ):
                assigned = db.get(
                    Repliker,
                    requirement
                    .assigned_repliker_id,
                )

            if not (
                _is_valid_final_gate_assignment(
                    requirement=requirement,
                    repliker=assigned,
                    busy_ids=busy_ids,
                    reserved_ids=
                        reserved_ids,
                )
            ):
                assigned = (
                    _find_final_gate_candidate(
                        db=db,
                        project=project,
                        requirement=
                            requirement,
                        busy_ids=busy_ids,
                        reserved_ids=
                            reserved_ids,
                    )
                )

            if assigned is None:
                requirement\
                    .assigned_repliker_id = (
                        None
                    )

                requirement\
                    .coverage_status = (
                        "pending"
                    )
            else:
                requirement\
                    .assigned_repliker_id = (
                        assigned.id
                    )

                requirement\
                    .coverage_status = (
                        "covered"
                    )

                reserved_ids.add(
                    assigned.id
                )

            continue

        repliker = (
            contract_specialists.get(
                specialty
            )
        )

        if repliker is None:
            requirement\
                .assigned_repliker_id = (
                    None
                )

            requirement\
                .coverage_status = (
                    "pending"
                )
        else:
            requirement\
                .assigned_repliker_id = (
                    repliker.id
                )

            requirement\
                .coverage_status = (
                    "covered"
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
