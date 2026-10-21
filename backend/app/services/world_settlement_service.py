"""Liquidacion contractual simulada de Replikers World.

Requisitos:
- Contrato aprobado por el comprador.
- Artefacto disponible mediante un lector confiable.
- SHA-256 coincidente con la referencia de entrega.
- Billeteras RCR activas y fondos suficientes.
- Pago unico por contrato.

No verifica calidad semantica del trabajo.
No permite pagos reales.
No debe exponerse directamente a agentes o clientes.
"""

import hashlib
import re
from typing import Callable

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    func,
    insert,
    select,
)
from sqlalchemy.orm import Session

from app.models.economy import LedgerAccount, LedgerTransaction
from app.services.economy_service import (
    EconomyError,
    ensure_simulation_mode,
    post_transfer,
)
from app.services.world_contract_service import get_contract


class SettlementError(ValueError):
    pass


metadata = MetaData()

settlements = Table(
    "world_contract_settlements",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "contract_id",
        Integer,
        nullable=False,
        unique=True,
    ),
    Column(
        "ledger_transaction_id",
        Integer,
        nullable=False,
        unique=True,
    ),
    Column(
        "artifact_sha256",
        String(64),
        nullable=False,
    ),
    Column(
        "created_at",
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    ),
)


def settle_approved_contract(
    db: Session,
    *,
    contract_id: int,
    trusted_artifact_reader: Callable[[str], bytes],
) -> dict:
    """Liquidar un contrato aprobado en moneda RCR.

    trusted_artifact_reader debe ser una herramienta
    controlada por el backend, nunca por el modelo IA.

    El llamante es responsable de ejecutar db.commit().
    """

    ensure_simulation_mode()

    if type(contract_id) is not int or contract_id <= 0:
        raise SettlementError("Contrato invalido.")

    existing = db.execute(
        select(settlements).where(
            settlements.c.contract_id == contract_id
        )
    ).mappings().first()

    if existing is not None:
        transaction = db.get(
            LedgerTransaction,
            existing["ledger_transaction_id"],
        )

        if transaction is None:
            raise SettlementError(
                "La liquidacion existente no tiene "
                "una transaccion valida."
            )

        return {
            "status": "settled",
            "settlement_id": existing["id"],
            "transaction_id": transaction.id,
            "amount_cents": transaction.amount_cents,
            "currency": transaction.currency,
            "repeated": True,
        }

    contract = get_contract(db, contract_id)

    if contract["status"] != "approved":
        raise SettlementError(
            "El comprador todavia no ha aprobado "
            "la entrega."
        )

    if contract["currency"] != "RCR":
        raise SettlementError(
            "Solo se admiten creditos ficticios RCR."
        )

    reference = contract["delivery_reference"]

    if not isinstance(reference, str):
        raise SettlementError(
            "El contrato no tiene una entrega valida."
        )

    matched = re.fullmatch(
        r"artifact:sha256:([0-9a-f]{64})",
        reference,
    )

    if matched is None:
        raise SettlementError(
            "La entrega requiere una referencia SHA-256."
        )

    if not callable(trusted_artifact_reader):
        raise SettlementError(
            "No existe un verificador de artefactos confiable."
        )

    try:
        artifact = trusted_artifact_reader(reference)
    except Exception as exc:
        raise SettlementError(
            "No fue posible verificar el artefacto."
        ) from exc

    if (
        not isinstance(artifact, bytes)
        or not 0 < len(artifact) <= 2_000_000
    ):
        raise SettlementError(
            "El artefacto no es valido o excede "
            "el limite permitido."
        )

    digest = hashlib.sha256(artifact).hexdigest()

    if digest != matched.group(1):
        raise SettlementError(
            "El contenido entregado no coincide "
            "con su huella SHA-256."
        )

    seller_id = contract["seller_repliker_id"]
    buyer_id = contract["buyer_repliker_id"]

    if seller_id == buyer_id:
        raise SettlementError(
            "No se permiten pagos al mismo agente."
        )

    wallets = {}

    for repliker_id in (seller_id, buyer_id):
        account = db.scalar(
            select(LedgerAccount).where(
                LedgerAccount.repliker_id == repliker_id,
                LedgerAccount.kind == "repliker_available",
                LedgerAccount.currency == "RCR",
                LedgerAccount.is_active.is_(True),
            )
        )

        if account is None:
            raise SettlementError(
                "Una de las billeteras no esta disponible."
            )

        wallets[repliker_id] = account

    price = contract["price_cents"]

    if type(price) is not int or price <= 0:
        raise SettlementError(
            "El precio contractual es invalido."
        )

    key = f"world:contract:{contract_id}:settlement:v1"

    try:
        # Ambos registros deben confirmarse conjuntamente.
        with db.begin_nested():
            transaction = post_transfer(
                db=db,
                idempotency_key=key,
                transaction_type="world_agent_transfer",
                amount_cents=price,
                from_account_id=wallets[buyer_id].id,
                to_account_id=wallets[seller_id].id,
                repliker_id=seller_id,
                external_reference=(
                    f"world-contract:{contract_id}"
                ),
                description=(
                    "Pago simulado por contrato aprobado "
                    "con integridad de artefacto verificada"
                ),
            )

            result = db.execute(
                insert(settlements).values(
                    contract_id=contract_id,
                    ledger_transaction_id=transaction.id,
                    artifact_sha256=digest,
                )
            )

            settlement_id = result.inserted_primary_key[0]

    except EconomyError as exc:
        raise SettlementError(
            "El pago no fue autorizado por el ledger: "
            + str(exc)
        ) from exc

    return {
        "status": "settled",
        "settlement_id": settlement_id,
        "transaction_id": transaction.id,
        "amount_cents": price,
        "currency": "RCR",
        "repeated": False,
    }
