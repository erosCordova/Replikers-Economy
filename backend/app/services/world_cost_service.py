
"""Costos contractuales verificados de Replikers World.

Un gasto existe solamente cuando el ledger registra
una transferencia RCR del vendedor a un proveedor.

No se consideran gastos verificados los costos
estimados por un modelo de IA.

El margen despues de gastos registrados NO equivale
a beneficio neto definitivo: pueden faltar costos.

Servicio interno: el identificador acting_repliker_id
debe proceder de autenticacion confiable antes de
exponerse mediante API.

El llamante controla commit y rollback.
"""

import re

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    CheckConstraint,
    func,
    insert,
    select,
)
from sqlalchemy.orm import Session

from app.models.economy import (
    LedgerAccount,
    LedgerTransaction,
)
from app.models.repliker import Repliker

from app.agentic.world_strategy_evaluation import (
    get_strategy_comparison,
)
from app.agentic.world_social_learning import adoptions
from app.agentic.world_negotiation_graph import negotiations

from app.services.world_contract_service import (
    contracts,
    get_contract,
)
from app.services.world_contract_service import ContractError
from app.services.economy_service import (
    ensure_simulation_mode,
    post_transfer,
    EconomyError,
)


class WorldCostError(ValueError):
    pass


metadata = MetaData()

expenses = Table(
    "world_contract_expenses",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "contract_id",
        Integer,
        ForeignKey("world_contracts.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "seller_repliker_id",
        Integer,
        ForeignKey("replikers.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "provider_repliker_id",
        Integer,
        ForeignKey("replikers.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "ledger_transaction_id",
        Integer,
        ForeignKey(
            "ledger_transactions.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        unique=True,
    ),
    Column("expense_key", String(48), nullable=False),
    Column("amount_cents", Integer, nullable=False),
    Column("note", String(240), nullable=False),
    Column(
        "created_at",
        DateTime,
        server_default=func.current_timestamp(),
        nullable=False,
    ),
    UniqueConstraint(
        "contract_id",
        "expense_key",
        name="uq_world_cost_contract_key",
    ),
    CheckConstraint(
        "amount_cents > 0",
        name="ck_world_cost_positive",
    ),
    CheckConstraint(
        "seller_repliker_id <> provider_repliker_id",
        name="ck_world_cost_parties",
    ),
)


def _positive_int(value, name):
    if type(value) is not int or value <= 0:
        raise WorldCostError(name + " invalido.")
    return value


def _wallet(db, repliker_id):
    agent = db.get(Repliker, repliker_id)

    if agent is None or not agent.is_active:
        raise WorldCostError(
            "Repliker inexistente o inactivo."
        )

    account = db.scalar(
        select(LedgerAccount).where(
            LedgerAccount.kind == "repliker_available",
            LedgerAccount.repliker_id == repliker_id,
            LedgerAccount.currency == "RCR",
            LedgerAccount.is_active.is_(True),
        )
    )

    if account is None:
        raise WorldCostError(
            "Billetera RCR inexistente o inactiva."
        )

    return account


def record_contract_expense(
    db: Session,
    *,
    contract_id: int,
    acting_repliker_id: int,
    provider_repliker_id: int,
    amount_cents: int,
    expense_key: str,
    note: str,
) -> dict:
    """Transferir un costo a un proveedor Repliker.

    El desembolso debe estar dentro del presupuesto
    estimado que se registro en el contrato.

    Se utiliza una llave contable determinista y
    una restriccion unica para evitar repeticiones.

    No se permiten gastos a la propia billetera
    ni al comprador del mismo contrato.
    """

    ensure_simulation_mode()

    _positive_int(contract_id, "Contrato")
    _positive_int(acting_repliker_id, "Actor")
    _positive_int(provider_repliker_id, "Proveedor")
    _positive_int(amount_cents, "Importe")

    if (
        not isinstance(expense_key, str)
        or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9:_-]{7,47}",
            expense_key,
        )
    ):
        raise WorldCostError(
            "Identificador de gasto invalido."
        )

    if (
        not isinstance(note, str)
        or not 8 <= len(note.strip()) <= 240
    ):
        raise WorldCostError(
            "Descripcion de gasto invalida."
        )

    try:
        contract = get_contract(db, contract_id)
    except ContractError as exc:
        raise WorldCostError('Contrato no encontrado o invalido.') from exc

    seller_id = contract["seller_repliker_id"]
    buyer_id = contract["buyer_repliker_id"]

    if acting_repliker_id != seller_id:
        raise WorldCostError(
            "Solo el vendedor puede solicitar "
            "gastos de su contrato."
        )

    if provider_repliker_id in (seller_id, buyer_id):
        raise WorldCostError(
            "El proveedor debe ser un tercero."
        )

    existing = db.execute(
        select(expenses).where(
            expenses.c.contract_id == contract_id,
            expenses.c.expense_key == expense_key,
        )
    ).mappings().first()

    if existing is not None:
        same = (
            existing["seller_repliker_id"] == seller_id
            and existing["provider_repliker_id"]
            == provider_repliker_id
            and existing["amount_cents"] == amount_cents
            and existing["note"] == note.strip()
        )

        if not same:
            raise WorldCostError(
                "La clave de gasto ya fue usada "
                "con datos diferentes."
            )

        transaction = db.get(
            LedgerTransaction,
            existing["ledger_transaction_id"],
        )

        if transaction is None:
            raise WorldCostError(
                "El gasto existente carece de "
                "transaccion contable."
            )

        return {
            "status": "verified",
            "expense_id": existing["id"],
            "transaction_id": transaction.id,
            "amount_cents": transaction.amount_cents,
            "repeated": True,
        }

    if contract["status"] not in (
        "open",
        "submitted",
        "approved",
    ):
        raise WorldCostError(
            "El estado del contrato no permite gastos."
        )

    seller_wallet = _wallet(db, seller_id)
    provider_wallet = _wallet(db, provider_repliker_id)

    planned_budget = contract["estimated_cost_cents"]

    used = db.scalar(
        select(func.coalesce(
            func.sum(expenses.c.amount_cents),
            0,
        ))
        .where(expenses.c.contract_id == contract_id)
    ) or 0

    if used + amount_cents > planned_budget:
        raise WorldCostError(
            "El gasto excede el presupuesto "
            "estimado del contrato."
        )

    ledger_key = (
        f"world:contract-cost:{contract_id}:{expense_key}"
    )

    try:
        with db.begin_nested():
            transaction = post_transfer(
                db=db,
                idempotency_key=ledger_key,
                transaction_type="world_agent_transfer",
                amount_cents=amount_cents,
                from_account_id=seller_wallet.id,
                to_account_id=provider_wallet.id,
                repliker_id=seller_id,
                external_reference=(
                    f"world-cost:{contract_id}:{expense_key}"
                ),
                description=note.strip(),
            )

            inserted = db.execute(
                insert(expenses).values(
                    contract_id=contract_id,
                    seller_repliker_id=seller_id,
                    provider_repliker_id=provider_repliker_id,
                    ledger_transaction_id=transaction.id,
                    expense_key=expense_key,
                    amount_cents=amount_cents,
                    note=note.strip(),
                )
            )

            expense_id = inserted.inserted_primary_key[0]

    except EconomyError as exc:
        raise WorldCostError(
            "Transferencia de costo rechazada: "
            + str(exc)
        ) from exc

    return {
        "status": "verified",
        "expense_id": expense_id,
        "transaction_id": transaction.id,
        "amount_cents": amount_cents,
        "repeated": False,
    }


def get_strategy_cashflow(
    db: Session,
    *,
    repliker_id: int | None = None,
) -> dict:
    """Calcular ingresos menos costos directos verificados.

    No declara ganancias netas definitivas.
    Solo clasifica contratos con procedencia registrada.
    """

    ensure_simulation_mode()

    report = get_strategy_comparison(
        db,
        repliker_id=repliker_id,
    )

    for group in report["groups"].values():
        group["verified_direct_expenses_cents"] = 0
        group["net_tracked_cashflow_cents"] = 0
        group["realized_net_profit_cents"] = None

    statement = (
        select(
            adoptions.c.origin,
            adoptions.c.repliker_id,
            contracts.c.id.label("contract_id"),
            expenses.c.seller_repliker_id,
            expenses.c.provider_repliker_id,
            expenses.c.amount_cents,
            expenses.c.ledger_transaction_id,
        )
        .select_from(expenses)
        .join(
            contracts,
            contracts.c.id == expenses.c.contract_id,
        )
        .join(
            negotiations,
            negotiations.c.id == contracts.c.negotiation_id,
        )
        .join(
            adoptions,
            adoptions.c.negotiation_id == negotiations.c.id,
        )
    )

    if repliker_id is not None:
        statement = statement.where(
            adoptions.c.repliker_id == repliker_id
        )

    rows = db.execute(statement).all()

    for row in rows:
        if row.origin not in report["groups"]:
            raise WorldCostError(
                "Origen de estrategia invalido."
            )

        if row.repliker_id != row.seller_repliker_id:
            raise WorldCostError(
                "Gasto atribuido a un agente incorrecto."
            )

        transaction = db.get(
            LedgerTransaction,
            row.ledger_transaction_id,
        )

        if transaction is None:
            raise WorldCostError(
                "No existe el movimiento del gasto."
            )

        source_account = _wallet(
            db, row.seller_repliker_id
        )
        provider_account = _wallet(
            db, row.provider_repliker_id
        )

        if not (
            transaction.from_account_id == source_account.id
            and transaction.to_account_id == provider_account.id
            and transaction.amount_cents == row.amount_cents
            and transaction.currency == "RCR"
            and transaction.transaction_type
                == "world_agent_transfer"
        ):
            raise WorldCostError(
                "Gasto sin respaldo contable consistente."
            )

        report["groups"][row.origin][
            "verified_direct_expenses_cents"
        ] += row.amount_cents

    for group in report["groups"].values():
        group["net_tracked_cashflow_cents"] = (
            group["verified_receipts_cents"]
            - group["verified_direct_expenses_cents"]
        )

    report["total_verified_direct_expenses_cents"] = sum(
        group["verified_direct_expenses_cents"]
        for group in report["groups"].values()
    )

    report["net_profit_fully_verified"] = False

    report["cost_evidence_warning"] = (
        "Solo se incluyen gastos vinculados a transferencias "
        "contables y negociaciones con estrategia clasificada. "
        "Pueden existir otros costos, impuestos, recursos "
        "o compromisos no registrados. El flujo calculado "
        "no equivale a beneficio neto definitivo."
    )

    return report
