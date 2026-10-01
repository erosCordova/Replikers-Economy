from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    Session,
    selectinload,
)

from app.auth.dependencies import (
    get_current_user,
    get_db,
)
from app.models.contract import (
    ACTIVE_CONTRACT_STATUSES,
    TaskContract,
)
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.schemas.contract import (
    ContractProjectSnapshot,
    ContractPublic,
    SelectionRunResponse,
    SelectionTaskResult,
)
from app.services.contract_service import (
    ContractSelectionError,
    select_contracts_for_project,
)


router = APIRouter(
    prefix="/contracts",
    tags=[
        "Contratacion autonoma",
    ],
)


def _check_project_access(
    project: Project,
    current_user: User,
):
    if (
        project.client_id
        != current_user.id
        and current_user.role
        != "admin"
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "No tienes acceso "
                "a este proyecto."
            ),
        )


def _contract_public(
    contract: TaskContract,
) -> ContractPublic:
    return ContractPublic(
        id=contract.id,
        project_id=
            contract.project_id,
        task_id=
            contract.task_id,
        task_title=
            contract.task.title,
        bid_id=
            contract.bid_id,
        repliker_id=
            contract.repliker_id,
        repliker_name=
            contract.repliker.name,
        status=
            contract.status,
        currency=
            contract.currency,
        amount_cents=
            contract.amount_cents,
        reserved_cents=
            contract.reserved_cents,
        skill_score=
            contract.skill_score,
        reputation_score=
            contract.reputation_score,
        confidence_score=
            contract.confidence_score,
        price_score=
            contract.price_score,
        time_score=
            contract.time_score,
        risk_score=
            contract.risk_score,
        selection_score=
            contract.selection_score,
        selected_by=
            contract.selected_by,
        selection_policy_version=(
            contract
            .selection_policy_version
        ),
        selection_summary=(
            contract
            .selection_summary
        ),
        created_at=
            contract.created_at,
    )


def _project_contracts(
    *,
    db: Session,
    project_id: int,
) -> list[TaskContract]:
    return list(
        db.scalars(
            select(TaskContract)
            .options(
                selectinload(
                    TaskContract.task
                ),
                selectinload(
                    TaskContract.repliker
                ),
            )
            .where(
                TaskContract.project_id
                == project_id
            )
            .order_by(
                TaskContract.id
            )
        ).all()
    )


@router.post(
    "/projects/{project_id}/select",
    response_model=
        SelectionRunResponse,
)
def select_project_contracts(
    project_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Proyecto no encontrado."
            ),
        )

    _check_project_access(
        project,
        current_user,
    )

    try:
        outcome = (
            select_contracts_for_project(
                db=db,
                project_id=project_id,
            )
        )

        db.commit()

    except ContractSelectionError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=(
                "La contratacion entro "
                "en conflicto con otra "
                "operacion concurrente."
            ),
        ) from exc

    except Exception:
        db.rollback()
        raise

    contracts = {
        contract.id:
            contract
        for contract
        in _project_contracts(
            db=db,
            project_id=project_id,
        )
    }

    task_results = []

    for result in (
        outcome.task_results
    ):
        contract_public = None

        if result.contract:
            persisted = contracts.get(
                result.contract.id
            )

            if persisted:
                contract_public = (
                    _contract_public(
                        persisted
                    )
                )

        task_results.append(
            SelectionTaskResult(
                task_id=result.task.id,
                task_title=
                    result.task.title,
                selected=(
                    contract_public
                    is not None
                ),
                contract=
                    contract_public,
                reason=result.reason,
            )
        )

    return SelectionRunResponse(
        project_id=
            outcome.project.id,
        project_status=
            outcome.project.status,
        contracts_created=
            len(
                outcome
                .contracts_created
            ),
        reserved_budget_cents=(
            outcome
            .reserved_budget_cents
        ),
        remaining_budget_cents=(
            outcome
            .remaining_budget_cents
        ),
        tasks=task_results,
    )


@router.get(
    "/projects/{project_id}",
    response_model=
        ContractProjectSnapshot,
)
def get_project_contracts(
    project_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Proyecto no encontrado."
            ),
        )

    _check_project_access(
        project,
        current_user,
    )

    contracts = (
        _project_contracts(
            db=db,
            project_id=project_id,
        )
    )

    reserved = (
        db.scalar(
            select(
                func.coalesce(
                    func.sum(
                        TaskContract
                        .reserved_cents
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
        or 0
    )

    budget = (
        project.budget_limit_cents
        or 0
    )

    return ContractProjectSnapshot(
        project_id=project.id,
        project_status=
            project.status,
        reserved_budget_cents=
            int(reserved),
        remaining_budget_cents=
            max(
                0,
                budget
                - int(reserved),
            ),
        contracts=[
            _contract_public(
                contract
            )
            for contract
            in contracts
        ],
    )


@router.get(
    "/tasks/{task_id}",
    response_model=
        ContractPublic,
)
def get_task_contract(
    task_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    task = db.get(
        Task,
        task_id,
    )

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Tarea no encontrada.",
        )

    project = db.get(
        Project,
        task.project_id,
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Proyecto no encontrado."
            ),
        )

    _check_project_access(
        project,
        current_user,
    )

    contract = db.scalar(
        select(TaskContract)
        .options(
            selectinload(
                TaskContract.task
            ),
            selectinload(
                TaskContract.repliker
            ),
        )
        .where(
            TaskContract.task_id
            == task_id
        )
        .order_by(
            TaskContract.id.desc()
        )
    )

    if contract is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "La tarea aun no tiene "
                "un contrato."
            ),
        )

    return _contract_public(
        contract
    )
