from __future__ import annotations

import asyncio
import unittest

from types import SimpleNamespace
from unittest.mock import patch

import app.models  # noqa: F401

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes.coordinator import (
    plan_project,
)
from app.api.routes.market import (
    run_autonomous_market,
)
from app.api.routes.realtime import (
    stream_my_events,
    stream_project_events,
)
from app.database.base import Base
from app.models.project import Project
from app.models.repliker import Repliker
from app.models.task import Task
from app.models.user import User
from app.schemas.coordinator import (
    AIProjectPlan,
)
from app.schemas.market import (
    AgentDecisionAI,
)
from app.services.web_repliker_registry_service import (
    ECOSYSTEM_OWNER_EMAIL,
)


class Phase13A23TransactionBoundaryTests(
    unittest.TestCase
):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:"
        )

        Base.metadata.create_all(
            self.engine
        )

        self.db = Session(
            bind=self.engine,
            expire_on_commit=False,
        )

        self.client = User(
            full_name="Cliente",
            email="cliente@tests.invalid",
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.owner = User(
            full_name="Ecosistema",
            email=ECOSYSTEM_OWNER_EMAIL,
            password_hash="test",
            role="system",
            is_active=False,
        )

        self.db.add_all(
            [
                self.client,
                self.owner,
            ]
        )

        self.db.flush()

        self.iris = Repliker(
            owner_id=self.owner.id,
            name="Iris",
            specialty="Product / Requirements",
            description="Planificación.",
            status="available",
            reputation_score=90,
            base_price_credits=85,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=0,
            is_active=True,
        )

        self.worker = Repliker(
            owner_id=self.owner.id,
            name="Nova",
            specialty="Frontend Developer",
            description="Interfaz.",
            status="available",
            reputation_score=90,
            base_price_credits=90,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=0,
            is_active=True,
        )

        self.db.add_all(
            [
                self.iris,
                self.worker,
            ]
        )

        self.db.flush()

        self.coordinator_project = Project(
            client_id=self.client.id,
            title="Proyecto de planificación",
            description="Proyecto de prueba.",
            status="draft",
            currency="PEN",
            budget_limit_cents=10000,
        )

        self.market_project = Project(
            client_id=self.client.id,
            title="Proyecto de mercado",
            description="Proyecto de prueba.",
            status="planned",
            currency="PEN",
            budget_limit_cents=10000,
            quoted_amount_cents=5000,
        )

        self.db.add_all(
            [
                self.coordinator_project,
                self.market_project,
            ]
        )

        self.db.flush()

        self.market_task = Task(
            project_id=self.market_project.id,
            title="Construir interfaz",
            description="Crear la interfaz.",
            required_specialty=
                "Frontend Developer",
            status="planned",
            complexity=50,
            max_budget_cents=5000,
        )

        self.db.add(
            self.market_task
        )

        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_project_stream_releases_transaction(
        self,
    ):
        request = SimpleNamespace()

        async def disconnected():
            return True

        request.is_disconnected = (
            disconnected
        )

        response = asyncio.run(
            stream_project_events(
                project_id=
                    self.market_project.id,
                request=request,
                after_id=0,
                last_event_id=None,
                db=self.db,
                current_user=self.client,
            )
        )

        self.assertIsNotNone(
            response
        )

        self.assertFalse(
            self.db.in_transaction()
        )

    def test_account_stream_releases_transaction(
        self,
    ):
        request = SimpleNamespace()

        async def disconnected():
            return True

        request.is_disconnected = (
            disconnected
        )

        response = asyncio.run(
            stream_my_events(
                request=request,
                after_id=0,
                last_event_id=None,
                db=self.db,
                current_user=self.client,
            )
        )

        self.assertIsNotNone(
            response
        )

        self.assertFalse(
            self.db.in_transaction()
        )

    def test_coordinator_has_no_transaction_during_ai(
        self,
    ):
        def fake_plan(
            *,
            project_data,
            marketplace_data,
        ):
            self.assertFalse(
                self.db.in_transaction()
            )

            return AIProjectPlan.model_validate(
                {
                    "summary":
                        "Plan de prueba.",
                    "strategy":
                        "Construcción ordenada.",
                    "required_specialists": [
                        {
                            "specialty":
                                "Frontend Developer",
                            "reason":
                                "Crear la interfaz.",
                            "mandatory":
                                True,
                            "final_gate":
                                False,
                        },
                        {
                            "specialty":
                                "Final Reviewer",
                            "reason":
                                "Revisión final.",
                            "mandatory":
                                True,
                            "final_gate":
                                True,
                        },
                    ],
                    "market_gaps": [],
                    "tasks": [
                        {
                            "title":
                                "Crear interfaz",
                            "description":
                                "Crear interfaz.",
                            "required_specialty":
                                "Frontend Developer",
                            "complexity":
                                50,
                            "max_budget_cents":
                                5000,
                            "required_skills": [],
                            "acceptance_criteria": [
                                "Interfaz funcional."
                            ],
                        }
                    ],
                }
            )

        with patch(
            "app.api.routes.coordinator."
            "build_project_plan",
            side_effect=fake_plan,
        ):
            response = plan_project(
                project_id=
                    self.coordinator_project.id,
                db=self.db,
                current_user=self.client,
            )

        self.assertEqual(
            response.coordinator,
            "Iris",
        )

    def test_market_has_no_transaction_during_ai(
        self,
    ):
        calls = []

        def fake_evaluate(**kwargs):
            calls.append(
                kwargs
            )

            self.assertFalse(
                self.db.in_transaction()
            )

            return AgentDecisionAI(
                decision="pass",
                amount_cents=None,
                confidence_score=80,
                estimated_minutes=None,
                message=(
                    "No participaré en esta tarea."
                ),
                reasoning=(
                    "Prueba de transacción."
                ),
            )

        with (
            patch(
                "app.api.routes.market."
                "resolve_repliker_tool_names",
                return_value=(),
            ),
            patch(
                "app.api.routes.market."
                "evaluate_repliker_for_task",
                side_effect=fake_evaluate,
            ),
        ):
            response = run_autonomous_market(
                project_id=
                    self.market_project.id,
                db=self.db,
                current_user=self.client,
            )

        self.assertGreater(
            len(calls),
            0,
        )

        self.assertGreater(
            response.new_decisions,
            0,
        )


if __name__ == "__main__":
    unittest.main()
