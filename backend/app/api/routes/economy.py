from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
    get_db,
)
from app.models.economy import (
    LedgerTransaction,
)
from app.models.project import Project
from app.models.user import User
from app.schemas.economy import (
    LedgerListResponse,
    LedgerTransactionPublic,
    ProjectEconomySnapshot,
    UserWalletSnapshot,
    SimulatedFundingRequest,
    SimulatedFundingResponse,
    SimulatedWithdrawalRequest,
    SimulatedWithdrawalResponse,
)
from app.services.economy_service import (
    EconomyError,
    build_project_economy_snapshot,
    build_user_wallet_snapshot,
    list_project_ledger,
    list_user_ledger,
    simulate_project_funding,
    simulate_withdrawal,
)


router = APIRouter(
    prefix="/economy",
    tags=[
        "Economia simulada",
    ],
)


def _project_access(
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


def _transaction_public(
    transaction:
        LedgerTransaction,
) -> LedgerTransactionPublic:
    return LedgerTransactionPublic(
        id=transaction.id,
        idempotency_key=
            transaction
            .idempotency_key,
        transaction_type=
            transaction
            .transaction_type,
        currency=
            transaction.currency,
        amount_cents=
            transaction.amount_cents,
        from_account_id=
            transaction
            .from_account_id,
        to_account_id=
            transaction
            .to_account_id,
        project_id=
            transaction.project_id,
        contract_id=
            transaction.contract_id,
        repliker_id=
            transaction.repliker_id,
        external_reference=
            transaction
            .external_reference,
        description=
            transaction.description,
        created_at=
            transaction.created_at,
    )


@router.get(
    "/me",
    response_model=
        UserWalletSnapshot,
)
def get_my_wallet(
    currency: str = Query(
        default="PEN",
        min_length=3,
        max_length=10,
    ),
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    try:
        state = (
            build_user_wallet_snapshot(
                db=db,
                user_id=
                    current_user.id,
                currency=currency,
            )
        )

        return UserWalletSnapshot(
            user_id=
                state.user_id,
            currency=
                state.currency,
            available_account_id=
                state
                .available_account_id,
            pending_account_id=
                state
                .pending_account_id,
            available_cents=
                state
                .available_cents,
            pending_cents=
                state
                .pending_cents,
            total_cents=
                state.total_cents,
        )

    except EconomyError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.get(
    "/me/ledger",
    response_model=
        LedgerListResponse,
)
def get_my_ledger(
    currency: str = Query(
        default="PEN",
        min_length=3,
        max_length=10,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    try:
        transactions = (
            list_user_ledger(
                db=db,
                user_id=
                    current_user.id,
                currency=currency,
                limit=limit,
                offset=offset,
            )
        )

        items = [
            _transaction_public(
                transaction
            )
            for transaction
            in transactions
        ]

        return LedgerListResponse(
            items=items,
            count=len(items),
        )

    except EconomyError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.get(
    "/projects/{project_id}",
    response_model=
        ProjectEconomySnapshot,
)
def get_project_economy(
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

    _project_access(
        project=project,
        current_user=current_user,
    )

    state = (
        build_project_economy_snapshot(
            db=db,
            project_id=project.id,
        )
    )

    return ProjectEconomySnapshot(
        project_id=
            state.project_id,
        currency=
            state.currency,
        payment_status=
            state.payment_status,
        custody_account_id=
            state
            .custody_account_id,
        custody_balance_cents=
            state
            .custody_balance_cents,
        contract_reserved_cents=
            state
            .contract_reserved_cents,
        unallocated_cents=
            state
            .unallocated_cents,
    )


@router.get(
    "/projects/{project_id}/ledger",
    response_model=
        LedgerListResponse,
)
def get_project_ledger(
    project_id: int,
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
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

    _project_access(
        project=project,
        current_user=current_user,
    )

    transactions = (
        list_project_ledger(
            db=db,
            project_id=project.id,
            limit=limit,
            offset=offset,
        )
    )

    items = [
        _transaction_public(
            transaction
        )
        for transaction
        in transactions
    ]

    return LedgerListResponse(
        items=items,
        count=len(items),
    )



@router.post(
    "/projects/{project_id}/simulate-funding",
    response_model=
        SimulatedFundingResponse,
)
def simulate_project_payment(
    project_id: int,
    payload:
        SimulatedFundingRequest,
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

    _project_access(
        project=project,
        current_user=current_user,
    )

    try:
        result = (
            simulate_project_funding(
                db=db,
                project_id=
                    project.id,
                idempotency_key=
                    payload
                    .idempotency_key,
                amount_cents=
                    payload
                    .amount_cents,
                initiated_by_user_id=
                    current_user.id,
            )
        )

        db.commit()

        return (
            SimulatedFundingResponse(
                mode="simulation",
                real_money=False,
                project_id=
                    result.project_id,
                transaction_id=
                    result.transaction_id,
                currency=
                    result.currency,
                amount_cents=
                    result.amount_cents,
                required_amount_cents=
                    result
                    .required_amount_cents,
                custody_balance_cents=
                    result
                    .custody_balance_cents,
                remaining_to_fund_cents=
                    result
                    .remaining_to_fund_cents,
                payment_status=
                    result
                    .payment_status,
                fully_funded=
                    result.fully_funded,
            )
        )

    except EconomyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc



@router.post(
    "/me/simulate-withdrawal",
    response_model=
        SimulatedWithdrawalResponse,
)
def simulate_my_withdrawal(
    payload:
        SimulatedWithdrawalRequest,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    try:
        result = simulate_withdrawal(
            db=db,
            user_id=
                current_user.id,
            currency=
                payload.currency,
            amount_cents=
                payload.amount_cents,
            idempotency_key=
                payload.idempotency_key,
        )

        db.commit()

        return (
            SimulatedWithdrawalResponse(
                mode="simulation",
                real_money=False,
                transaction_id=
                    result.transaction_id,
                currency=
                    result.currency,
                amount_cents=
                    result.amount_cents,
                remaining_available_cents=(
                    result
                    .remaining_available_cents
                ),
            )
        )

    except EconomyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
