from __future__ import annotations

import unittest
from types import SimpleNamespace

import app.models  # noqa: F401

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agentic.project_graph import (
    ProjectLifecycleHandlers,
    run_project_lifecycle,
)
from app.database.base import Base
from app.models.contract import TaskContract
from app.models.project import Project
from app.models.project_specialist import (
    ProjectSpecialistOffer,
    ProjectSpecialistRequirement,
)
from app.models.repliker import Repliker
from app.models.task import (
    Task,
    TaskBid,
)
from app.models.user import User
from app.services.specialist_coverage_service import (
    enforce_project_specialist_gate,
    sync_project_specialist_coverage,
)


class Phase13A26GateServiceTests(
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
            email="cliente@gate.test",
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.owner = User(
            full_name="Ecosistema",
            email="owner@gate.test",
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

        self.nova = Repliker(
            owner_id=self.owner.id,
            name="Nova",
            specialty=
                "Frontend Developer",
            description="Interfaz.",
            status="assigned",
            reputation_score=90,
            base_price_credits=50,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=10,
            is_active=True,
        )

        self.vera = Repliker(
            owner_id=self.owner.id,
            name="Vera",
            specialty="Final Reviewer",
            description="Revision final.",
            status="available",
            reputation_score=100,
            base_price_credits=50,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=20,
            is_active=True,
        )

        self.db.add_all(
            [
                self.nova,
                self.vera,
            ]
        )

        self.db.flush()

        self.project = Project(
            client_id=self.client.id,
            title="Proyecto",
            description="Prueba.",
            status="partially_contracted",
            currency="PEN",
            budget_limit_cents=10000,
        )

        self.db.add(
            self.project
        )

        self.db.flush()

        self.task = Task(
            project_id=self.project.id,
            title="Interfaz",
            description="Crear interfaz.",
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
            repliker_id=self.nova.id,
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
            repliker_id=self.nova.id,
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
            selection_policy_version="test",
            selection_summary="Prueba.",
        )

        self.db.add(
            self.contract
        )

        self.db.commit()

    def accept_final_reviewer(
        self,
        requirement,
        repliker=None,
    ):
        repliker = repliker or self.vera

        offer = ProjectSpecialistOffer(
            project_id=requirement.project_id,
            requirement_id=requirement.id,
            repliker_id=repliker.id,
            status="accepted",
            confidence_score=100,
            message="Acepto.",
            reasoning="Disponible.",
        )

        self.db.add(offer)
        self.db.flush()

        return offer

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add_requirement(
        self,
        specialty: str,
        *,
        final_gate: bool = False,
    ):
        item = ProjectSpecialistRequirement(
            project_id=self.project.id,
            specialty=specialty,
            reason="Necesario.",
            is_mandatory=True,
            is_final_gate=final_gate,
            coverage_status="pending",
        )

        self.db.add(
            item
        )

        self.db.flush()

        return item

    def test_legacy_project_without_requirements_is_compatible(
        self,
    ):
        snapshot = (
            sync_project_specialist_coverage(
                db=self.db,
                project_id=self.project.id,
            )
        )

        self.assertTrue(
            snapshot.ready
        )

    def test_missing_specialist_prevents_contracted_status(
        self,
    ):
        self.add_requirement(
            "Frontend Developer"
        )

        self.add_requirement(
            "Backend Developer"
        )

        self.add_requirement(
            "Final Reviewer",
            final_gate=True,
        )

        snapshot = (
            enforce_project_specialist_gate(
                db=self.db,
                project_id=self.project.id,
            )
        )

        self.assertFalse(
            snapshot.ready
        )

        self.assertEqual(
            self.project.status,
            "partially_contracted",
        )

        self.assertIn(
            "Backend Developer",
            snapshot.missing_specialties,
        )

    def test_complete_coverage_promotes_project(
        self,
    ):
        self.add_requirement(
            "Frontend Developer"
        )

        self.add_requirement(
            "Final Reviewer",
            final_gate=True,
        )

        # 13A26_ACCEPT_FINAL
        final_requirement = (
            self.db.query(
                ProjectSpecialistRequirement
            )
            .filter_by(
                project_id=self.project.id,
                is_final_gate=True,
            )
            .one()
        )

        self.db.add(
            ProjectSpecialistOffer(
                project_id=self.project.id,
                requirement_id=
                    final_requirement.id,
                repliker_id=self.vera.id,
                status="accepted",
                confidence_score=100,
                message="Acepto.",
                reasoning="Disponible.",
            )
        )

        self.db.flush()

        snapshot = (
            enforce_project_specialist_gate(
                db=self.db,
                project_id=self.project.id,
            )
        )

        self.assertTrue(
            snapshot.ready
        )

        self.assertEqual(
            self.project.status,
            "contracted",
        )


class Phase13A26GraphGateTests(
    unittest.TestCase
):
    def test_graph_stops_before_delegation_when_coverage_missing(
        self,
    ):
        project = SimpleNamespace(
            id=1,
            status="planned",
            payment_status="funded",
        )

        calls = {
            "delegation": 0,
            "execution": 0,
        }

        def get_project(**kwargs):
            _ = kwargs
            return project

        def market(**kwargs):
            _ = kwargs
            project.status = (
                "market_open"
            )

            return {
                "new_decisions": 1,
                "bid_count": 1,
            }

        def contract(**kwargs):
            _ = kwargs

            project.status = (
                "partially_contracted"
            )

            return {
                "contracts_created": 1,
                "contract_ids": [10],
                "specialist_coverage_ready":
                    False,
                "mandatory_specialists": 3,
                "covered_specialists": 2,
                "missing_specialties": [
                    "Backend Developer"
                ],
            }

        def delegation(**kwargs):
            _ = kwargs
            calls["delegation"] += 1

            return {
                "processed": 1,
                "delegated": 0,
            }

        def execution(**kwargs):
            _ = kwargs
            calls["execution"] += 1

            raise AssertionError(
                "La ejecucion no debio iniciar."
            )

        handlers = (
            ProjectLifecycleHandlers(
                get_project=get_project,
                is_funded=lambda **kwargs: True,
                plan=lambda **kwargs: {},
                market=market,
                contract=contract,
                delegation=delegation,
                execution=execution,
                qa=lambda **kwargs: {},
                integration=lambda **kwargs: {
                    "completed": False,
                    "total_tasks": 1,
                    "completed_tasks": 0,
                },
                active_contracts=
                    lambda **kwargs: [10],
            )
        )

        state = run_project_lifecycle(
            db=None,
            project_id=1,
            handlers=handlers,
        )

        self.assertEqual(
            state["current_stage"],
            "awaiting_specialists",
        )

        self.assertEqual(
            state["next_action"],
            "rerun_market",
        )

        self.assertFalse(
            state[
                "specialist_coverage_ready"
            ]
        )

        self.assertEqual(
            calls["delegation"],
            0,
        )

        self.assertEqual(
            calls["execution"],
            0,
        )

        self.assertIn(
            "Desarrollador de Servidor",
            state["missing_specialties"],
        )

        self.assertNotIn(
            "Backend Developer",
            state["blocked_reason"],
        )



class Phase13A26ResumeGateTests(
    unittest.TestCase
):
    def test_contracted_project_revalidates_coverage(
        self,
    ):
        project = SimpleNamespace(
            id=77,
            status="contracted",
            payment_status="funded",
        )

        calls = {
            "contract": 0,
            "delegation": 0,
            "execution": 0,
        }

        def get_project(**kwargs):
            _ = kwargs
            return project

        def contract(**kwargs):
            _ = kwargs

            calls["contract"] += 1

            project.status = (
                "partially_contracted"
            )

            return {
                "contracts_created": 0,
                "contract_ids": [100],
                "specialist_coverage_ready":
                    False,
                "mandatory_specialists": 3,
                "covered_specialists": 2,
                "missing_specialties": [
                    "Backend Developer"
                ],
            }

        def delegation(**kwargs):
            _ = kwargs

            calls["delegation"] += 1

            raise AssertionError(
                "No debió delegar sin "
                "cobertura completa."
            )

        def execution(**kwargs):
            _ = kwargs

            calls["execution"] += 1

            raise AssertionError(
                "No debió ejecutar sin "
                "cobertura completa."
            )

        handlers = (
            ProjectLifecycleHandlers(
                get_project=get_project,
                is_funded=
                    lambda **kwargs: True,
                plan=lambda **kwargs: {},
                market=lambda **kwargs: {},
                contract=contract,
                delegation=delegation,
                execution=execution,
                qa=lambda **kwargs: {},
                integration=
                    lambda **kwargs: {
                        "completed": False,
                        "total_tasks": 1,
                        "completed_tasks": 0,
                    },
                active_contracts=
                    lambda **kwargs: [100],
            )
        )

        state = run_project_lifecycle(
            db=None,
            project_id=77,
            handlers=handlers,
        )

        self.assertEqual(
            calls["contract"],
            1,
        )

        self.assertEqual(
            calls["delegation"],
            0,
        )

        self.assertEqual(
            calls["execution"],
            0,
        )

        self.assertEqual(
            state["current_stage"],
            "awaiting_specialists",
        )

        self.assertEqual(
            state["missing_specialties"],
            [
                "Desarrollador de Servidor"
            ],
        )

        self.assertIn(
            "Desarrollador de Servidor",
            state["blocked_reason"],
        )


if __name__ == "__main__":
    unittest.main()
