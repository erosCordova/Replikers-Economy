
"""Pruebas de gastos simultaneos con SQLite."""

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.pool import NullPool

from app.services.world_atomic_cost_service import (
    AtomicCostError,
    record_serialized_expense,
)
from app.services.world_cost_service import WorldCostError


@pytest.fixture
def prepared(tmp_path):
    source = Path(
        os.environ["REPLIKERS_WORLD_ATOMIC_TEST_DB"]
    )

    target = tmp_path / "concurrent_costs.db"

    with sqlite3.connect(
        source.resolve().as_uri() + "?mode=ro",
        uri=True,
    ) as original:
        with sqlite3.connect(str(target)) as destination:
            original.backup(destination)

    engine = create_engine(
        URL.create(
            "sqlite+pysqlite",
            database=str(target),
        ),
        connect_args={
            "timeout": 25,
            "check_same_thread": False,
        },
        poolclass=NullPool,
    )

    @event.listens_for(engine, "connect")
    def enable_fk(connection, record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    with engine.connect() as con:
        contract_id = con.exec_driver_sql(
            """
            SELECT contract_id
            FROM world_contract_expenses
            ORDER BY id
            LIMIT 1
            """
        ).scalar_one()

    yield engine, target, contract_id
    engine.dispose()


def counts(engine):
    with engine.connect() as con:
        tx = con.exec_driver_sql(
            "SELECT COUNT(*) FROM ledger_transactions"
        ).scalar_one()

        expenses = con.exec_driver_sql(
            "SELECT COUNT(*) FROM world_contract_expenses"
        ).scalar_one()

    return tx, expenses


def pay(
    prepared,
    *,
    key="recurso-digital-001",
    amount=500,
    actor=1,
    provider=3,
    contract_id=None,
):
    engine, _, default_contract = prepared

    return record_serialized_expense(
        engine,
        contract_id=(
            contract_id
            if contract_id is not None
            else default_contract
        ),
        acting_repliker_id=actor,
        provider_repliker_id=provider,
        amount_cents=amount,
        expense_key=key,
        note="Pago ficticio a proveedor digital.",
    )


def balances(path):
    """Obtener saldos mediante el ledger oficial."""

    from sqlalchemy import create_engine, select
    from sqlalchemy.engine import URL
    from sqlalchemy.orm import Session

    from app.models.economy import LedgerAccount
    from app.services.economy_service import account_balance

    engine = create_engine(
        URL.create(
            "sqlite+pysqlite",
            database=str(path),
        ),
        connect_args={"timeout": 20},
    )

    try:
        with Session(engine) as db:
            accounts = db.scalars(
                select(LedgerAccount)
                .where(
                    LedgerAccount.kind == "repliker_available",
                    LedgerAccount.currency == "RCR",
                )
                .order_by(LedgerAccount.repliker_id)
            ).all()

            result = {}

            for account in accounts:
                if account.repliker_id is None:
                    continue

                result[int(account.repliker_id)] = int(
                    account_balance(
                        db=db,
                        account_id=account.id,
                    )
                )

            return result

    finally:
        engine.dispose()


def parallel_attempts(prepared, count=8):
    with ThreadPoolExecutor(
        max_workers=count
    ) as pool:

        jobs = [
            pool.submit(
                pay,
                prepared,
                key=f"simultaneous-{index:04d}",
                amount=100,
            )
            for index in range(count)
        ]

        successes = []
        rejected = []

        for job in jobs:
            try:
                successes.append(
                    job.result(timeout=60)
                )
            except WorldCostError as exc:
                rejected.append(type(exc).__name__)

    return successes, rejected


def test_01_baseline_has_verified_cost(prepared):
    assert counts(prepared[0]) == (10, 1)


def test_02_existing_key_is_idempotent(prepared):
    response = pay(prepared)

    assert response["repeated"] is True
    assert counts(prepared[0]) == (10, 1)


def test_03_modified_replay_is_rejected(prepared):
    with pytest.raises(WorldCostError):
        pay(prepared, amount=100)

    assert counts(prepared[0]) == (10, 1)


def test_04_parallel_replay_never_duplicates(prepared):
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = [
            pool.submit(pay, prepared)
            for _ in range(8)
        ]

        results = [
            job.result(timeout=60)
            for job in jobs
        ]

    assert len(results) == 8
    assert all(item["repeated"] for item in results)
    assert counts(prepared[0]) == (10, 1)


def test_05_only_one_parallel_cost_fits_budget(prepared):
    successes, rejected = parallel_attempts(
        prepared,
        count=8,
    )

    assert len(successes) == 1
    assert len(rejected) == 7
    assert counts(prepared[0]) == (11, 2)


def test_06_rejected_cost_has_no_partial_write(prepared):
    with pytest.raises(WorldCostError):
        pay(
            prepared,
            key="excess-budget-0001",
            amount=101,
        )

    assert counts(prepared[0]) == (10, 1)


def test_07_buyer_cannot_impose_seller_cost(prepared):
    with pytest.raises(WorldCostError):
        pay(
            prepared,
            actor=2,
            key="unauthorized-0001",
            amount=100,
        )

    assert counts(prepared[0]) == (10, 1)


def test_08_self_payment_is_rejected(prepared):
    with pytest.raises(WorldCostError):
        pay(
            prepared,
            provider=1,
            key="self-payment-0001",
            amount=100,
        )


def test_09_missing_contract_is_rejected(prepared):
    with pytest.raises(WorldCostError):
        pay(
            prepared,
            contract_id=999999999,
        )

    assert counts(prepared[0]) == (10, 1)


def test_10_new_cost_changes_only_two_wallets(prepared):
    original = balances(prepared[1])

    result = pay(
        prepared,
        key="wallet-impact-0001",
        amount=100,
    )

    current = balances(prepared[1])

    assert result["repeated"] is False
    assert current[1] - original[1] == -100
    assert current[2] - original[2] == 0
    assert current[3] - original[3] == 100


def test_11_replaying_new_cost_changes_nothing(prepared):
    first = pay(
        prepared,
        key="new-idempotency-0001",
        amount=100,
    )

    second = pay(
        prepared,
        key="new-idempotency-0001",
        amount=100,
    )

    assert first["transaction_id"] == second["transaction_id"]
    assert second["repeated"] is True
    assert counts(prepared[0]) == (11, 2)


def test_12_budget_cannot_be_exceeded_after_payment(prepared):
    pay(
        prepared,
        key="budget-consumed-0001",
        amount=100,
    )

    with pytest.raises(WorldCostError):
        pay(
            prepared,
            key="budget-consumed-0002",
            amount=1,
        )

    assert counts(prepared[0]) == (11, 2)


def test_13_in_memory_database_is_not_supported():
    engine = create_engine("sqlite:///:memory:")

    try:
        with pytest.raises(AtomicCostError):
            record_serialized_expense(
                engine,
                contract_id=1,
                acting_repliker_id=1,
                provider_repliker_id=3,
                amount_cents=100,
                expense_key="invalid-memory-0001",
                note="Prueba de motor incompatible.",
            )
    finally:
        engine.dispose()


def test_14_invalid_timeout_is_rejected(prepared):
    for timeout in (0, -1, True, 61):
        with pytest.raises(AtomicCostError):
            record_serialized_expense(
                prepared[0],
                contract_id=prepared[2],
                acting_repliker_id=1,
                provider_repliker_id=3,
                amount_cents=100,
                expense_key="timeout-invalid-0001",
                note="Prueba de tiempo invalido.",
                timeout_seconds=timeout,
            )


def test_15_parallel_rejections_preserve_integrity(prepared):
    parallel_attempts(prepared, count=8)

    with sqlite3.connect(
        prepared[1].resolve().as_uri() + "?mode=ro",
        uri=True,
    ) as con:

        integrity = con.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        foreign_keys = con.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

    assert integrity == "ok"
    assert foreign_keys == []
