from __future__ import annotations

import unittest

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401

from app.api.routes.economy import (
    router as economy_router,
)
from app.database.base import Base
from app.models.economy import (
    LedgerAccount,
    LedgerTransaction,
)
from app.models.project import Project
from app.models.user import User
from app.services.economy_service import (
    EconomyError,
    account_balance,
    build_project_economy_snapshot,
    build_user_wallet_snapshot,
    ensure_platform_revenue_account,
    ensure_project_custody_account,
    ensure_system_clearing_account,
    ensure_user_wallet_accounts,
    list_project_ledger,
    list_user_ledger,
    post_transfer,
)


class Phase10ALedgerTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={
                "check_same_thread":
                    False,
            },
            poolclass=StaticPool,
        )

        cls.Session = sessionmaker(
            bind=cls.engine,
            autocommit=False,
            autoflush=False,
        )

        Base.metadata.create_all(
            bind=cls.engine
        )

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(
            bind=cls.engine
        )

        cls.engine.dispose()

    def setUp(self):
        self.db = self.Session()

        self.user = User(
            full_name="Ledger User",
            email=(
                "ledger-user-"
                f"{self._testMethodName}"
                "@example.test"
            ),
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.db.add(
            self.user
        )

        self.db.flush()

        self.project = Project(
            client_id=
                self.user.id,
            title="Ledger Project",
            description=(
                "Proyecto economico "
                "de prueba."
            ),
            currency="PEN",
            budget_limit_cents=
                20_000,
            quoted_amount_cents=
                10_000,
            payment_status="unpaid",
        )

        self.db.add(
            self.project
        )

        self.db.flush()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def bootstrap_accounts(self):
        clearing = (
            ensure_system_clearing_account(
                db=self.db,
                currency="PEN",
            )
        )

        custody = (
            ensure_project_custody_account(
                db=self.db,
                project_id=
                    self.project.id,
            )
        )

        available, pending = (
            ensure_user_wallet_accounts(
                db=self.db,
                user_id=
                    self.user.id,
                currency="PEN",
            )
        )

        platform = (
            ensure_platform_revenue_account(
                db=self.db,
                currency="PEN",
            )
        )

        return (
            clearing,
            custody,
            available,
            pending,
            platform,
        )

    def test_account_creation_is_idempotent(
        self,
    ):
        first = (
            ensure_project_custody_account(
                db=self.db,
                project_id=
                    self.project.id,
            )
        )

        second = (
            ensure_project_custody_account(
                db=self.db,
                project_id=
                    self.project.id,
            )
        )

        self.assertEqual(
            first.id,
            second.id,
        )

        self.assertEqual(
            first.account_key,
            (
                f"project:"
                f"{self.project.id}:"
                "custody:PEN"
            ),
        )

    def test_double_entry_balances(
        self,
    ):
        (
            clearing,
            custody,
            available,
            pending,
            platform,
        ) = self.bootstrap_accounts()

        post_transfer(
            db=self.db,
            idempotency_key=
                "test-funding-1",
            transaction_type=
                "funding",
            amount_cents=10_000,
            from_account_id=
                clearing.id,
            to_account_id=
                custody.id,
            project_id=
                self.project.id,
        )

        post_transfer(
            db=self.db,
            idempotency_key=
                "test-earning-1",
            transaction_type=
                "earning",
            amount_cents=7_000,
            from_account_id=
                custody.id,
            to_account_id=
                pending.id,
            project_id=
                self.project.id,
        )

        post_transfer(
            db=self.db,
            idempotency_key=
                "test-commission-1",
            transaction_type=
                "commission",
            amount_cents=1_000,
            from_account_id=
                custody.id,
            to_account_id=
                platform.id,
            project_id=
                self.project.id,
        )

        self.assertEqual(
            account_balance(
                db=self.db,
                account_id=
                    clearing.id,
            ),
            -10_000,
        )

        self.assertEqual(
            account_balance(
                db=self.db,
                account_id=
                    custody.id,
            ),
            2_000,
        )

        self.assertEqual(
            account_balance(
                db=self.db,
                account_id=
                    pending.id,
            ),
            7_000,
        )

        self.assertEqual(
            account_balance(
                db=self.db,
                account_id=
                    available.id,
            ),
            0,
        )

        self.assertEqual(
            account_balance(
                db=self.db,
                account_id=
                    platform.id,
            ),
            1_000,
        )

        total = sum(
            account_balance(
                db=self.db,
                account_id=
                    account.id,
            )
            for account in [
                clearing,
                custody,
                available,
                pending,
                platform,
            ]
        )

        self.assertEqual(
            total,
            0,
        )

    def test_transfer_idempotency(
        self,
    ):
        (
            clearing,
            custody,
            _,
            _,
            _,
        ) = self.bootstrap_accounts()

        first = post_transfer(
            db=self.db,
            idempotency_key=
                "idempotent-funding",
            transaction_type=
                "funding",
            amount_cents=5_000,
            from_account_id=
                clearing.id,
            to_account_id=
                custody.id,
            project_id=
                self.project.id,
        )

        second = post_transfer(
            db=self.db,
            idempotency_key=
                "idempotent-funding",
            transaction_type=
                "funding",
            amount_cents=5_000,
            from_account_id=
                clearing.id,
            to_account_id=
                custody.id,
            project_id=
                self.project.id,
        )

        self.assertEqual(
            first.id,
            second.id,
        )

        transactions = (
            list_project_ledger(
                db=self.db,
                project_id=
                    self.project.id,
            )
        )

        self.assertEqual(
            len(transactions),
            1,
        )

    def test_idempotency_conflict_rejected(
        self,
    ):
        (
            clearing,
            custody,
            _,
            _,
            _,
        ) = self.bootstrap_accounts()

        post_transfer(
            db=self.db,
            idempotency_key=
                "conflicting-key",
            transaction_type=
                "funding",
            amount_cents=5_000,
            from_account_id=
                clearing.id,
            to_account_id=
                custody.id,
            project_id=
                self.project.id,
        )

        with self.assertRaises(
            EconomyError
        ):
            post_transfer(
                db=self.db,
                idempotency_key=
                    "conflicting-key",
                transaction_type=
                    "funding",
                amount_cents=4_999,
                from_account_id=
                    clearing.id,
                to_account_id=
                    custody.id,
                project_id=
                    self.project.id,
            )

    def test_overdraft_rejected(
        self,
    ):
        (
            _,
            custody,
            _,
            pending,
            _,
        ) = self.bootstrap_accounts()

        with self.assertRaises(
            EconomyError
        ):
            post_transfer(
                db=self.db,
                idempotency_key=
                    "invalid-overdraft",
                transaction_type=
                    "earning",
                amount_cents=1,
                from_account_id=
                    custody.id,
                to_account_id=
                    pending.id,
                project_id=
                    self.project.id,
            )

    def test_wallet_snapshot(
        self,
    ):
        (
            clearing,
            _,
            available,
            pending,
            _,
        ) = self.bootstrap_accounts()

        post_transfer(
            db=self.db,
            idempotency_key=
                "wallet-available",
            transaction_type=
                "adjustment",
            amount_cents=3_000,
            from_account_id=
                clearing.id,
            to_account_id=
                available.id,
        )

        post_transfer(
            db=self.db,
            idempotency_key=
                "wallet-pending",
            transaction_type=
                "adjustment",
            amount_cents=2_000,
            from_account_id=
                clearing.id,
            to_account_id=
                pending.id,
        )

        snapshot = (
            build_user_wallet_snapshot(
                db=self.db,
                user_id=
                    self.user.id,
                currency="PEN",
            )
        )

        self.assertEqual(
            snapshot.available_cents,
            3_000,
        )

        self.assertEqual(
            snapshot.pending_cents,
            2_000,
        )

        self.assertEqual(
            snapshot.total_cents,
            5_000,
        )

        rows = list_user_ledger(
            db=self.db,
            user_id=
                self.user.id,
            currency="PEN",
        )

        self.assertEqual(
            len(rows),
            2,
        )

    def test_project_snapshot(
        self,
    ):
        (
            clearing,
            custody,
            _,
            _,
            _,
        ) = self.bootstrap_accounts()

        post_transfer(
            db=self.db,
            idempotency_key=
                "snapshot-funding",
            transaction_type=
                "funding",
            amount_cents=8_000,
            from_account_id=
                clearing.id,
            to_account_id=
                custody.id,
            project_id=
                self.project.id,
        )

        state = (
            build_project_economy_snapshot(
                db=self.db,
                project_id=
                    self.project.id,
            )
        )

        self.assertEqual(
            state.custody_balance_cents,
            8_000,
        )

        self.assertEqual(
            state.contract_reserved_cents,
            0,
        )

        self.assertEqual(
            state.unallocated_cents,
            8_000,
        )

    def test_model_tables_exist(
        self,
    ):
        self.assertIn(
            "ledger_accounts",
            Base.metadata.tables,
        )

        self.assertIn(
            "ledger_transactions",
            Base.metadata.tables,
        )

        self.assertIsNotNone(
            LedgerAccount
        )

        self.assertIsNotNone(
            LedgerTransaction
        )


class Phase10AApiTests(
    unittest.TestCase
):
    def test_routes_exist(
        self,
    ):
        api = FastAPI()

        api.include_router(
            economy_router,
            prefix="/api/v1",
        )

        paths = set(
            api.openapi()[
                "paths"
            ]
        )

        required = {
            "/api/v1/economy/me",
            "/api/v1/economy/me/ledger",
            (
                "/api/v1/economy/"
                "projects/{project_id}"
            ),
            (
                "/api/v1/economy/"
                "projects/{project_id}/ledger"
            ),
        }

        self.assertTrue(
            required.issubset(
                paths
            )
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
