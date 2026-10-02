from __future__ import annotations

import unittest

from fastapi import FastAPI
from sqlalchemy import (
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import (
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401

from app.api.routes.economy import (
    router as economy_router,
)
from app.core.config import settings
from app.database.base import Base
from app.models.contract import (
    TaskContract,
)
from app.models.economy import (
    LedgerAccount,
    LedgerTransaction,
)
from app.models.project import Project
from app.models.repliker import Repliker
from app.models.task import (
    Task,
    TaskBid,
)
from app.models.user import User
from app.services.economy_service import (
    EconomyError,
    account_balance,
    build_user_wallet_snapshot,
    ensure_platform_revenue_account,
    ensure_project_custody_account,
    ensure_system_clearing_account,
    finalize_project_economy,
    settle_contract_earnings,
    simulate_project_funding,
    simulate_withdrawal,
)


class Phase10CSettlementTests(
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

        self.client = User(
            full_name="Cliente Simulado",
            email=(
                "client-"
                f"{self._testMethodName}"
                "@example.test"
            ),
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.owner = User(
            full_name="Owner Repliker",
            email=(
                "owner-"
                f"{self._testMethodName}"
                "@example.test"
            ),
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.db.add_all(
            [
                self.client,
                self.owner,
            ]
        )

        self.db.flush()

        self.repliker = Repliker(
            owner_id=self.owner.id,
            name="R10C",
            specialty="Backend",
            description=(
                "Repliker de prueba."
            ),
            status="available",
            reputation_score=50,
            base_price_credits=50,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=0,
            is_active=True,
        )

        self.db.add(
            self.repliker
        )

        self.db.flush()

        self.project = Project(
            client_id=self.client.id,
            title="Proyecto 10C",
            description=(
                "Prueba integral "
                "de economia simulada."
            ),
            status="contracted",
            currency="PEN",
            budget_limit_cents=
                10_000,
            quoted_amount_cents=
                10_000,
            payment_status="unpaid",
        )

        self.db.add(
            self.project
        )

        self.db.flush()

        self.task = Task(
            project_id=
                self.project.id,
            title="Tarea 10C",
            description=(
                "Tarea economica."
            ),
            status="completed",
            complexity=50,
            max_budget_cents=
                8_000,
        )

        self.db.add(
            self.task
        )

        self.db.flush()

        self.bid = TaskBid(
            task_id=self.task.id,
            repliker_id=
                self.repliker.id,
            amount_cents=8_000,
            confidence_score=90,
            estimated_minutes=60,
            message="Oferta prueba",
            status="selected",
        )

        self.db.add(
            self.bid
        )

        self.db.flush()

        self.contract = TaskContract(
            project_id=
                self.project.id,
            task_id=
                self.task.id,
            bid_id=
                self.bid.id,
            repliker_id=
                self.repliker.id,
            status="completed",
            currency="PEN",
            amount_cents=8_000,
            reserved_cents=8_000,
            skill_score=80,
            reputation_score=80,
            confidence_score=90,
            price_score=80,
            time_score=80,
            risk_score=80,
            selection_score=82,
            selected_by="r00",
            selection_policy_version=
                "test-v1",
            selection_summary=
                "Contrato de prueba.",
        )

        self.db.add(
            self.contract
        )

        self.db.flush()

        simulate_project_funding(
            db=self.db,
            project_id=
                self.project.id,
            idempotency_key=(
                "funding:"
                f"{self._testMethodName}"
            ),
            amount_cents=10_000,
            initiated_by_user_id=
                self.client.id,
        )

        self.db.flush()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_simulation_mode_only(
        self,
    ):
        self.assertEqual(
            settings.ECONOMY_MODE,
            "simulation",
        )

        self.assertFalse(
            settings
            .REAL_PAYMENTS_ENABLED
        )

        self.assertEqual(
            settings
            .PLATFORM_COMMISSION_BPS,
            1000,
        )

    def test_contract_settlement_90_10(
        self,
    ):
        result = (
            settle_contract_earnings(
                db=self.db,
                contract_id=
                    self.contract.id,
            )
        )

        self.assertEqual(
            result.gross_cents,
            8_000,
        )

        self.assertEqual(
            result.owner_net_cents,
            7_200,
        )

        self.assertEqual(
            result.commission_cents,
            800,
        )

        self.assertEqual(
            len(result.allocations),
            1,
        )

        wallet = (
            build_user_wallet_snapshot(
                db=self.db,
                user_id=
                    self.owner.id,
                currency="PEN",
            )
        )

        self.assertEqual(
            wallet.pending_cents,
            7_200,
        )

        self.assertEqual(
            wallet.available_cents,
            0,
        )

        platform = (
            ensure_platform_revenue_account(
                db=self.db,
                currency="PEN",
            )
        )

        self.assertEqual(
            account_balance(
                db=self.db,
                account_id=
                    platform.id,
            ),
            800,
        )

        custody = (
            ensure_project_custody_account(
                db=self.db,
                project_id=
                    self.project.id,
            )
        )

        self.assertEqual(
            account_balance(
                db=self.db,
                account_id=
                    custody.id,
            ),
            2_000,
        )

    def test_settlement_is_idempotent(
        self,
    ):
        first = (
            settle_contract_earnings(
                db=self.db,
                contract_id=
                    self.contract.id,
            )
        )

        second = (
            settle_contract_earnings(
                db=self.db,
                contract_id=
                    self.contract.id,
            )
        )

        self.assertEqual(
            first.gross_cents,
            second.gross_cents,
        )

        wallet = (
            build_user_wallet_snapshot(
                db=self.db,
                user_id=
                    self.owner.id,
                currency="PEN",
            )
        )

        self.assertEqual(
            wallet.pending_cents,
            7_200,
        )

        count = int(
            self.db.scalar(
                select(
                    func.count(
                        LedgerTransaction.id
                    )
                )
                .where(
                    LedgerTransaction
                    .contract_id
                    == self.contract.id,
                    LedgerTransaction
                    .transaction_type
                    .in_(
                        (
                            "earning",
                            "commission",
                        )
                    ),
                )
            )
            or 0
        )

        self.assertEqual(
            count,
            2,
        )

    def test_project_finalization_releases_and_refunds(
        self,
    ):
        settle_contract_earnings(
            db=self.db,
            contract_id=
                self.contract.id,
        )

        result = (
            finalize_project_economy(
                db=self.db,
                project_id=
                    self.project.id,
            )
        )

        self.assertEqual(
            result[
                "released_cents"
            ],
            7_200,
        )

        self.assertEqual(
            result[
                "refunded_cents"
            ],
            2_000,
        )

        self.assertEqual(
            result[
                "payment_status"
            ],
            "settled",
        )

        owner_wallet = (
            build_user_wallet_snapshot(
                db=self.db,
                user_id=
                    self.owner.id,
                currency="PEN",
            )
        )

        self.assertEqual(
            owner_wallet.pending_cents,
            0,
        )

        self.assertEqual(
            owner_wallet.available_cents,
            7_200,
        )

        client_wallet = (
            build_user_wallet_snapshot(
                db=self.db,
                user_id=
                    self.client.id,
                currency="PEN",
            )
        )

        self.assertEqual(
            client_wallet.available_cents,
            2_000,
        )

        custody = (
            ensure_project_custody_account(
                db=self.db,
                project_id=
                    self.project.id,
            )
        )

        self.assertEqual(
            account_balance(
                db=self.db,
                account_id=
                    custody.id,
            ),
            0,
        )

    def test_simulated_withdrawal(
        self,
    ):
        settle_contract_earnings(
            db=self.db,
            contract_id=
                self.contract.id,
        )

        finalize_project_economy(
            db=self.db,
            project_id=
                self.project.id,
        )

        result = simulate_withdrawal(
            db=self.db,
            user_id=
                self.owner.id,
            currency="PEN",
            amount_cents=5_000,
            idempotency_key=(
                "withdraw:"
                f"{self._testMethodName}"
            ),
        )

        self.assertEqual(
            result.amount_cents,
            5_000,
        )

        self.assertEqual(
            result
            .remaining_available_cents,
            2_200,
        )

        repeated = simulate_withdrawal(
            db=self.db,
            user_id=
                self.owner.id,
            currency="PEN",
            amount_cents=5_000,
            idempotency_key=(
                "withdraw:"
                f"{self._testMethodName}"
            ),
        )

        self.assertEqual(
            repeated.transaction_id,
            result.transaction_id,
        )

        self.assertEqual(
            repeated
            .remaining_available_cents,
            2_200,
        )

    def test_withdrawal_overdraft_rejected(
        self,
    ):
        with self.assertRaises(
            EconomyError
        ):
            simulate_withdrawal(
                db=self.db,
                user_id=
                    self.owner.id,
                currency="PEN",
                amount_cents=1,
                idempotency_key=(
                    "invalid-withdraw:"
                    f"{self._testMethodName}"
                ),
            )

    def test_ledger_conservation(
        self,
    ):
        settle_contract_earnings(
            db=self.db,
            contract_id=
                self.contract.id,
        )

        finalize_project_economy(
            db=self.db,
            project_id=
                self.project.id,
        )

        simulate_withdrawal(
            db=self.db,
            user_id=
                self.owner.id,
            currency="PEN",
            amount_cents=5_000,
            idempotency_key=(
                "conservation-withdraw"
            ),
        )

        account_ids = list(
            self.db.scalars(
                select(
                    LedgerAccount.id
                )
                .where(
                    LedgerAccount.currency
                    == "PEN"
                )
            ).all()
        )

        total = sum(
            account_balance(
                db=self.db,
                account_id=
                    account_id,
            )
            for account_id
            in account_ids
        )

        self.assertEqual(
            total,
            0,
        )

    def test_system_clearing_absorbs_simulated_money(
        self,
    ):
        settle_contract_earnings(
            db=self.db,
            contract_id=
                self.contract.id,
        )

        finalize_project_economy(
            db=self.db,
            project_id=
                self.project.id,
        )

        simulate_withdrawal(
            db=self.db,
            user_id=
                self.owner.id,
            currency="PEN",
            amount_cents=5_000,
            idempotency_key=(
                "clearing-withdraw"
            ),
        )

        clearing = (
            ensure_system_clearing_account(
                db=self.db,
                currency="PEN",
            )
        )

        # Creo 10,000 ficticios y luego
        # recibio 5,000 en retiro simulado.
        self.assertEqual(
            account_balance(
                db=self.db,
                account_id=
                    clearing.id,
            ),
            -5_000,
        )


class Phase10CApiTests(
    unittest.TestCase
):
    def test_withdrawal_route_exists(
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

        self.assertIn(
            (
                "/api/v1/economy/"
                "me/simulate-withdrawal"
            ),
            paths,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
