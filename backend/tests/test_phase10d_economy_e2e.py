from __future__ import annotations

import inspect
import unittest

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

from app.core.config import settings
from app.database.base import Base
from app.models.contract import TaskContract
from app.models.delegation import (
    DelegatedTask,
    DelegationRequest,
    Subcontract,
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
from app.services.contract_service import (
    select_contracts_for_project,
)
from app.services.delegation_service import (
    _eligible_candidates,
)
from app.services.economy_service import (
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


class Phase10DEconomyE2E(
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

        self.client = self._user(
            "Cliente 10D",
            "client",
        )

        self.owner_a = self._user(
            "Owner A",
            "owner-a",
        )

        self.owner_b = self._user(
            "Owner B",
            "owner-b",
        )

        self.owner_c = self._user(
            "Owner C",
            "owner-c",
        )

        self.db.flush()

        self.repliker_a = self._repliker(
            owner=self.owner_a,
            name="R-A",
        )

        self.repliker_b = self._repliker(
            owner=self.owner_b,
            name="R-B",
        )

        self.repliker_c = self._repliker(
            owner=self.owner_c,
            name="R-C",
        )

        self.db.flush()

        self.project = Project(
            client_id=self.client.id,
            title="Economia E2E 10D",
            description=(
                "Proyecto de prueba "
                "economica con delegacion."
            ),
            status="contracted",
            currency="PEN",
            budget_limit_cents=
                12_000,
            quoted_amount_cents=
                12_000,
            payment_status="unpaid",
        )

        self.db.add(
            self.project
        )

        self.db.flush()

        self.task = Task(
            project_id=
                self.project.id,
            title="Contrato raiz",
            description=(
                "Trabajo con cadena "
                "de delegacion."
            ),
            status="completed",
            complexity=80,
            max_budget_cents=
                10_000,
        )

        self.db.add(
            self.task
        )

        self.db.flush()

        self.bid = TaskBid(
            task_id=self.task.id,
            repliker_id=
                self.repliker_a.id,
            amount_cents=10_000,
            confidence_score=95,
            estimated_minutes=120,
            message="Oferta raiz",
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
                self.repliker_a.id,
            status="completed",
            currency="PEN",
            amount_cents=10_000,
            reserved_cents=10_000,
            skill_score=90,
            reputation_score=90,
            confidence_score=95,
            price_score=85,
            time_score=85,
            risk_score=90,
            selection_score=90,
            selected_by="r00",
            selection_policy_version=
                "phase10d-test",
            selection_summary=
                "Contrato raiz 10D.",
        )

        self.db.add(
            self.contract
        )

        self.db.flush()

        self._create_delegation_chain()

        simulate_project_funding(
            db=self.db,
            project_id=
                self.project.id,
            idempotency_key=(
                "phase10d-funding:"
                f"{self._testMethodName}"
            ),
            amount_cents=12_000,
            initiated_by_user_id=
                self.client.id,
        )

        self.db.flush()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def _user(
        self,
        name: str,
        key: str,
    ) -> User:
        user = User(
            full_name=name,
            email=(
                f"{key}-"
                f"{self._testMethodName}"
                "@example.test"
            ),
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.db.add(user)

        return user

    def _repliker(
        self,
        *,
        owner: User,
        name: str,
    ) -> Repliker:
        repliker = Repliker(
            owner_id=owner.id,
            name=name,
            specialty="Software",
            description="Test 10D",
            status="available",
            reputation_score=80,
            base_price_credits=50,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=0,
            is_active=True,
        )

        self.db.add(repliker)

        return repliker

    def _create_delegation_chain(
        self,
    ):
        # A delega 4,000 a B.
        request_b = DelegationRequest(
            dedup_key=(
                f"phase10d:"
                f"{self.contract.id}:b"
            ),
            project_id=
                self.project.id,
            root_contract_id=
                self.contract.id,
            parent_task_id=
                self.task.id,
            parent_request_id=None,
            delegator_repliker_id=
                self.repliker_a.id,
            depth=1,
            status="awarded",
            decision="delegate",
            reason=(
                "Delegacion de prueba A-B."
            ),
            required_skill_name=
                "backend",
            minimum_skill_level=70,
            max_budget_cents=4_000,
        )

        self.db.add(
            request_b
        )

        self.db.flush()

        delegated_b = DelegatedTask(
            delegation_request_id=
                request_b.id,
            project_id=
                self.project.id,
            parent_task_id=
                self.task.id,
            title="Subtarea B",
            description=(
                "Trabajo delegado a B."
            ),
            status="assigned",
            complexity=70,
            required_skill_name=
                "backend",
            minimum_skill_level=70,
            max_budget_cents=4_000,
        )

        self.db.add(
            delegated_b
        )

        self.db.flush()

        subcontract_b = Subcontract(
            delegation_request_id=
                request_b.id,
            delegated_task_id=
                delegated_b.id,
            project_id=
                self.project.id,
            root_contract_id=
                self.contract.id,
            parent_task_id=
                self.task.id,
            delegator_repliker_id=
                self.repliker_a.id,
            subcontractor_repliker_id=
                self.repliker_b.id,
            status="awarded",
            currency="PEN",
            amount_cents=4_000,
            reserved_cents=4_000,
            depth=1,
            selection_score=90,
            pricing_policy_version=
                "phase10d-test",
            selection_summary=
                "A delega a B.",
        )

        self.db.add(
            subcontract_b
        )

        self.db.flush()

        # B delega 1,000 de sus 4,000 a C.
        request_c = DelegationRequest(
            dedup_key=(
                f"phase10d:"
                f"{self.contract.id}:c"
            ),
            project_id=
                self.project.id,
            root_contract_id=
                self.contract.id,
            parent_task_id=
                self.task.id,
            parent_request_id=
                request_b.id,
            delegator_repliker_id=
                self.repliker_b.id,
            depth=2,
            status="awarded",
            decision="delegate",
            reason=(
                "Delegacion de prueba B-C."
            ),
            required_skill_name=
                "qa",
            minimum_skill_level=70,
            max_budget_cents=1_000,
        )

        self.db.add(
            request_c
        )

        self.db.flush()

        delegated_c = DelegatedTask(
            delegation_request_id=
                request_c.id,
            project_id=
                self.project.id,
            parent_task_id=
                self.task.id,
            title="Subtarea C",
            description=(
                "Trabajo delegado a C."
            ),
            status="assigned",
            complexity=60,
            required_skill_name="qa",
            minimum_skill_level=70,
            max_budget_cents=1_000,
        )

        self.db.add(
            delegated_c
        )

        self.db.flush()

        subcontract_c = Subcontract(
            delegation_request_id=
                request_c.id,
            delegated_task_id=
                delegated_c.id,
            project_id=
                self.project.id,
            root_contract_id=
                self.contract.id,
            parent_task_id=
                self.task.id,
            delegator_repliker_id=
                self.repliker_b.id,
            subcontractor_repliker_id=
                self.repliker_c.id,
            status="awarded",
            currency="PEN",
            amount_cents=1_000,
            reserved_cents=1_000,
            depth=2,
            selection_score=90,
            pricing_policy_version=
                "phase10d-test",
            selection_summary=
                "B delega a C.",
        )

        self.db.add(
            subcontract_c
        )

        self.db.flush()

    def _wallet(
        self,
        user: User,
    ):
        return build_user_wallet_snapshot(
            db=self.db,
            user_id=user.id,
            currency="PEN",
        )

    def test_nested_delegation_split(
        self,
    ):
        result = settle_contract_earnings(
            db=self.db,
            contract_id=
                self.contract.id,
        )

        self.assertEqual(
            result.gross_cents,
            10_000,
        )

        self.assertEqual(
            result.owner_net_cents,
            9_000,
        )

        self.assertEqual(
            result.commission_cents,
            1_000,
        )

        allocations = {
            item.repliker_id:
                item
            for item
            in result.allocations
        }

        a = allocations[
            self.repliker_a.id
        ]

        b = allocations[
            self.repliker_b.id
        ]

        c = allocations[
            self.repliker_c.id
        ]

        self.assertEqual(
            a.gross_cents,
            6_000,
        )

        self.assertEqual(
            a.owner_net_cents,
            5_400,
        )

        self.assertEqual(
            a.commission_cents,
            600,
        )

        self.assertEqual(
            b.gross_cents,
            3_000,
        )

        self.assertEqual(
            b.owner_net_cents,
            2_700,
        )

        self.assertEqual(
            b.commission_cents,
            300,
        )

        self.assertEqual(
            c.gross_cents,
            1_000,
        )

        self.assertEqual(
            c.owner_net_cents,
            900,
        )

        self.assertEqual(
            c.commission_cents,
            100,
        )

        self.assertEqual(
            self._wallet(
                self.owner_a
            ).pending_cents,
            5_400,
        )

        self.assertEqual(
            self._wallet(
                self.owner_b
            ).pending_cents,
            2_700,
        )

        self.assertEqual(
            self._wallet(
                self.owner_c
            ).pending_cents,
            900,
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
            1_000,
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

    def test_nested_settlement_idempotent(
        self,
    ):
        first = settle_contract_earnings(
            db=self.db,
            contract_id=
                self.contract.id,
        )

        second = settle_contract_earnings(
            db=self.db,
            contract_id=
                self.contract.id,
        )

        self.assertEqual(
            first.gross_cents,
            second.gross_cents,
        )

        self.assertEqual(
            self._wallet(
                self.owner_a
            ).pending_cents,
            5_400,
        )

        self.assertEqual(
            self._wallet(
                self.owner_b
            ).pending_cents,
            2_700,
        )

        self.assertEqual(
            self._wallet(
                self.owner_c
            ).pending_cents,
            900,
        )

        transaction_count = int(
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

        # 3 ganancias + 3 comisiones.
        self.assertEqual(
            transaction_count,
            6,
        )

    def test_complete_simulated_flow(
        self,
    ):
        settle_contract_earnings(
            db=self.db,
            contract_id=
                self.contract.id,
        )

        final = finalize_project_economy(
            db=self.db,
            project_id=
                self.project.id,
        )

        self.assertEqual(
            final["released_cents"],
            9_000,
        )

        self.assertEqual(
            final["refunded_cents"],
            2_000,
        )

        self.assertEqual(
            final["payment_status"],
            "settled",
        )

        self.assertEqual(
            self._wallet(
                self.owner_a
            ).available_cents,
            5_400,
        )

        self.assertEqual(
            self._wallet(
                self.owner_b
            ).available_cents,
            2_700,
        )

        self.assertEqual(
            self._wallet(
                self.owner_c
            ).available_cents,
            900,
        )

        self.assertEqual(
            self._wallet(
                self.client
            ).available_cents,
            2_000,
        )

        withdrawal_a = (
            simulate_withdrawal(
                db=self.db,
                user_id=
                    self.owner_a.id,
                currency="PEN",
                amount_cents=1_000,
                idempotency_key=
                    "phase10d-withdraw-a",
            )
        )

        withdrawal_b = (
            simulate_withdrawal(
                db=self.db,
                user_id=
                    self.owner_b.id,
                currency="PEN",
                amount_cents=500,
                idempotency_key=
                    "phase10d-withdraw-b",
            )
        )

        withdrawal_c = (
            simulate_withdrawal(
                db=self.db,
                user_id=
                    self.owner_c.id,
                currency="PEN",
                amount_cents=400,
                idempotency_key=
                    "phase10d-withdraw-c",
            )
        )

        self.assertEqual(
            withdrawal_a
            .remaining_available_cents,
            4_400,
        )

        self.assertEqual(
            withdrawal_b
            .remaining_available_cents,
            2_200,
        )

        self.assertEqual(
            withdrawal_c
            .remaining_available_cents,
            500,
        )

        repeated = simulate_withdrawal(
            db=self.db,
            user_id=
                self.owner_a.id,
            currency="PEN",
            amount_cents=1_000,
            idempotency_key=
                "phase10d-withdraw-a",
        )

        self.assertEqual(
            repeated.transaction_id,
            withdrawal_a.transaction_id,
        )

        all_account_ids = list(
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
            in all_account_ids
        )

        self.assertEqual(
            total,
            0,
        )

        clearing = (
            ensure_system_clearing_account(
                db=self.db,
                currency="PEN",
            )
        )

        self.assertEqual(
            account_balance(
                db=self.db,
                account_id=
                    clearing.id,
            ),
            -10_100,
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
            1_000,
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

    def test_economic_anti_self_dealing_guards(
        self,
    ):
        contract_source = inspect.getsource(
            select_contracts_for_project
        )

        delegation_source = inspect.getsource(
            _eligible_candidates
        )

        self.assertIn(
            "project.client_id",
            contract_source,
        )

        self.assertIn(
            "repliker.owner_id",
            contract_source,
        )

        self.assertIn(
            "project.client_id",
            delegation_source,
        )

        self.assertIn(
            "delegator.owner_id",
            delegation_source,
        )

    def test_real_money_remains_disabled(
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


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
