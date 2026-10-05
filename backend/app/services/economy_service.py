from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import (
    func,
    or_,
    select,
)
from sqlalchemy.exc import (
    IntegrityError,
)
from sqlalchemy.orm import Session

from app.models.contract import (
    ACTIVE_CONTRACT_STATUSES,
    TaskContract,
)
from app.models.economy import (
    LEDGER_ACCOUNT_KINDS,
    LEDGER_TRANSACTION_TYPES,
    LedgerAccount,
    LedgerTransaction,
)
from app.models.project import Project
from app.models.user import User
from app.models.repliker import Repliker
from app.models.delegation import (
    DelegationRequest,
    Subcontract,
)
from app.core.config import settings


class EconomyError(ValueError):
    pass


@dataclass(frozen=True)
class UserWalletState:
    user_id: int
    currency: str

    available_account_id: int | None

    pending_account_id: int | None

    available_cents: int
    pending_cents: int
    total_cents: int


@dataclass(frozen=True)
class SimulatedFundingResult:
    transaction_id: int

    project_id: int

    currency: str

    amount_cents: int

    required_amount_cents: int

    custody_balance_cents: int

    remaining_to_fund_cents: int

    payment_status: str

    fully_funded: bool


@dataclass(frozen=True)
class ProjectEconomyState:
    project_id: int
    currency: str
    payment_status: str

    custody_account_id: int | None

    custody_balance_cents: int
    contract_reserved_cents: int
    unallocated_cents: int


def normalize_currency(
    currency: str,
) -> str:
    value = (
        currency
        .strip()
        .upper()
    )

    if (
        len(value) < 3
        or len(value) > 10
        or not value.isalnum()
    ):
        raise EconomyError(
            "Moneda invalida."
        )

    return value


def _account_key(
    *,
    kind: str,
    currency: str,
    user_id: int | None,
    project_id: int | None,
) -> str:
    if kind == "user_available":
        return (
            f"user:{user_id}:"
            f"available:{currency}"
        )

    if kind == "user_pending":
        return (
            f"user:{user_id}:"
            f"pending:{currency}"
        )

    if kind == "project_custody":
        return (
            f"project:{project_id}:"
            f"custody:{currency}"
        )

    if kind == "platform_revenue":
        return (
            f"platform:revenue:"
            f"{currency}"
        )

    if kind == "system_clearing":
        return (
            f"system:clearing:"
            f"{currency}"
        )

    raise EconomyError(
        "Tipo de cuenta desconocido."
    )


def get_account_by_key(
    *,
    db: Session,
    account_key: str,
) -> LedgerAccount | None:
    return db.scalar(
        select(
            LedgerAccount
        )
        .where(
            LedgerAccount.account_key
            == account_key
        )
    )


def ensure_account(
    *,
    db: Session,
    kind: str,
    currency: str,
    user_id: int | None = None,
    project_id: int | None = None,
) -> LedgerAccount:
    if (
        kind
        not in LEDGER_ACCOUNT_KINDS
    ):
        raise EconomyError(
            "Tipo de cuenta invalido."
        )

    currency = normalize_currency(
        currency
    )

    if kind in {
        "user_available",
        "user_pending",
    }:
        if (
            user_id is None
            or project_id is not None
        ):
            raise EconomyError(
                "La cuenta de usuario "
                "requiere user_id."
            )

        if (
            db.get(
                User,
                user_id,
            )
            is None
        ):
            raise EconomyError(
                "Usuario no encontrado."
            )

    elif kind == "project_custody":
        if (
            project_id is None
            or user_id is not None
        ):
            raise EconomyError(
                "La cuenta de custodia "
                "requiere project_id."
            )

        project = db.get(
            Project,
            project_id,
        )

        if project is None:
            raise EconomyError(
                "Proyecto no encontrado."
            )

        if (
            normalize_currency(
                project.currency
            )
            != currency
        ):
            raise EconomyError(
                "La moneda de la cuenta "
                "no coincide con el proyecto."
            )

    else:
        if (
            user_id is not None
            or project_id is not None
        ):
            raise EconomyError(
                "La cuenta de sistema "
                "no admite propietario."
            )

    key = _account_key(
        kind=kind,
        currency=currency,
        user_id=user_id,
        project_id=project_id,
    )

    existing = db.scalar(
        select(
            LedgerAccount
        )
        .where(
            LedgerAccount.account_key
            == key
        )
        .with_for_update()
    )

    if existing is not None:
        return existing

    account = LedgerAccount(
        account_key=key,
        kind=kind,
        currency=currency,
        user_id=user_id,
        project_id=project_id,
        is_active=True,
    )

    try:
        with db.begin_nested():
            db.add(
                account
            )

            db.flush()

        return account

    except IntegrityError as exc:
        existing = db.scalar(
            select(
                LedgerAccount
            )
            .where(
                LedgerAccount.account_key
                == key
            )
        )

        if existing is not None:
            return existing

        raise EconomyError(
            "No se pudo crear "
            "la cuenta del ledger."
        ) from exc


def ensure_user_wallet_accounts(
    *,
    db: Session,
    user_id: int,
    currency: str,
) -> tuple[
    LedgerAccount,
    LedgerAccount,
]:
    available = ensure_account(
        db=db,
        kind="user_available",
        currency=currency,
        user_id=user_id,
    )

    pending = ensure_account(
        db=db,
        kind="user_pending",
        currency=currency,
        user_id=user_id,
    )

    return (
        available,
        pending,
    )


def ensure_project_custody_account(
    *,
    db: Session,
    project_id: int,
) -> LedgerAccount:
    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise EconomyError(
            "Proyecto no encontrado."
        )

    return ensure_account(
        db=db,
        kind="project_custody",
        currency=project.currency,
        project_id=project.id,
    )


def ensure_platform_revenue_account(
    *,
    db: Session,
    currency: str,
) -> LedgerAccount:
    return ensure_account(
        db=db,
        kind="platform_revenue",
        currency=currency,
    )


def ensure_system_clearing_account(
    *,
    db: Session,
    currency: str,
) -> LedgerAccount:
    return ensure_account(
        db=db,
        kind="system_clearing",
        currency=currency,
    )


def account_balance(
    *,
    db: Session,
    account_id: int,
) -> int:
    account = db.get(
        LedgerAccount,
        account_id,
    )

    if account is None:
        raise EconomyError(
            "Cuenta del ledger "
            "no encontrada."
        )

    incoming = int(
        db.scalar(
            select(
                func.coalesce(
                    func.sum(
                        LedgerTransaction
                        .amount_cents
                    ),
                    0,
                )
            )
            .where(
                LedgerTransaction
                .to_account_id
                == account.id
            )
        )
        or 0
    )

    outgoing = int(
        db.scalar(
            select(
                func.coalesce(
                    func.sum(
                        LedgerTransaction
                        .amount_cents
                    ),
                    0,
                )
            )
            .where(
                LedgerTransaction
                .from_account_id
                == account.id
            )
        )
        or 0
    )

    return incoming - outgoing


def _validate_existing_transfer(
    *,
    existing: LedgerTransaction,
    transaction_type: str,
    amount_cents: int,
    from_account_id: int,
    to_account_id: int,
    project_id: int | None,
    contract_id: int | None,
    repliker_id: int | None,
):
    matches = (
        existing.transaction_type
        == transaction_type
        and existing.amount_cents
        == amount_cents
        and existing.from_account_id
        == from_account_id
        and existing.to_account_id
        == to_account_id
        and existing.project_id
        == project_id
        and existing.contract_id
        == contract_id
        and existing.repliker_id
        == repliker_id
    )

    if not matches:
        raise EconomyError(
            "La clave de idempotencia "
            "ya pertenece a otra "
            "transferencia."
        )


def post_transfer(
    *,
    db: Session,
    idempotency_key: str,
    transaction_type: str,
    amount_cents: int,
    from_account_id: int,
    to_account_id: int,
    project_id: int | None = None,
    contract_id: int | None = None,
    repliker_id: int | None = None,
    initiated_by_user_id:
        int | None = None,
    external_reference:
        str | None = None,
    description: str = "",
) -> LedgerTransaction:
    key = (
        idempotency_key
        .strip()
    )

    if (
        not key
        or len(key) > 180
    ):
        raise EconomyError(
            "Clave de idempotencia "
            "invalida."
        )

    if (
        transaction_type
        not in LEDGER_TRANSACTION_TYPES
    ):
        raise EconomyError(
            "Tipo de transaccion "
            "invalido."
        )

    if amount_cents <= 0:
        raise EconomyError(
            "El importe debe ser "
            "mayor que cero."
        )

    if (
        from_account_id
        == to_account_id
    ):
        raise EconomyError(
            "Una transferencia no puede "
            "usar la misma cuenta como "
            "origen y destino."
        )

    existing = db.scalar(
        select(
            LedgerTransaction
        )
        .where(
            LedgerTransaction
            .idempotency_key
            == key
        )
        .with_for_update()
    )

    if existing is not None:
        _validate_existing_transfer(
            existing=existing,
            transaction_type=
                transaction_type,
            amount_cents=
                amount_cents,
            from_account_id=
                from_account_id,
            to_account_id=
                to_account_id,
            project_id=
                project_id,
            contract_id=
                contract_id,
            repliker_id=
                repliker_id,
        )

        return existing

    accounts = list(
        db.scalars(
            select(
                LedgerAccount
            )
            .where(
                LedgerAccount.id.in_(
                    [
                        from_account_id,
                        to_account_id,
                    ]
                )
            )
            .with_for_update()
        ).all()
    )

    by_id = {
        account.id:
            account
        for account in accounts
    }

    source = by_id.get(
        from_account_id
    )

    destination = by_id.get(
        to_account_id
    )

    if (
        source is None
        or destination is None
    ):
        raise EconomyError(
            "Cuenta de origen o destino "
            "no encontrada."
        )

    if (
        not source.is_active
        or not destination.is_active
    ):
        raise EconomyError(
            "La transferencia utiliza "
            "una cuenta inactiva."
        )

    if (
        source.currency
        != destination.currency
    ):
        raise EconomyError(
            "No se permiten transferencias "
            "entre monedas distintas."
        )

    if (
        source.kind
        != "system_clearing"
    ):
        balance = account_balance(
            db=db,
            account_id=
                source.id,
        )

        if (
            balance
            < amount_cents
        ):
            raise EconomyError(
                "Saldo insuficiente."
            )

    transaction = LedgerTransaction(
        idempotency_key=key,
        transaction_type=
            transaction_type,
        currency=
            source.currency,
        amount_cents=
            amount_cents,
        from_account_id=
            source.id,
        to_account_id=
            destination.id,
        project_id=
            project_id,
        contract_id=
            contract_id,
        repliker_id=
            repliker_id,
        initiated_by_user_id=
            initiated_by_user_id,
        external_reference=(
            external_reference.strip()
            if external_reference
            else None
        ),
        description=(
            description[:4000]
        ),
    )

    try:
        with db.begin_nested():
            db.add(
                transaction
            )

            db.flush()

        return transaction

    except IntegrityError as exc:
        existing = db.scalar(
            select(
                LedgerTransaction
            )
            .where(
                LedgerTransaction
                .idempotency_key
                == key
            )
        )

        if existing is None:
            raise EconomyError(
                "No se pudo registrar "
                "la transferencia."
            ) from exc

        _validate_existing_transfer(
            existing=existing,
            transaction_type=
                transaction_type,
            amount_cents=
                amount_cents,
            from_account_id=
                from_account_id,
            to_account_id=
                to_account_id,
            project_id=
                project_id,
            contract_id=
                contract_id,
            repliker_id=
                repliker_id,
        )

        return existing


def _account_if_exists(
    *,
    db: Session,
    account_key: str,
) -> LedgerAccount | None:
    return db.scalar(
        select(
            LedgerAccount
        )
        .where(
            LedgerAccount.account_key
            == account_key
        )
    )


def build_user_wallet_snapshot(
    *,
    db: Session,
    user_id: int,
    currency: str,
) -> UserWalletState:
    if (
        db.get(
            User,
            user_id,
        )
        is None
    ):
        raise EconomyError(
            "Usuario no encontrado."
        )

    currency = normalize_currency(
        currency
    )

    available = _account_if_exists(
        db=db,
        account_key=
            _account_key(
                kind=
                    "user_available",
                currency=
                    currency,
                user_id=
                    user_id,
                project_id=
                    None,
            ),
    )

    pending = _account_if_exists(
        db=db,
        account_key=
            _account_key(
                kind=
                    "user_pending",
                currency=
                    currency,
                user_id=
                    user_id,
                project_id=
                    None,
            ),
    )

    available_balance = (
        account_balance(
            db=db,
            account_id=
                available.id,
        )
        if available is not None
        else 0
    )

    pending_balance = (
        account_balance(
            db=db,
            account_id=
                pending.id,
        )
        if pending is not None
        else 0
    )

    return UserWalletState(
        user_id=user_id,
        currency=currency,
        available_account_id=(
            available.id
            if available
            else None
        ),
        pending_account_id=(
            pending.id
            if pending
            else None
        ),
        available_cents=
            available_balance,
        pending_cents=
            pending_balance,
        total_cents=(
            available_balance
            + pending_balance
        ),
    )


def build_project_economy_snapshot(
    *,
    db: Session,
    project_id: int,
) -> ProjectEconomyState:
    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise EconomyError(
            "Proyecto no encontrado."
        )

    currency = normalize_currency(
        project.currency
    )

    account = _account_if_exists(
        db=db,
        account_key=
            _account_key(
                kind=
                    "project_custody",
                currency=
                    currency,
                user_id=
                    None,
                project_id=
                    project.id,
            ),
    )

    custody_balance = (
        account_balance(
            db=db,
            account_id=
                account.id,
        )
        if account is not None
        else 0
    )

    contract_reserved = int(
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
                == project.id,
                TaskContract.status.in_(
                    ACTIVE_CONTRACT_STATUSES
                ),
            )
        )
        or 0
    )

    return ProjectEconomyState(
        project_id=
            project.id,
        currency=
            currency,
        payment_status=
            project.payment_status,
        custody_account_id=(
            account.id
            if account
            else None
        ),
        custody_balance_cents=
            custody_balance,
        contract_reserved_cents=
            contract_reserved,
        unallocated_cents=
            max(
                0,
                custody_balance
                - contract_reserved,
            ),
    )


def list_transactions_for_accounts(
    *,
    db: Session,
    account_ids: list[int],
    limit: int = 50,
    offset: int = 0,
) -> list[LedgerTransaction]:
    if not account_ids:
        return []

    safe_limit = max(
        1,
        min(
            int(limit),
            200,
        ),
    )

    safe_offset = max(
        0,
        int(offset),
    )

    return list(
        db.scalars(
            select(
                LedgerTransaction
            )
            .where(
                or_(
                    LedgerTransaction
                    .from_account_id
                    .in_(
                        account_ids
                    ),
                    LedgerTransaction
                    .to_account_id
                    .in_(
                        account_ids
                    ),
                )
            )
            .order_by(
                LedgerTransaction
                .id.desc()
            )
            .offset(
                safe_offset
            )
            .limit(
                safe_limit
            )
        ).all()
    )


def list_user_ledger(
    *,
    db: Session,
    user_id: int,
    currency: str,
    limit: int = 50,
    offset: int = 0,
) -> list[LedgerTransaction]:
    snapshot = (
        build_user_wallet_snapshot(
            db=db,
            user_id=user_id,
            currency=currency,
        )
    )

    account_ids = [
        account_id
        for account_id
        in [
            snapshot
            .available_account_id,
            snapshot
            .pending_account_id,
        ]
        if account_id is not None
    ]

    return (
        list_transactions_for_accounts(
            db=db,
            account_ids=
                account_ids,
            limit=limit,
            offset=offset,
        )
    )


def list_project_ledger(
    *,
    db: Session,
    project_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[LedgerTransaction]:
    snapshot = (
        build_project_economy_snapshot(
            db=db,
            project_id=project_id,
        )
    )

    if (
        snapshot.custody_account_id
        is None
    ):
        return []

    return (
        list_transactions_for_accounts(
            db=db,
            account_ids=[
                snapshot
                .custody_account_id
            ],
            limit=limit,
            offset=offset,
        )
    )



# ============================================================
# FINANCIACION SIMULADA
# ============================================================

def ensure_simulation_mode():
    if (
        settings.ECONOMY_MODE
        != "simulation"
    ):
        raise EconomyError(
            "La economia no esta "
            "en modo simulacion."
        )

    if (
        settings.REAL_PAYMENTS_ENABLED
    ):
        raise EconomyError(
            "Los pagos reales deben "
            "permanecer desactivados "
            "durante las pruebas."
        )


def required_project_funding_cents(
    project: Project,
) -> int:
    if bool(
        getattr(
            project,
            "is_admin_free",
            False,
        )
    ):
        return 0

    quoted = (
        project.quoted_amount_cents
        or 0
    )

    budget = (
        project.budget_limit_cents
        or 0
    )

    if quoted > 0:
        required = quoted
    else:
        required = budget

    if required <= 0:
        raise EconomyError(
            "El proyecto no tiene "
            "un importe financiable."
        )

    if (
        budget > 0
        and required > budget
    ):
        raise EconomyError(
            "El importe cotizado supera "
            "el presupuesto del proyecto."
        )

    return int(
        required
    )


def project_has_sufficient_custody(
    *,
    db: Session,
    project: Project,
) -> bool:
    if bool(
        getattr(
            project,
            "is_admin_free",
            False,
        )
    ):
        return True

    required = (
        required_project_funding_cents(
            project
        )
    )

    snapshot = (
        build_project_economy_snapshot(
            db=db,
            project_id=project.id,
        )
    )

    return (
        snapshot.custody_balance_cents
        >= required
    )


def sync_project_payment_status(
    *,
    db: Session,
    project: Project,
) -> str:
    if bool(
        getattr(
            project,
            "is_admin_free",
            False,
        )
    ):
        project.payment_status = (
            "admin_free"
        )

        db.flush()

        return "admin_free"

    required = (
        required_project_funding_cents(
            project
        )
    )

    snapshot = (
        build_project_economy_snapshot(
            db=db,
            project_id=project.id,
        )
    )

    balance = (
        snapshot.custody_balance_cents
    )

    if balance >= required:
        status = "escrowed"

    elif balance > 0:
        status = "partially_funded"

    else:
        status = "unpaid"

    project.payment_status = status

    db.flush()

    return status


def simulate_project_funding(
    *,
    db: Session,
    project_id: int,
    idempotency_key: str,
    amount_cents: int | None = None,
    initiated_by_user_id:
        int | None = None,
) -> SimulatedFundingResult:
    """
    Introduce dinero FICTICIO en la
    custodia del proyecto.

    system_clearing representa la fuente
    simulada de fondos.

    No existe proveedor bancario,
    tarjeta, wallet ni dinero real.
    """

    ensure_simulation_mode()

    project = db.scalar(
        select(
            Project
        )
        .where(
            Project.id
            == project_id
        )
        .with_for_update()
    )

    if project is None:
        raise EconomyError(
            "Proyecto no encontrado."
        )

    if bool(
        getattr(
            project,
            "is_admin_free",
            False,
        )
    ):
        raise EconomyError(
            "Los proyectos gratuitos "
            "de administrador no requieren "
            "financiación."
        )

    required = (
        required_project_funding_cents(
            project
        )
    )

    clearing = (
        ensure_system_clearing_account(
            db=db,
            currency=project.currency,
        )
    )

    custody = (
        ensure_project_custody_account(
            db=db,
            project_id=project.id,
        )
    )

    key = (
        idempotency_key
        .strip()
    )

    if not key:
        raise EconomyError(
            "La clave de idempotencia "
            "es obligatoria."
        )

    existing = db.scalar(
        select(
            LedgerTransaction
        )
        .where(
            LedgerTransaction
            .idempotency_key
            == key
        )
        .with_for_update()
    )

    if existing is not None:
        valid_existing = (
            existing.transaction_type
            == "funding"
            and existing.project_id
            == project.id
            and existing.from_account_id
            == clearing.id
            and existing.to_account_id
            == custody.id
        )

        if not valid_existing:
            raise EconomyError(
                "La clave de idempotencia "
                "ya pertenece a otra "
                "operacion."
            )

        if (
            amount_cents is not None
            and existing.amount_cents
            != amount_cents
        ):
            raise EconomyError(
                "La clave de idempotencia "
                "fue reutilizada con "
                "otro importe."
            )

        status = (
            sync_project_payment_status(
                db=db,
                project=project,
            )
        )

        balance = account_balance(
            db=db,
            account_id=custody.id,
        )

        return SimulatedFundingResult(
            transaction_id=
                existing.id,
            project_id=
                project.id,
            currency=
                project.currency,
            amount_cents=
                existing.amount_cents,
            required_amount_cents=
                required,
            custody_balance_cents=
                balance,
            remaining_to_fund_cents=
                max(
                    0,
                    required - balance,
                ),
            payment_status=
                status,
            fully_funded=(
                balance >= required
            ),
        )

    current_balance = (
        account_balance(
            db=db,
            account_id=custody.id,
        )
    )

    remaining = max(
        0,
        required - current_balance,
    )

    if remaining <= 0:
        sync_project_payment_status(
            db=db,
            project=project,
        )

        raise EconomyError(
            "El proyecto ya esta "
            "completamente financiado."
        )

    amount = (
        remaining
        if amount_cents is None
        else int(amount_cents)
    )

    if amount <= 0:
        raise EconomyError(
            "El importe debe ser "
            "mayor que cero."
        )

    if amount > remaining:
        raise EconomyError(
            "El pago simulado supera "
            "el importe pendiente "
            "del proyecto."
        )

    transaction = post_transfer(
        db=db,
        idempotency_key=key,
        transaction_type="funding",
        amount_cents=amount,
        from_account_id=
            clearing.id,
        to_account_id=
            custody.id,
        project_id=
            project.id,
        initiated_by_user_id=
            initiated_by_user_id,
        external_reference=(
            f"SIM-PROJECT-"
            f"{project.id}"
        ),
        description=(
            "Financiacion ficticia "
            "del proyecto en modo "
            "simulacion."
        ),
    )

    status = (
        sync_project_payment_status(
            db=db,
            project=project,
        )
    )

    balance = account_balance(
        db=db,
        account_id=custody.id,
    )

    return SimulatedFundingResult(
        transaction_id=
            transaction.id,
        project_id=
            project.id,
        currency=
            project.currency,
        amount_cents=
            transaction.amount_cents,
        required_amount_cents=
            required,
        custody_balance_cents=
            balance,
        remaining_to_fund_cents=
            max(
                0,
                required - balance,
            ),
        payment_status=
            status,
        fully_funded=(
            balance >= required
        ),
    )



# ============================================================
# LIQUIDACION SIMULADA
# ============================================================

@dataclass(frozen=True)
class ContractEarningAllocation:
    repliker_id: int
    owner_id: int
    gross_cents: int
    commission_cents: int
    owner_net_cents: int


@dataclass(frozen=True)
class ContractSettlementResult:
    contract_id: int
    project_id: int
    currency: str
    gross_cents: int
    owner_net_cents: int
    commission_cents: int
    allocations: list[
        ContractEarningAllocation
    ]


@dataclass(frozen=True)
class SimulatedWithdrawalResult:
    transaction_id: int
    currency: str
    amount_cents: int
    remaining_available_cents: int


def platform_commission_bps() -> int:
    value = int(
        settings
        .PLATFORM_COMMISSION_BPS
    )

    if (
        value < 0
        or value > 10_000
    ):
        raise EconomyError(
            "La comision de plataforma "
            "es invalida."
        )

    return value


def _contract_net_allocations(
    *,
    db: Session,
    contract: TaskContract,
) -> dict[int, int]:
    """
    Calcula cuanto corresponde realmente
    a cada Repliker.

    Si A delega parte a B y B delega parte
    a C, no contamos dos veces ese dinero.

    A = contrato - delegaciones directas
    B = subcontrato - delegaciones directas de B
    C = su importe neto
    """

    subcontracts = list(
        db.scalars(
            select(
                Subcontract
            )
            .where(
                Subcontract.root_contract_id
                == contract.id,
                Subcontract.status.in_(
                    (
                        "awarded",
                        "active",
                        "completed",
                    )
                ),
            )
            .order_by(
                Subcontract.depth,
                Subcontract.id,
            )
        ).all()
    )

    if not subcontracts:
        return {
            contract.repliker_id:
                contract.amount_cents
        }

    request_ids = [
        subcontract
        .delegation_request_id
        for subcontract
        in subcontracts
    ]

    requests = list(
        db.scalars(
            select(
                DelegationRequest
            )
            .where(
                DelegationRequest.id.in_(
                    request_ids
                )
            )
        ).all()
    )

    request_by_id = {
        request.id:
            request
        for request in requests
    }

    direct_child_totals: dict[
        int | None,
        int,
    ] = {}

    for subcontract in subcontracts:
        request = request_by_id.get(
            subcontract
            .delegation_request_id
        )

        if request is None:
            raise EconomyError(
                "La cadena de delegacion "
                "esta incompleta."
            )

        parent_id = (
            request.parent_request_id
        )

        direct_child_totals[
            parent_id
        ] = (
            direct_child_totals.get(
                parent_id,
                0,
            )
            + subcontract.amount_cents
        )

    principal_net = (
        contract.amount_cents
        - direct_child_totals.get(
            None,
            0,
        )
    )

    if principal_net < 0:
        raise EconomyError(
            "Las delegaciones superan "
            "el importe del contrato."
        )

    allocations: dict[int, int] = {
        contract.repliker_id:
            principal_net
    }

    for subcontract in subcontracts:
        child_total = (
            direct_child_totals.get(
                subcontract
                .delegation_request_id,
                0,
            )
        )

        net = (
            subcontract.amount_cents
            - child_total
        )

        if net < 0:
            raise EconomyError(
                "Una cadena de delegacion "
                "supera su presupuesto."
            )

        allocations[
            subcontract
            .subcontractor_repliker_id
        ] = (
            allocations.get(
                subcontract
                .subcontractor_repliker_id,
                0,
            )
            + net
        )

    if (
        sum(
            allocations.values()
        )
        != contract.amount_cents
    ):
        raise EconomyError(
            "La distribucion economica "
            "del contrato no conserva "
            "el importe total."
        )

    return allocations


def settle_contract_earnings(
    *,
    db: Session,
    contract_id: int,
) -> ContractSettlementResult:
    """
    Liquida un contrato aprobado.

    El dinero sigue siendo SIMULADO.
    El propietario humano recibe la
    ganancia en saldo pendiente.
    """

    ensure_simulation_mode()

    contract = db.scalar(
        select(
            TaskContract
        )
        .where(
            TaskContract.id
            == contract_id
        )
        .with_for_update()
    )

    if contract is None:
        raise EconomyError(
            "Contrato no encontrado."
        )

    if contract.status != "completed":
        raise EconomyError(
            "Solo se puede liquidar "
            "un contrato completado."
        )

    project = db.get(
        Project,
        contract.project_id,
    )

    if project is None:
        raise EconomyError(
            "Proyecto no encontrado."
        )

    custody = (
        ensure_project_custody_account(
            db=db,
            project_id=
                project.id,
        )
    )

    allocations = (
        _contract_net_allocations(
            db=db,
            contract=contract,
        )
    )

    gross_total = sum(
        allocations.values()
    )

    already_settled = int(
        db.scalar(
            select(
                func.coalesce(
                    func.sum(
                        LedgerTransaction
                        .amount_cents
                    ),
                    0,
                )
            )
            .where(
                LedgerTransaction
                .contract_id
                == contract.id,
                LedgerTransaction
                .from_account_id
                == custody.id,
                LedgerTransaction
                .transaction_type.in_(
                    (
                        "earning",
                        "commission",
                    )
                ),
            )
        )
        or 0
    )

    if already_settled > gross_total:
        raise EconomyError(
            "La liquidacion registrada "
            "supera el importe "
            "del contrato."
        )

    missing_to_settle = (
        gross_total
        - already_settled
    )

    if (
        account_balance(
            db=db,
            account_id=custody.id,
        )
        < missing_to_settle
    ):
        raise EconomyError(
            "La custodia no contiene "
            "fondos suficientes para "
            "completar la liquidacion."
        )

    commission_bps = (
        platform_commission_bps()
    )

    platform = (
        ensure_platform_revenue_account(
            db=db,
            currency=
                contract.currency,
        )
    )

    result_lines: list[
        ContractEarningAllocation
    ] = []

    total_owner = 0
    total_commission = 0

    for (
        repliker_id,
        gross,
    ) in sorted(
        allocations.items()
    ):
        if gross <= 0:
            continue

        repliker = db.get(
            Repliker,
            repliker_id,
        )

        if repliker is None:
            raise EconomyError(
                "Repliker beneficiario "
                "no encontrado."
            )

        owner = db.get(
            User,
            repliker.owner_id,
        )

        if owner is None:
            raise EconomyError(
                "Propietario del Repliker "
                "no encontrado."
            )

        _, pending = (
            ensure_user_wallet_accounts(
                db=db,
                user_id=owner.id,
                currency=
                    contract.currency,
            )
        )

        commission = (
            gross
            * commission_bps
            // 10_000
        )

        owner_net = (
            gross - commission
        )

        if owner_net > 0:
            post_transfer(
                db=db,
                idempotency_key=(
                    "settlement:"
                    f"contract:{contract.id}:"
                    f"repliker:{repliker.id}:"
                    "earning:v1"
                ),
                transaction_type=
                    "earning",
                amount_cents=
                    owner_net,
                from_account_id=
                    custody.id,
                to_account_id=
                    pending.id,
                project_id=
                    project.id,
                contract_id=
                    contract.id,
                repliker_id=
                    repliker.id,
                description=(
                    "Ganancia ficticia "
                    "aprobada por QA."
                ),
            )

        if commission > 0:
            post_transfer(
                db=db,
                idempotency_key=(
                    "settlement:"
                    f"contract:{contract.id}:"
                    f"repliker:{repliker.id}:"
                    "commission:v1"
                ),
                transaction_type=
                    "commission",
                amount_cents=
                    commission,
                from_account_id=
                    custody.id,
                to_account_id=
                    platform.id,
                project_id=
                    project.id,
                contract_id=
                    contract.id,
                repliker_id=
                    repliker.id,
                description=(
                    "Comision ficticia "
                    "de plataforma."
                ),
            )

        total_owner += owner_net
        total_commission += commission

        result_lines.append(
            ContractEarningAllocation(
                repliker_id=
                    repliker.id,
                owner_id=
                    owner.id,
                gross_cents=
                    gross,
                commission_cents=
                    commission,
                owner_net_cents=
                    owner_net,
            )
        )

    if (
        total_owner
        + total_commission
        != gross_total
    ):
        raise EconomyError(
            "La liquidacion no conserva "
            "el importe del contrato."
        )

    return ContractSettlementResult(
        contract_id=
            contract.id,
        project_id=
            project.id,
        currency=
            contract.currency,
        gross_cents=
            gross_total,
        owner_net_cents=
            total_owner,
        commission_cents=
            total_commission,
        allocations=
            result_lines,
    )


def release_project_earnings(
    *,
    db: Session,
    project_id: int,
) -> int:
    """
    Al finalizar el proyecto mueve las
    ganancias ficticias de pendiente a
    disponible.
    """

    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise EconomyError(
            "Proyecto no encontrado."
        )

    earning_rows = list(
        db.execute(
            select(
                LedgerTransaction,
                LedgerAccount,
            )
            .join(
                LedgerAccount,
                LedgerAccount.id
                == LedgerTransaction
                .to_account_id,
            )
            .where(
                LedgerTransaction.project_id
                == project.id,
                LedgerTransaction
                .transaction_type
                == "earning",
                LedgerAccount.kind
                == "user_pending",
            )
        ).all()
    )

    amounts_by_user: dict[
        int,
        int,
    ] = {}

    for transaction, account in (
        earning_rows
    ):
        if account.user_id is None:
            raise EconomyError(
                "Cuenta pendiente sin "
                "propietario."
            )

        amounts_by_user[
            account.user_id
        ] = (
            amounts_by_user.get(
                account.user_id,
                0,
            )
            + transaction.amount_cents
        )

    released = 0

    for (
        user_id,
        amount,
    ) in sorted(
        amounts_by_user.items()
    ):
        if amount <= 0:
            continue

        available, pending = (
            ensure_user_wallet_accounts(
                db=db,
                user_id=user_id,
                currency=
                    project.currency,
            )
        )

        post_transfer(
            db=db,
            idempotency_key=(
                "release:"
                f"project:{project.id}:"
                f"user:{user_id}:v1"
            ),
            transaction_type=
                "allocation",
            amount_cents=
                amount,
            from_account_id=
                pending.id,
            to_account_id=
                available.id,
            project_id=
                project.id,
            description=(
                "Liberacion ficticia "
                "de ganancias al "
                "completar el proyecto."
            ),
        )

        released += amount

    return released


def refund_project_remainder(
    *,
    db: Session,
    project_id: int,
) -> int:
    """
    Devuelve al cliente cualquier saldo
    ficticio que haya quedado sin gastar.
    """

    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise EconomyError(
            "Proyecto no encontrado."
        )

    custody = (
        ensure_project_custody_account(
            db=db,
            project_id=
                project.id,
        )
    )

    remainder = account_balance(
        db=db,
        account_id=custody.id,
    )

    if remainder <= 0:
        return 0

    available, _ = (
        ensure_user_wallet_accounts(
            db=db,
            user_id=
                project.client_id,
            currency=
                project.currency,
        )
    )

    post_transfer(
        db=db,
        idempotency_key=(
            "refund:"
            f"project:{project.id}:"
            "remainder:v1"
        ),
        transaction_type=
            "refund",
        amount_cents=
            remainder,
        from_account_id=
            custody.id,
        to_account_id=
            available.id,
        project_id=
            project.id,
        initiated_by_user_id=
            project.client_id,
        description=(
            "Reembolso ficticio "
            "del saldo no utilizado."
        ),
    )

    return remainder


def finalize_project_economy(
    *,
    db: Session,
    project_id: int,
) -> dict:
    ensure_simulation_mode()

    released = (
        release_project_earnings(
            db=db,
            project_id=project_id,
        )
    )

    refunded = (
        refund_project_remainder(
            db=db,
            project_id=project_id,
        )
    )

    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise EconomyError(
            "Proyecto no encontrado."
        )

    project.payment_status = (
        "settled"
    )

    db.flush()

    return {
        "released_cents":
            released,
        "refunded_cents":
            refunded,
        "payment_status":
            project.payment_status,
    }


def simulate_withdrawal(
    *,
    db: Session,
    user_id: int,
    currency: str,
    amount_cents: int,
    idempotency_key: str,
) -> SimulatedWithdrawalResult:
    """
    Retiro exclusivamente ficticio.

    No llama a bancos, tarjetas,
    Yape, Plin ni proveedores reales.
    """

    ensure_simulation_mode()

    currency = normalize_currency(
        currency
    )

    available, _ = (
        ensure_user_wallet_accounts(
            db=db,
            user_id=user_id,
            currency=currency,
        )
    )

    clearing = (
        ensure_system_clearing_account(
            db=db,
            currency=currency,
        )
    )

    transaction = post_transfer(
        db=db,
        idempotency_key=(
            idempotency_key
        ),
        transaction_type=
            "withdrawal",
        amount_cents=
            amount_cents,
        from_account_id=
            available.id,
        to_account_id=
            clearing.id,
        initiated_by_user_id=
            user_id,
        external_reference=(
            f"SIM-WITHDRAWAL-"
            f"{user_id}"
        ),
        description=(
            "Retiro ficticio del "
            "saldo simulado."
        ),
    )

    remaining = account_balance(
        db=db,
        account_id=
            available.id,
    )

    return SimulatedWithdrawalResult(
        transaction_id=
            transaction.id,
        currency=
            currency,
        amount_cents=
            transaction.amount_cents,
        remaining_available_cents=
            remaining,
    )
