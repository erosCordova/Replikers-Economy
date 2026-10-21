
"""Pruebas de costos contractuales verificables."""

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
    insert,
    select,
)
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.agentic.world_negotiation_graph import (
    build_world_negotiation_graph,
)
from app.agentic.world_social_learning import adoptions

from app.services.world_contract_service import (
    open_contract,
    submit_delivery,
    review_delivery,
)
from app.services.world_settlement_service import (
    settle_approved_contract,
)
from app.services.world_cost_service import (
    WorldCostError,
    expenses,
    record_contract_expense,
    get_strategy_cashflow,
)
from app.models.economy import LedgerTransaction


ARTIFACT = b"replikers-world-artifact-cost-verified"
DIGEST = hashlib.sha256(ARTIFACT).hexdigest()
REFERENCE = "artifact:sha256:" + DIGEST


@pytest.fixture
def db(tmp_path):
    source = Path(
        os.environ["REPLIKERS_WORLD_TEST_DB"]
    )
    target = tmp_path / "cost_test.db"

    with sqlite3.connect(
        source.resolve().as_uri() + "?mode=ro",
        uri=True,
    ) as origin:
        with sqlite3.connect(str(target)) as destination:
            origin.backup(destination)

    engine = create_engine(
        URL.create(
            "sqlite+pysqlite",
            database=str(target),
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


def new_contract(db, *, approved=False, planned=600):
    graph = build_world_negotiation_graph(
        db=db,
        response_engine=lambda context: {
            "decision": "accept",
            "message": "Acepto estas condiciones de prueba.",
        },
    )

    negotiation = graph.invoke({
        "idempotency_key": (
            "world-cost-test-" + uuid.uuid4().hex
        ),
        "proposal": {
            "proposer_repliker_id": 1,
            "target_repliker_id": 2,
            "title": "Servicio digital con proveedores",
            "description": (
                "Crear un informe digital para el "
                "comprador con ayuda de un proveedor."
            ),
            "currency": "RCR",
            "price_cents": 2500,
            "estimated_cost_cents": planned,
        },
    })

    assert negotiation["status"] == "accepted"

    contract = open_contract(
        db,
        negotiation_id=negotiation["negotiation_id"],
        acting_repliker_id=1,
    )

    if approved:
        submit_delivery(
            db,
            contract_id=contract["id"],
            acting_repliker_id=1,
            reference=REFERENCE,
        )

        review_delivery(
            db,
            contract_id=contract["id"],
            acting_repliker_id=2,
            decision="approve",
            note="Entrega revisada y aprobada.",
        )

    return contract, negotiation["negotiation_id"]


def cost(db, contract_id, amount=500, key="resource-0001"):
    return record_contract_expense(
        db,
        contract_id=contract_id,
        acting_repliker_id=1,
        provider_repliker_id=3,
        amount_cents=amount,
        expense_key=key,
        note="Proveedor digital del contrato",
    )


def tracked(db, negotiation_id):
    db.execute(
        insert(adoptions).values(
            negotiation_id=negotiation_id,
            repliker_id=1,
            source_ids_json="[]",
            origin="original",
        )
    )


def count(db, table):
    return db.scalar(
        select(func.count()).select_from(table)
    )


def test_01_cost_starts_at_zero(db):
    report = get_strategy_cashflow(db)
    assert report["total_verified_direct_expenses_cents"] == 0


def test_02_no_net_profit_is_invented(db):
    report = get_strategy_cashflow(db)

    assert report["net_profit_fully_verified"] is False

    for group in report["groups"].values():
        assert group["realized_net_profit_cents"] is None


def test_03_valid_expense_creates_ledger_transfer(db):
    contract, _ = new_contract(db)

    previous = count(db, LedgerTransaction.__table__)
    result = cost(db, contract["id"])

    assert result["status"] == "verified"
    assert result["amount_cents"] == 500
    assert count(db, LedgerTransaction.__table__) == previous + 1


def test_04_expense_is_idempotent(db):
    contract, _ = new_contract(db)

    first = cost(db, contract["id"])
    second = cost(db, contract["id"])

    assert first["transaction_id"] == second["transaction_id"]
    assert second["repeated"] is True
    assert count(db, expenses) == 1


def test_05_reused_key_cannot_change_amount(db):
    contract, _ = new_contract(db)
    cost(db, contract["id"], amount=100)

    with pytest.raises(WorldCostError):
        cost(db, contract["id"], amount=200)


def test_06_budget_excess_is_rejected(db):
    contract, _ = new_contract(db)

    with pytest.raises(WorldCostError):
        cost(db, contract["id"], amount=601)

    assert count(db, expenses) == 0


def test_07_multiple_expenses_respect_budget(db):
    contract, _ = new_contract(db)

    cost(db, contract["id"], amount=200, key="resource-0001")
    cost(db, contract["id"], amount=300, key="resource-0002")

    with pytest.raises(WorldCostError):
        cost(
            db,
            contract["id"],
            amount=200,
            key="resource-0003",
        )

    assert count(db, expenses) == 2


def test_08_buyer_cannot_request_seller_expense(db):
    contract, _ = new_contract(db)

    with pytest.raises(WorldCostError):
        record_contract_expense(
            db,
            contract_id=contract["id"],
            acting_repliker_id=2,
            provider_repliker_id=3,
            amount_cents=100,
            expense_key="resource-0001",
            note="Gasto no autorizado",
        )


def test_09_seller_cannot_pay_self(db):
    contract, _ = new_contract(db)

    with pytest.raises(WorldCostError):
        record_contract_expense(
            db,
            contract_id=contract["id"],
            acting_repliker_id=1,
            provider_repliker_id=1,
            amount_cents=100,
            expense_key="resource-0001",
            note="Transferencia a si mismo",
        )


def test_10_provider_cannot_be_buyer(db):
    contract, _ = new_contract(db)

    with pytest.raises(WorldCostError):
        record_contract_expense(
            db,
            contract_id=contract["id"],
            acting_repliker_id=1,
            provider_repliker_id=2,
            amount_cents=100,
            expense_key="resource-0001",
            note="Proveedor no independiente",
        )


def test_11_nonexistent_provider_is_rejected(db):
    contract, _ = new_contract(db)

    with pytest.raises(WorldCostError):
        record_contract_expense(
            db,
            contract_id=contract["id"],
            acting_repliker_id=1,
            provider_repliker_id=999999,
            amount_cents=100,
            expense_key="resource-0001",
            note="Proveedor inexistente",
        )


def test_12_invalid_amounts_are_rejected(db):
    contract, _ = new_contract(db)

    for amount in (-1, 0, True, "100", None):
        with pytest.raises(WorldCostError):
            cost(db, contract["id"], amount=amount)


def test_13_invalid_contract_is_rejected(db):
    with pytest.raises(WorldCostError):
        cost(db, 99999999)


def test_14_expenses_without_sale_are_not_profit(db):
    contract, negotiation_id = new_contract(db)

    tracked(db, negotiation_id)
    cost(db, contract["id"], amount=100)

    report = get_strategy_cashflow(
        db,
        repliker_id=1,
    )

    group = report["groups"]["original"]

    assert group["verified_receipts_cents"] == 0
    assert group["verified_direct_expenses_cents"] == 100
    assert group["net_tracked_cashflow_cents"] == -100
    assert group["realized_net_profit_cents"] is None


def test_15_settlement_less_verified_costs(db):
    contract, negotiation_id = new_contract(
        db,
        approved=True,
    )

    tracked(db, negotiation_id)

    cost(db, contract["id"], amount=500)

    payment = settle_approved_contract(
        db,
        contract_id=contract["id"],
        trusted_artifact_reader=lambda ref: ARTIFACT,
    )

    assert payment["status"] == "settled"

    report = get_strategy_cashflow(
        db,
        repliker_id=1,
    )

    group = report["groups"]["original"]

    assert group["verified_receipts_cents"] == 2500
    assert group["verified_direct_expenses_cents"] == 500
    assert group["net_tracked_cashflow_cents"] == 2000
    assert group["realized_net_profit_cents"] is None


def test_16_replayed_expense_does_not_duplicate_ledger(db):
    contract, _ = new_contract(db)

    first = cost(db, contract["id"])
    db.commit()

    before = count(db, LedgerTransaction.__table__)
    second = cost(db, contract["id"])

    assert first["transaction_id"] == second["transaction_id"]
    assert count(db, LedgerTransaction.__table__) == before


def test_17_unrelated_transfers_are_not_expenses(db):
    report = get_strategy_cashflow(db)

    assert count(db, LedgerTransaction.__table__) == 8
    assert report["total_verified_direct_expenses_cents"] == 0
