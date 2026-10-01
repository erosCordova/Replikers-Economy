from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.exc import (
    IntegrityError,
)
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
    get_db,
)
from app.models.contract import (
    TaskContract,
)
from app.models.delegation import (
    Subcontract,
)
from app.models.project import Project
from app.models.user import User
from app.schemas.delegation import (
    DelegationProjectSnapshot,
    DelegationRunResponse,
)
from app.services.delegation_service import (
    DelegationValidationError,
    build_delegation_snapshot,
    run_delegation_cycle_for_contract,
    run_delegation_cycle_for_subcontract,
    serialize_delegation_request,
)


router = APIRouter(
    prefix="/delegations",
    tags=[
        "Delegacion autonoma",
    ],
)


def _check_project_access(
    *,
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


def _project_or_404(
    *,
    db: Session,
    project_id: int,
) -> Project:
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

    return project


@router.post(
    "/contracts/{contract_id}/run",
    response_model=
        DelegationRunResponse,
)
def run_contract_delegation(
    contract_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    contract = db.get(
        TaskContract,
        contract_id,
    )

    if contract is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Contrato no encontrado."
            ),
        )

    project = _project_or_404(
        db=db,
        project_id=
            contract.project_id,
    )

    _check_project_access(
        project=project,
        current_user=current_user,
    )

    try:
        outcome = (
            run_delegation_cycle_for_contract(
                db=db,
                contract_id=
                    contract.id,
            )
        )

        db.commit()

        return DelegationRunResponse(
            decision=
                outcome.decision,
            reason=
                outcome.reason,
            request=(
                serialize_delegation_request(
                    db=db,
                    request=
                        outcome.request,
                )
                if outcome.request
                else None
            ),
        )

    except DelegationValidationError as exc:
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
                "La delegacion entro "
                "en conflicto con otra "
                "operacion concurrente."
            ),
        ) from exc

    except Exception:
        db.rollback()
        raise


@router.post(
    "/subcontracts/{subcontract_id}/run",
    response_model=
        DelegationRunResponse,
)
def run_nested_delegation(
    subcontract_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    subcontract = db.get(
        Subcontract,
        subcontract_id,
    )

    if subcontract is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Subcontrato no encontrado."
            ),
        )

    project = _project_or_404(
        db=db,
        project_id=
            subcontract.project_id,
    )

    _check_project_access(
        project=project,
        current_user=current_user,
    )

    try:
        outcome = (
            run_delegation_cycle_for_subcontract(
                db=db,
                subcontract_id=
                    subcontract.id,
            )
        )

        db.commit()

        return DelegationRunResponse(
            decision=
                outcome.decision,
            reason=
                outcome.reason,
            request=(
                serialize_delegation_request(
                    db=db,
                    request=
                        outcome.request,
                )
                if outcome.request
                else None
            ),
        )

    except DelegationValidationError as exc:
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
                "La delegacion entro "
                "en conflicto con otra "
                "operacion concurrente."
            ),
        ) from exc

    except Exception:
        db.rollback()
        raise


@router.get(
    "/projects/{project_id}",
    response_model=
        DelegationProjectSnapshot,
)
def get_project_delegations(
    project_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    project = _project_or_404(
        db=db,
        project_id=project_id,
    )

    _check_project_access(
        project=project,
        current_user=current_user,
    )

    return build_delegation_snapshot(
        db=db,
        project=project,
    )
