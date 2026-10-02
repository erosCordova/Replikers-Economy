from __future__ import annotations

import inspect
import unittest

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401

from app.api.routes.economy import (
    router as economy_router,
)
from app.core.config import settings
from app.database.base import Base
from app.models.project import Project
from app.models.user import User
from app.services.contract_service import (
    select_contracts_for_project,
)
from app.services.economy_service import (
    EconomyError,
    build_project_economy_snapshot,
    project_has_sufficient_custody,
    simulate_project_funding,
)
from app.services.project_lifecycle_service import (
    project_is_funded,
)


class Phase10BSimulatedFundingTests(
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
            full_name="Simulation User",
            email=(
                "simulation-"
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
            client_id=self.user.id,
            title="Proyecto simulado",
            description=(
                "Proyecto de prueba "
                "economica."
            ),
            currency="PEN",
            budget_limit_cents=
                15_000,
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

    def test_real_money_is_disabled(
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

    def test_partial_funding(
        self,
    ):
        result = (
            simulate_project_funding(
                db=self.db,
                project_id=
                    self.project.id,
                idempotency_key=
                    "phase10b-partial",
                amount_cents=4_000,
                initiated_by_user_id=
                    self.user.id,
            )
        )

        self.assertEqual(
            result.custody_balance_cents,
            4_000,
        )

        self.assertEqual(
            result
            .remaining_to_fund_cents,
            6_000,
        )

        self.assertEqual(
            result.payment_status,
            "partially_funded",
        )

        self.assertFalse(
            result.fully_funded
        )

        self.assertFalse(
            project_has_sufficient_custody(
                db=self.db,
                project=self.project,
            )
        )

    def test_full_funding(
        self,
    ):
        first = (
            simulate_project_funding(
                db=self.db,
                project_id=
                    self.project.id,
                idempotency_key=
                    "phase10b-first",
                amount_cents=4_000,
            )
        )

        self.assertFalse(
            first.fully_funded
        )

        second = (
            simulate_project_funding(
                db=self.db,
                project_id=
                    self.project.id,
                idempotency_key=
                    "phase10b-second",
                amount_cents=6_000,
            )
        )

        self.assertTrue(
            second.fully_funded
        )

        self.assertEqual(
            second.payment_status,
            "escrowed",
        )

        self.assertEqual(
            second.custody_balance_cents,
            10_000,
        )

        self.assertTrue(
            project_is_funded(
                db=self.db,
                project=self.project,
            )
        )

    def test_automatic_remaining_amount(
        self,
    ):
        result = (
            simulate_project_funding(
                db=self.db,
                project_id=
                    self.project.id,
                idempotency_key=
                    "phase10b-auto",
            )
        )

        self.assertEqual(
            result.amount_cents,
            10_000,
        )

        self.assertTrue(
            result.fully_funded
        )

    def test_funding_idempotency(
        self,
    ):
        first = (
            simulate_project_funding(
                db=self.db,
                project_id=
                    self.project.id,
                idempotency_key=
                    "phase10b-idempotent",
                amount_cents=2_500,
            )
        )

        second = (
            simulate_project_funding(
                db=self.db,
                project_id=
                    self.project.id,
                idempotency_key=
                    "phase10b-idempotent",
                amount_cents=2_500,
            )
        )

        self.assertEqual(
            first.transaction_id,
            second.transaction_id,
        )

        snapshot = (
            build_project_economy_snapshot(
                db=self.db,
                project_id=
                    self.project.id,
            )
        )

        self.assertEqual(
            snapshot
            .custody_balance_cents,
            2_500,
        )

    def test_overfunding_rejected(
        self,
    ):
        with self.assertRaises(
            EconomyError
        ):
            simulate_project_funding(
                db=self.db,
                project_id=
                    self.project.id,
                idempotency_key=
                    "phase10b-overfund",
                amount_cents=10_001,
            )

    def test_contract_service_uses_ledger(
        self,
    ):
        source = inspect.getsource(
            select_contracts_for_project
        )

        self.assertIn(
            "project_has_sufficient_custody",
            source,
        )

    def test_lifecycle_uses_ledger(
        self,
    ):
        source = inspect.getsource(
            project_is_funded
        )

        self.assertIn(
            "project_has_sufficient_custody",
            source,
        )


class Phase10BApiTests(
    unittest.TestCase
):
    def test_simulation_route_exists(
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
                "projects/{project_id}/"
                "simulate-funding"
            ),
            paths,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
