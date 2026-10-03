from __future__ import annotations

import json
import unittest

from datetime import (
    datetime,
    timezone,
)
from types import SimpleNamespace
from unittest.mock import (
    MagicMock,
    patch,
)

import app.models  # noqa: F401

from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import Session

from app.agentic.project_graph import (
    ProjectLifecycleHandlers,
    run_project_lifecycle,
)
from app.database.base import Base
from app.models.project import Project
from app.models.project_specialist import (
    ProjectFinalReview,
    ProjectSpecialistOffer,
    ProjectSpecialistRequirement,
)
from app.models.repliker import Repliker
from app.models.task import (
    Task,
    TaskAcceptanceCriterion,
)
from app.models.user import User
from app.schemas.final_review import (
    FinalReviewCorrectionAI,
    FinalReviewDecisionAI,
)
from app.services.final_review_service import (
    run_project_final_review,
)


LIFECYCLE_MODULE = (
    "app.services."
    "project_lifecycle_service"
)


class Phase13FinalReviewAgentTests(
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
            email="cliente@vera.test",
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.owner = User(
            full_name="Ecosistema",
            email="owner@vera.test",
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

        self.vera = Repliker(
            owner_id=self.owner.id,
            name="Vera",
            specialty="Final Reviewer",
            description=(
                "Revisión integral final."
            ),
            status="available",
            reputation_score=100,
            base_price_credits=100,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=20,
            is_active=True,
        )

        self.db.add(
            self.vera
        )

        self.db.flush()

        self.project = Project(
            client_id=self.client.id,
            title="Proyecto",
            description="Entrega completa.",
            status="awaiting_final_review",
            currency="PEN",
            budget_limit_cents=10000,
        )

        self.db.add(
            self.project
        )

        self.db.flush()

        self.task = Task(
            project_id=self.project.id,
            title="Implementación",
            description=(
                "Implementación principal."
            ),
            required_specialty=
                "Backend Developer",
            status="completed",
            complexity=70,
            max_budget_cents=1000,
        )

        self.db.add(
            self.task
        )

        self.db.flush()

        self.db.add(
            TaskAcceptanceCriterion(
                task_id=self.task.id,
                description=(
                    "La implementación "
                    "debe funcionar."
                ),
                status="passed",
                evidence=(
                    "Verificación QA aprobada."
                ),
                is_mandatory=True,
            )
        )

        self.requirement = (
            ProjectSpecialistRequirement(
                project_id=self.project.id,
                specialty="Final Reviewer",
                reason="Validar entrega.",
                is_mandatory=True,
                is_final_gate=True,
                coverage_status="covered",
                assigned_repliker_id=
                    self.vera.id,
            )
        )

        self.db.add(
            self.requirement
        )

        self.db.flush()

        self.db.add(
            ProjectSpecialistOffer(
                project_id=self.project.id,
                requirement_id=
                    self.requirement.id,
                repliker_id=self.vera.id,
                status="accepted",
                confidence_score=100,
                message=(
                    "Acepto realizar "
                    "la revisión final."
                ),
                reasoning="Disponible.",
                responded_at=datetime.now(
                    timezone.utc
                ),
            )
        )

        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_vera_can_approve_project(
        self,
    ):
        def evaluator(**kwargs):
            self.assertEqual(
                kwargs[
                    "reviewer_data"
                ]["nombre"],
                "Vera",
            )

            return FinalReviewDecisionAI(
                decision="approve",
                score=98,
                summary=(
                    "La entrega cumple "
                    "los requisitos y puede "
                    "ser entregada."
                ),
                corrections=[],
                reasoning=(
                    "Evidencia suficiente."
                ),
            )

        with patch(
            f"{LIFECYCLE_MODULE}."
            "finalize_project_economy"
        ) as economy:
            result = (
                run_project_final_review(
                    db=self.db,
                    project_id=
                        self.project.id,
                    evaluator=evaluator,
                )
            )

        self.assertEqual(
            result["status"],
            "approved",
        )

        self.assertTrue(
            result["completed"]
        )

        self.assertEqual(
            self.project.status,
            "completed",
        )

        economy.assert_called_once()

    def test_vera_can_request_corrections(
        self,
    ):
        def evaluator(**kwargs):
            _ = kwargs

            return FinalReviewDecisionAI(
                decision=
                    "request_corrections",
                score=72,
                summary=(
                    "La entrega necesita "
                    "una corrección antes "
                    "de ser aprobada."
                ),
                corrections=[
                    FinalReviewCorrectionAI(
                        task_id=
                            self.task.id,
                        instruction=(
                            "Corrige la validación "
                            "de la entrega."
                        ),
                        severity="high",
                    )
                ],
                reasoning=(
                    "Existe una observación "
                    "pendiente."
                ),
            )

        with patch(
            f"{LIFECYCLE_MODULE}."
            "finalize_project_economy"
        ) as economy:
            result = (
                run_project_final_review(
                    db=self.db,
                    project_id=
                        self.project.id,
                    evaluator=evaluator,
                )
            )

        self.assertEqual(
            result["status"],
            "corrections_requested",
        )

        self.assertFalse(
            result["completed"]
        )

        self.assertEqual(
            self.project.status,
            "corrections_requested",
        )

        economy.assert_not_called()

        review = self.db.scalar(
            select(
                ProjectFinalReview
            )
            .where(
                ProjectFinalReview.project_id
                == self.project.id
            )
        )

        corrections = json.loads(
            review.corrections_json
        )

        self.assertEqual(
            corrections[0]["task_id"],
            self.task.id,
        )

    def test_ai_wait_has_no_open_transaction(
        self,
    ):
        transaction_states = []

        def evaluator(**kwargs):
            _ = kwargs

            transaction_states.append(
                self.db.in_transaction()
            )

            return FinalReviewDecisionAI(
                decision=
                    "request_corrections",
                score=80,
                summary=(
                    "Se requiere "
                    "una corrección."
                ),
                corrections=[
                    FinalReviewCorrectionAI(
                        task_id=
                            self.task.id,
                        instruction=(
                            "Ajusta el resultado."
                        ),
                    )
                ],
                reasoning="Pendiente.",
            )

        run_project_final_review(
            db=self.db,
            project_id=self.project.id,
            evaluator=evaluator,
        )

        self.assertEqual(
            transaction_states,
            [False],
        )

    def test_same_delivery_is_not_reviewed_twice(
        self,
    ):
        calls = 0

        def evaluator(**kwargs):
            nonlocal calls
            _ = kwargs

            calls += 1

            return FinalReviewDecisionAI(
                decision=
                    "request_corrections",
                score=70,
                summary=(
                    "Se requieren cambios."
                ),
                corrections=[
                    FinalReviewCorrectionAI(
                        task_id=
                            self.task.id,
                        instruction=(
                            "Corrige la entrega."
                        ),
                    )
                ],
                reasoning="Pendiente.",
            )

        first = run_project_final_review(
            db=self.db,
            project_id=self.project.id,
            evaluator=evaluator,
        )

        second = run_project_final_review(
            db=self.db,
            project_id=self.project.id,
            evaluator=evaluator,
        )

        self.assertEqual(
            calls,
            1,
        )

        self.assertEqual(
            first["review_id"],
            second["review_id"],
        )

    def test_graph_executes_final_reviewer(
        self,
    ):
        project = SimpleNamespace(
            id=55,
            status="awaiting_final_review",
            payment_status="funded",
        )

        review_calls = []

        def integration(**kwargs):
            _ = kwargs

            return {
                "completed": False,
                "total_tasks": 1,
                "completed_tasks": 1,
                "project_status":
                    project.status,
                "final_review_required":
                    True,
                "final_review_status":
                    "pending",
                "final_review_id":
                    None,
            }

        def final_review(**kwargs):
            review_calls.append(
                kwargs["project_id"]
            )

            project.status = "completed"

            return {
                "review_id": 99,
                "reviewer_id": 15,
                "attempt_number": 1,
                "status": "approved",
                "score": 100,
                "summary": (
                    "Proyecto aprobado."
                ),
                "corrections": [],
                "completed": True,
                "project_status":
                    "completed",
            }

        handlers = ProjectLifecycleHandlers(
            get_project=
                lambda **kwargs:
                    project,
            is_funded=
                lambda **kwargs:
                    True,
            plan=
                lambda **kwargs: {},
            market=
                lambda **kwargs: {},
            contract=
                lambda **kwargs: {},
            delegation=
                lambda **kwargs: {},
            execution=
                lambda **kwargs:
                    SimpleNamespace(
                        review_ids=[],
                        execution_attempts=0,
                        failed_contract_ids=[],
                    ),
            qa=
                lambda **kwargs:
                    SimpleNamespace(
                        qa_attempts=0,
                        retry_execution_attempts=0,
                        qa_passed=0,
                        qa_failed=0,
                        completed_contract_ids=[],
                        failed_contract_ids=[],
                    ),
            integration=integration,
            active_contracts=
                lambda **kwargs: [],
            emit=
                lambda **kwargs: None,
            final_review=
                final_review,
        )

        state = run_project_lifecycle(
            db=MagicMock(),
            project_id=project.id,
            handlers=handlers,
        )

        self.assertEqual(
            review_calls,
            [project.id],
        )

        self.assertEqual(
            state["current_stage"],
            "completed",
        )

        self.assertEqual(
            state["final_review_status"],
            "approved",
        )


if __name__ == "__main__":
    unittest.main()
