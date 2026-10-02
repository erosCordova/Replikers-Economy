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
from app.models.qa import (
    QAReview,
)
from app.models.repliker import (
    Repliker,
)
from app.models.user import User
from app.schemas.qa import (
    QAReviewPublic,
)
from app.schemas.qa_workflow import (
    QAFollowupPublic,
    QAReputationEventPublic,
    QARetryRunPublic,
)
from app.services.gemini_client import (
    GeminiConfigurationError,
    GeminiResponseError,
)
from app.services.qa_evaluation_service import (
    QAEvaluationError,
    evaluate_contract_qa,
)
from app.services.qa_service import (
    QAServiceError,
    build_qa_snapshot,
    get_latest_qa_review,
    prepare_qa_review,
)
from app.services.qa_workflow_service import (
    MAX_QA_ATTEMPTS,
    QAWorkflowError,
    build_followup,
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


def _review_or_404(
    *,
    db: Session,
    review_id: int,
) -> QAReview:
    review = db.get(
        QAReview,
        review_id,
    )

    if review is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Revision QA no encontrada."
            ),
        )

    return review


def _project(
    *,
    db: Session,
    contract: TaskContract,
) -> Project | None:
    return db.get(
        Project,
        contract.project_id,
    )


def _can_view(
    *,
    db: Session,
    contract: TaskContract,
    current_user: User,
) -> bool:
    if current_user.role == "admin":
        return True

    project = _project(
        db=db,
        contract=contract,
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


def _can_control_qa(
    *,
    db: Session,
    contract: TaskContract,
    current_user: User,
) -> bool:
    if current_user.role == "admin":
        return True

    project = _project(
        db=db,
        contract=contract,
    )

    return bool(
        project is not None
        and project.client_id
        == current_user.id
    )


@router.post(
    "/contracts/{contract_id}/prepare",
    response_model=QAReviewPublic,
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

    if not _can_control_qa(
        db=db,
        contract=contract,
        current_user=
            current_user,
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "El propietario del "
                "Repliker ejecutor no puede "
                "controlar su propia "
                "revision QA."
            ),
        )

    try:
        review = prepare_qa_review(
            db=db,
            contract_id=
                contract.id,
        )

        db.commit()
        db.refresh(review)

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


@router.post(
    "/contracts/{contract_id}/evaluate",
    response_model=QAReviewPublic,
)
def evaluate_contract_review(
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

    if not _can_control_qa(
        db=db,
        contract=contract,
        current_user=
            current_user,
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "El propietario del "
                "Repliker ejecutor no puede "
                "aprobar su propia entrega."
            ),
        )

    try:
        review = evaluate_contract_qa(
            db=db,
            contract_id=
                contract.id,
        )

        db.commit()
        db.refresh(review)

        return build_qa_snapshot(
            db=db,
            review=review,
        )

    except QAEvaluationError as exc:
        db.rollback()

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except GeminiConfigurationError as exc:
        db.rollback()

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except GeminiResponseError as exc:
        db.rollback()

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


@router.post(
    "/reviews/{review_id}/followup",
    response_model=QAFollowupPublic,
)
def followup_review(
    review_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    review = _review_or_404(
        db=db,
        review_id=
            review_id,
    )

    contract = _contract_or_404(
        db=db,
        contract_id=
            review.contract_id,
    )

    if not _can_control_qa(
        db=db,
        contract=contract,
        current_user=
            current_user,
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "No tienes permiso para "
                "procesar el follow-up QA."
            ),
        )

    try:
        result = build_followup(
            db=db,
            review=review,
            run_retry=True,
        )

        retry = result[
            "retry"
        ]

        reputation = result[
            "reputation"
        ]

        return QAFollowupPublic(
            review_id=
                review.id,
            review_status=
                review.status,
            attempt_number=
                review.attempt_number,
            max_attempts=
                MAX_QA_ATTEMPTS,
            action=
                str(
                    result[
                        "action"
                    ]
                ),
            retry=(
                QARetryRunPublic
                .model_validate(
                    retry
                )
                if retry is not None
                else None
            ),
            reputation=(
                QAReputationEventPublic
                .model_validate(
                    reputation
                )
                if reputation
                is not None
                else None
            ),
            trace=[
                str(item)
                for item
                in result[
                    "trace"
                ]
            ],
        )

    except QAWorkflowError as exc:
        db.rollback()

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.get(
    "/contracts/{contract_id}/latest",
    response_model=QAReviewPublic,
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
