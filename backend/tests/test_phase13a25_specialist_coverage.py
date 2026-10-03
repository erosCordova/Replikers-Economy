from __future__ import annotations

import unittest

from unittest.mock import patch

import app.models  # noqa: F401

from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import Session

from app.api.routes.coordinator import (
    plan_project,
)
from app.database.base import Base
from app.models.contract import (
    TaskContract,
)
from app.models.project import Project
from app.models.project_specialist import (
    ProjectSpecialistRequirement,
)
from app.models.repliker import Repliker
from app.models.task import (
    Task,
    TaskBid,
)
from app.models.user import User
from app.schemas.coordinator import (
    AIProjectPlan,
)
from app.services.specialist_coverage_service import (
    sync_project_specialist_coverage,
)


class CoverageTestBase(
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
            email="cliente@coverage.test",
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.owner = User(
            full_name="Ecosistema",
            email="ecosistema@coverage.test",
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

        self.frontend = Repliker(
            owner_id=self.owner.id,
            name="Nova",
            specialty=
                "Frontend Developer",
            description="Interfaz.",
            status="assigned",
            reputation_score=90,
            base_price_credits=90,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=10,
            is_active=True,
        )

        self.vera = Repliker(
            owner_id=self.owner.id,
            name="Vera",
            specialty=
                "Final Reviewer",
            description="Revision final.",
            status="available",
            reputation_score=100,
            base_price_credits=100,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=20,
            is_active=True,
        )

        self.db.add_all(
            [
                self.frontend,
                self.vera,
            ]
        )

        self.db.flush()

        self.project = Project(
            client_id=self.client.id,
            title="Proyecto principal",
            description="Prueba.",
            status="planned",
            currency="PEN",
            budget_limit_cents=10000,
            quoted_amount_cents=5000,
        )

        self.db.add(
            self.project
        )

        self.db.flush()

        self.task = Task(
            project_id=self.project.id,
            title="Crear interfaz",
            description="Interfaz.",
            required_specialty=
                "Frontend Developer",
            status="assigned",
            complexity=50,
            max_budget_cents=5000,
        )

        self.db.add(
            self.task
        )

        self.db.flush()

        self.bid = TaskBid(
            task_id=self.task.id,
            repliker_id=
                self.frontend.id,
            amount_cents=4000,
            confidence_score=95,
            estimated_minutes=60,
            message="Acepto.",
            status="accepted",
        )

        self.db.add(
            self.bid
        )

        self.db.flush()

        self.contract = TaskContract(
            project_id=self.project.id,
            task_id=self.task.id,
            bid_id=self.bid.id,
            repliker_id=
                self.frontend.id,
            status="awarded",
            currency="PEN",
            amount_cents=4000,
            reserved_cents=4000,
            skill_score=100,
            reputation_score=90,
            confidence_score=95,
            price_score=90,
            time_score=90,
            risk_score=95,
            selection_score=95,
            selected_by="test",
            selection_policy_version=
                "test",
            selection_summary=
                "Prueba.",
        )

        self.db.add(
            self.contract
        )

        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add_requirement(
        self,
        *,
        project_id: int,
        specialty: str,
        mandatory: bool = True,
        final_gate: bool = False,
    ):
        requirement = (
            ProjectSpecialistRequirement(
                project_id=project_id,
                specialty=specialty,
                reason="Necesario.",
                is_mandatory=mandatory,
                is_final_gate=
                    final_gate,
                coverage_status=
                    "pending",
            )
        )

        self.db.add(
            requirement
        )

        self.db.flush()

        return requirement


class Phase13A25CoverageTests(
    CoverageTestBase
):
    def test_contract_and_final_gate_cover_project(
        self,
    ):
        frontend_req = (
            self.add_requirement(
                project_id=
                    self.project.id,
                specialty=
                    "Frontend Developer",
            )
        )

        final_req = (
            self.add_requirement(
                project_id=
                    self.project.id,
                specialty=
                    "Final Reviewer",
                final_gate=True,
            )
        )

        snapshot = (
            sync_project_specialist_coverage(
                db=self.db,
                project_id=
                    self.project.id,
            )
        )

        self.assertTrue(
            snapshot.ready
        )

        self.assertEqual(
            snapshot.mandatory_total,
            2,
        )

        self.assertEqual(
            snapshot.mandatory_covered,
            2,
        )

        self.assertEqual(
            frontend_req
            .assigned_repliker_id,
            self.frontend.id,
        )

        self.assertEqual(
            final_req
            .assigned_repliker_id,
            self.vera.id,
        )

    def test_missing_mandatory_specialist_blocks(
        self,
    ):
        self.add_requirement(
            project_id=self.project.id,
            specialty=
                "Backend Developer",
        )

        self.add_requirement(
            project_id=self.project.id,
            specialty=
                "Final Reviewer",
            final_gate=True,
        )

        snapshot = (
            sync_project_specialist_coverage(
                db=self.db,
                project_id=
                    self.project.id,
            )
        )

        self.assertFalse(
            snapshot.ready
        )

        self.assertIn(
            "Backend Developer",
            snapshot
            .missing_specialties,
        )

    def test_optional_specialist_does_not_block(
        self,
    ):
        self.add_requirement(
            project_id=self.project.id,
            specialty=
                "Backend Developer",
            mandatory=False,
        )

        self.add_requirement(
            project_id=self.project.id,
            specialty=
                "Final Reviewer",
            final_gate=True,
        )

        snapshot = (
            sync_project_specialist_coverage(
                db=self.db,
                project_id=
                    self.project.id,
            )
        )

        self.assertTrue(
            snapshot.ready
        )

    def test_final_reviewer_is_not_reused(
        self,
    ):
        first_req = self.add_requirement(
            project_id=self.project.id,
            specialty=
                "Final Reviewer",
            final_gate=True,
        )

        first = (
            sync_project_specialist_coverage(
                db=self.db,
                project_id=
                    self.project.id,
            )
        )

        self.assertTrue(
            first.ready
        )

        self.assertEqual(
            first_req
            .assigned_repliker_id,
            self.vera.id,
        )

        second_project = Project(
            client_id=self.client.id,
            title="Segundo proyecto",
            description="Prueba.",
            status="planned",
            currency="PEN",
            budget_limit_cents=5000,
        )

        self.db.add(
            second_project
        )

        self.db.flush()

        second_req = self.add_requirement(
            project_id=
                second_project.id,
            specialty=
                "Final Reviewer",
            final_gate=True,
        )

        second = (
            sync_project_specialist_coverage(
                db=self.db,
                project_id=
                    second_project.id,
            )
        )

        self.assertFalse(
            second.ready
        )

        self.assertIsNone(
            second_req
            .assigned_repliker_id
        )


class Phase13A25PlanningPersistenceTests(
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
            email="cliente@planning.test",
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.owner = User(
            full_name="Ecosistema",
            email="owner@planning.test",
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
            specialty=
                "Product / Requirements",
            description="Planificacion.",
            status="available",
            reputation_score=100,
            base_price_credits=85,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=20,
            is_active=True,
        )

        self.db.add(
            self.iris
        )

        self.project = Project(
            client_id=self.client.id,
            title="Proyecto de Iris",
            description="Prueba.",
            status="draft",
            currency="PEN",
            budget_limit_cents=10000,
        )

        self.db.add(
            self.project
        )

        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_iris_persists_specialist_requirements(
        self,
    ):
        plan = AIProjectPlan.model_validate(
            {
                "summary":
                    "Plan de prueba.",
                "strategy":
                    "Implementacion.",
                "required_specialists": [
                    {
                        "specialty":
                            "Frontend Developer",
                        "reason":
                            "Construir interfaz.",
                        "mandatory":
                            True,
                        "final_gate":
                            False,
                    },
                    {
                        "specialty":
                            "Final Reviewer",
                        "reason":
                            "Revision final.",
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
                            "Construir interfaz.",
                        "required_specialty":
                            "Frontend Developer",
                        "complexity":
                            50,
                        "max_budget_cents":
                            5000,
                        "required_skills":
                            [],
                        "acceptance_criteria": [
                            "Interfaz funcional."
                        ],
                    }
                ],
            }
        )

        with (
            patch(
                "app.api.routes.coordinator."
                "_get_official_iris",
                return_value=self.iris,
            ),
            patch(
                "app.api.routes.coordinator."
                "build_project_plan",
                return_value=plan,
            ),
        ):
            response = plan_project(
                project_id=
                    self.project.id,
                db=self.db,
                current_user=
                    self.client,
            )

        self.assertEqual(
            response.coordinator,
            "Iris",
        )

        requirements = list(
            self.db.scalars(
                select(
                    ProjectSpecialistRequirement
                )
                .where(
                    ProjectSpecialistRequirement
                    .project_id
                    == self.project.id
                )
                .order_by(
                    ProjectSpecialistRequirement
                    .id
                )
            ).all()
        )

        self.assertEqual(
            len(requirements),
            2,
        )

        self.assertEqual(
            [
                item.specialty
                for item in requirements
            ],
            [
                "Frontend Developer",
                "Final Reviewer",
            ],
        )

        self.assertTrue(
            requirements[1]
            .is_final_gate
        )


if __name__ == "__main__":
    unittest.main()
