from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
    get_db,
)
from app.models.contract import (
    TaskContract,
)
from app.models.project import (
    Project,
)
from app.models.repliker import (
    Repliker,
)
from app.models.user import (
    User,
)
from app.schemas.qa import (
    QAReviewPublic,
)
from app.services.qa_service import (
    QAServiceError,
    build_qa_snapshot,
    get_latest_qa_review,
    prepare_qa_review,
)


router = APIRouter(
    prefix="/qa",
    tags=[
        "QA y verificacion",
    ],
)


def _contract_or_404(
    *,
    db: Session,
    contract_id: int,
) -> TaskContract:
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

    return contract


def _can_view(
    *,
    db: Session,
    contract: TaskContract,
    current_user: User,
) -> bool:
    if current_user.role == "admin":
        return True

    project = db.get(
        Project,
        contract.project_id,
    )

    if (
        project is not None
        and project.client_id
        == current_user.id
    ):
        return True

    repliker = db.get(
        Repliker,
        contract.repliker_id,
    )

    return bool(
        repliker is not None
        and repliker.owner_id
        == current_user.id
    )


def _can_prepare(
    *,
    db: Session,
    contract: TaskContract,
    current_user: User,
) -> bool:
    if current_user.role == "admin":
        return True

    project = db.get(
        Project,
        contract.project_id,
    )

    return bool(
        project is not None
        and project.client_id
        == current_user.id
    )


@router.post(
    "/contracts/{contract_id}/prepare",
    response_model=
        QAReviewPublic,
)
def prepare_contract_qa(
    contract_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    contract = _contract_or_404(
        db=db,
        contract_id=
            contract_id,
    )

    if not _can_prepare(
        db=db,
        contract=contract,
        current_user=
            current_user,
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "El Repliker ejecutor "
                "no puede preparar ni aprobar "
                "su propia revision QA."
            ),
        )

    try:
        review = prepare_qa_review(
            db=db,
            contract_id=
                contract.id,
        )

        db.commit()

        db.refresh(
            review
        )

        return build_qa_snapshot(
            db=db,
            review=review,
        )

    except QAServiceError as exc:
        db.rollback()

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.get(
    "/contracts/{contract_id}/latest",
    response_model=
        QAReviewPublic,
)
def latest_contract_qa(
    contract_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    contract = _contract_or_404(
        db=db,
        contract_id=
            contract_id,
    )

    if not _can_view(
        db=db,
        contract=contract,
        current_user=
            current_user,
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "No tienes permiso para "
                "consultar esta revision QA."
            ),
        )

    review = get_latest_qa_review(
        db=db,
        contract_id=
            contract.id,
    )

    if review is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Este contrato todavia "
                "no tiene revisiones QA."
            ),
        )

    return build_qa_snapshot(
        db=db,
        review=review,
    )
