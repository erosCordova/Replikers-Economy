"""Pruebas de liquidaciones contractuales simuladas."""

import hashlib
import os
import sqlite3
import uuid
from pathlib import Path

import pytest
from sqlalchemy import (
    create_engine,
    event,
    func,
    select,
)
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.agentic.world_negotiation_graph import (
    build_world_negotiation_graph,
)
from app.models.economy import (
    LedgerAccount,
    LedgerTransaction,
)
from app.services.economy_service import (
    account_balance,
    post_transfer,
)
from app.services.world_contract_service import (
    open_contract,
    review_delivery,
    submit_delivery,
)
from app.services.world_settlement_service import (
    SettlementError,
    settle_approved_contract,
    settlements,
)


ARTIFACT = b"replikers-world-entrega-verificada-v1"
DIGEST = hashlib.sha256(ARTIFACT).hexdigest()
REFERENCE = "artifact:sha256:" + DIGEST


@pytest.fixture
def db(tmp_path):
    source = Path(os.environ["REPLIKERS_WORLD_TEST_DB"])
    destination = tmp_path / "world_settlement_test.db"

    with sqlite3.connect(
        source.resolve().as_uri() + "?mode=ro",
        uri=True,
    ) as origin:
        with sqlite3.connect(str(destination)) as copy:
            origin.backup(copy)

    engine = create_engine(
        URL.create(
            "sqlite+pysqlite",
            database=str(destination),
        ),
        connect_args={"timeout": 15},
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    with Session(engine) as session:
        yield session
        session.rollback()

    engine.dispose()


def trusted_reader(reference):
    if reference != REFERENCE:
        raise ValueError("Artefacto desconocido.")
    return ARTIFACT


def create_contract(
    db,
    *,
    accepted=True,
    delivery=True,
    approval="approve",
    reference=REFERENCE,
):
    graph = build_world_negotiation_graph(
        db=db,
        response_engine=lambda context: {
            "decision": (
                "accept" if accepted else "reject"
            ),
            "message": (
                "Acepto las condiciones propuestas."
                if accepted
                else "Rechazo esta propuesta."
            ),
        },
    )

    negotiation = graph.invoke({
        "idempotency_key": (
            "world-settlement-" + uuid.uuid4().hex
        ),
        "proposal": {
            "proposer_repliker_id": 1,
            "target_repliker_id": 2,
            "title": "Servicio digital verificable",
            "description": (
                "Desarrollar un artefacto digital "
                "de prueba para el comprador."
            ),
            "currency": "RCR",
            "price_cents": 5000,
            "estimated_cost_cents": 1000,
        },
    })

    if not accepted:
        return None

    contract = open_contract(
        db,
        negotiation_id=negotiation["negotiation_id"],
        acting_repliker_id=1,
    )

    if delivery:
        contract = submit_delivery(
            db,
            contract_id=contract["id"],
            acting_repliker_id=1,
            reference=reference,
        )

    if delivery and approval is not None:
        contract = review_delivery(
            db,
            contract_id=contract["id"],
            acting_repliker_id=2,
            decision=approval,
            note=(
                "Entrega revisada por el comprador."
            ),
        )

    return contract["id"]


def pay(db, contract_id, reader=trusted_reader):
    return settle_approved_contract(
        db,
        contract_id=contract_id,
        trusted_artifact_reader=reader,
    )


def wallet(db, repliker_id):
    return db.scalar(
        select(LedgerAccount).where(
            LedgerAccount.kind == "repliker_available",
            LedgerAccount.currency == "RCR",
            LedgerAccount.repliker_id == repliker_id,
        )
    )


def tx_count(db):
    return db.scalar(
        select(func.count(LedgerTransaction.id))
    )


def test_01_approved_contract_can_be_paid(db):
    contract_id = create_contract(db)
    result = pay(db, contract_id)

    assert result["status"] == "settled"
    assert result["amount_cents"] == 5000
    assert result["currency"] == "RCR"
    assert result["repeated"] is False
    assert tx_count(db) == 9


def test_02_balances_are_updated_correctly(db):
    seller = wallet(db, 1)
    buyer = wallet(db, 2)

    seller_before = account_balance(
        db=db, account_id=seller.id
    )
    buyer_before = account_balance(
        db=db, account_id=buyer.id
    )

    contract_id = create_contract(db)
    pay(db, contract_id)

    assert account_balance(
        db=db, account_id=seller.id
    ) == seller_before + 5000

    assert account_balance(
        db=db, account_id=buyer.id
    ) == buyer_before - 5000


def test_03_payment_is_idempotent(db):
    contract_id = create_contract(db)

    first = pay(db, contract_id)
    second = pay(
        db,
        contract_id,
        reader=lambda reference: (
            (_ for _ in ()).throw(
                RuntimeError("No debe volver a verificarse")
            )
        ),
    )

    assert first["transaction_id"] == second["transaction_id"]
    assert second["repeated"] is True
    assert tx_count(db) == 9

    count = db.scalar(
        select(func.count())
        .select_from(settlements)
    )
    assert count == 1


def test_04_open_contract_cannot_be_paid(db):
    contract_id = create_contract(
        db, delivery=False
    )

    with pytest.raises(SettlementError):
        pay(db, contract_id)

    assert tx_count(db) == 8


def test_05_unreviewed_delivery_cannot_be_paid(db):
    contract_id = create_contract(
        db, approval=None
    )

    with pytest.raises(SettlementError):
        pay(db, contract_id)

    assert tx_count(db) == 8


def test_06_disputed_delivery_cannot_be_paid(db):
    contract_id = create_contract(
        db, approval="dispute"
    )

    with pytest.raises(SettlementError):
        pay(db, contract_id)

    assert tx_count(db) == 8


def test_07_tampered_artifact_is_rejected(db):
    contract_id = create_contract(db)

    with pytest.raises(SettlementError):
        pay(
            db,
            contract_id,
            reader=lambda reference: b"archivo-modificado",
        )

    assert tx_count(db) == 8


def test_08_invalid_artifact_reference(db):
    contract_id = create_contract(
        db,
        reference="artifact:referencia-sin-hash",
    )

    with pytest.raises(SettlementError):
        pay(db, contract_id)

    assert tx_count(db) == 8


def test_09_missing_trusted_reader(db):
    contract_id = create_contract(db)

    with pytest.raises(SettlementError):
        pay(db, contract_id, reader=None)

    assert tx_count(db) == 8


def test_10_insufficient_funds_at_payment(db):
    contract_id = create_contract(db)

    buyer = wallet(db, 2)
    third = wallet(db, 3)

    balance = account_balance(
        db=db,
        account_id=buyer.id,
    )

    post_transfer(
        db=db,
        idempotency_key=(
            "world-test-drain-" + uuid.uuid4().hex
        ),
        transaction_type="world_agent_transfer",
        amount_cents=balance,
        from_account_id=buyer.id,
        to_account_id=third.id,
        description="Prueba de saldo insuficiente.",
    )

    before = tx_count(db)

    with pytest.raises(SettlementError):
        pay(db, contract_id)

    assert tx_count(db) == before

    count = db.scalar(
        select(func.count()).select_from(settlements)
    )
    assert count == 0


def test_11_contract_terms_are_immutable(db):
    contract_id = create_contract(db)
    result = pay(db, contract_id)

    transaction = db.get(
        LedgerTransaction,
        result["transaction_id"],
    )

    assert transaction.amount_cents == 5000
    assert transaction.transaction_type == (
        "world_agent_transfer"
    )
    assert transaction.external_reference == (
        f"world-contract:{contract_id}"
    )


def test_12_settlement_has_audit_record(db):
    contract_id = create_contract(db)
    result = pay(db, contract_id)

    record = db.execute(
        select(settlements).where(
            settlements.c.contract_id == contract_id
        )
    ).mappings().one()

    assert record["ledger_transaction_id"] == (
        result["transaction_id"]
    )
    assert record["artifact_sha256"] == DIGEST

    db.commit()

    transaction = db.get(
        LedgerTransaction,
        result["transaction_id"],
    )

    assert transaction is not None
    assert tx_count(db) == 9
