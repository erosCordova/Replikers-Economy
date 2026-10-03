from __future__ import annotations

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

from sqlalchemy import create_engine
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
from app.models.task import Task
from app.models.user import User
from app.services.project_lifecycle_service import (
    finalize_project_if_ready,
)


LIFECYCLE_MODULE = (
    "app.services."
    "project_lifecycle_service"
)


class Phase13A210FinalReviewGateTests(
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
            email="cliente@final.test",
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.owner = User(
            full_name="Ecosistema",
            email="owner@final.test",
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
            description="Revisión final.",
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

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def create_project(
        self,
        *,
        with_final_gate: bool,
    ):
        project = Project(
            client_id=self.client.id,
            title="Proyecto",
            description="Proyecto final.",
            status="contracted",
            currency="PEN",
            budget_limit_cents=10000,
        )

        self.db.add(
            project
        )

        self.db.flush()

        task = Task(
            project_id=project.id,
            title="Entrega",
            description="Entrega completa.",
            status="completed",
            max_budget_cents=1000,
            required_specialty=
                "Backend Developer",
        )

        self.db.add(
            task
        )

        self.db.flush()

        requirement = None

        if with_final_gate:
            requirement = (
                ProjectSpecialistRequirement(
                    project_id=project.id,
                    specialty=
                        "Final Reviewer",
                    reason=(
                        "Validar entrega final."
                    ),
                    is_mandatory=True,
                    is_final_gate=True,
                    coverage_status="covered",
                    assigned_repliker_id=
                        self.vera.id,
                )
            )

            self.db.add(
                requirement
            )

            self.db.flush()

            self.db.add(
                ProjectSpecialistOffer(
                    project_id=project.id,
                    requirement_id=
                        requirement.id,
                    repliker_id=self.vera.id,
                    status="accepted",
                    confidence_score=100,
                    message="Acepto.",
                    reasoning="Disponible.",
                    responded_at=datetime.now(
                        timezone.utc
                    ),
                )
            )

        self.db.commit()

        return (
            project,
            requirement,
        )

    def test_legacy_project_can_still_finalize(
        self,
    ):
        project, _ = self.create_project(
            with_final_gate=False
        )

        with patch(
            f"{LIFECYCLE_MODULE}."
            "finalize_project_economy"
        ) as economy:
            result = (
                finalize_project_if_ready(
                    db=self.db,
                    project_id=project.id,
                )
            )

        self.assertTrue(
            result["completed"]
        )

        self.assertEqual(
            project.status,
            "completed",
        )

        economy.assert_called_once()

    def test_project_waits_without_final_review(
        self,
    ):
        project, _ = self.create_project(
            with_final_gate=True
        )

        with patch(
            f"{LIFECYCLE_MODULE}."
            "finalize_project_economy"
        ) as economy:
            result = (
                finalize_project_if_ready(
                    db=self.db,
                    project_id=project.id,
                )
            )

        self.assertFalse(
            result["completed"]
        )

        self.assertTrue(
            result[
                "final_review_required"
            ]
        )

        self.assertEqual(
            result[
                "final_review_status"
            ],
            "pending",
        )

        self.assertEqual(
            project.status,
            "awaiting_final_review",
        )

        economy.assert_not_called()

    def test_wrong_reviewer_approval_is_ignored(
        self,
    ):
        project, requirement = (
            self.create_project(
                with_final_gate=True
            )
        )

        other = Repliker(
            owner_id=self.owner.id,
            name="Otro",
            specialty="Final Reviewer",
            description="Otro revisor.",
            status="available",
            reputation_score=80,
            base_price_credits=100,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=5,
            is_active=True,
        )

        self.db.add(
            other
        )

        self.db.flush()

        self.db.add(
            ProjectFinalReview(
                project_id=project.id,
                requirement_id=
                    requirement.id,
                reviewer_repliker_id=
                    other.id,
                attempt_number=1,
                status="approved",
                score=100,
                summary="Aprobado.",
                completed_at=datetime.now(
                    timezone.utc
                ),
            )
        )

        self.db.commit()

        with patch(
            f"{LIFECYCLE_MODULE}."
            "finalize_project_economy"
        ) as economy:
            result = (
                finalize_project_if_ready(
                    db=self.db,
                    project_id=project.id,
                )
            )

        self.assertFalse(
            result["completed"]
        )

        economy.assert_not_called()

    def test_corrections_block_completion(
        self,
    ):
        project, requirement = (
            self.create_project(
                with_final_gate=True
            )
        )

        self.db.add(
            ProjectFinalReview(
                project_id=project.id,
                requirement_id=
                    requirement.id,
                reviewer_repliker_id=
                    self.vera.id,
                attempt_number=1,
                status=
                    "corrections_requested",
                score=70,
                summary=(
                    "Se requieren correcciones."
                ),
                corrections_json=(
                    '[{"detalle": '
                    '"Corregir entrega."}]'
                ),
                completed_at=datetime.now(
                    timezone.utc
                ),
            )
        )

        self.db.commit()

        with patch(
            f"{LIFECYCLE_MODULE}."
            "finalize_project_economy"
        ) as economy:
            result = (
                finalize_project_if_ready(
                    db=self.db,
                    project_id=project.id,
                )
            )

        self.assertFalse(
            result["completed"]
        )

        self.assertEqual(
            result[
                "final_review_status"
            ],
            "corrections_requested",
        )

        self.assertEqual(
            project.status,
            "corrections_requested",
        )

        economy.assert_not_called()

    def test_approved_review_allows_completion(
        self,
    ):
        project, requirement = (
            self.create_project(
                with_final_gate=True
            )
        )

        review = ProjectFinalReview(
            project_id=project.id,
            requirement_id=
                requirement.id,
            reviewer_repliker_id=
                self.vera.id,
            attempt_number=1,
            status="approved",
            score=98,
            summary=(
                "Proyecto aprobado "
                "para entrega."
            ),
            completed_at=datetime.now(
                timezone.utc
            ),
        )

        self.db.add(
            review
        )

        self.db.commit()

        with patch(
            f"{LIFECYCLE_MODULE}."
            "finalize_project_economy"
        ) as economy:
            result = (
                finalize_project_if_ready(
                    db=self.db,
                    project_id=project.id,
                )
            )

        self.assertTrue(
            result["completed"]
        )

        self.assertEqual(
            result[
                "final_review_id"
            ],
            review.id,
        )

        self.assertEqual(
            project.status,
            "completed",
        )

        economy.assert_called_once()

    def test_graph_waits_for_final_review(
        self,
    ):
        project = SimpleNamespace(
            id=88,
            status="awaiting_final_review",
            payment_status="funded",
        )

        def integration(**kwargs):
            _ = kwargs

            project.status = (
                "awaiting_final_review"
            )

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

        handlers = (
            ProjectLifecycleHandlers(
                get_project=
                    lambda **kwargs:
                        project,
                is_funded=
                    lambda **kwargs: True,
                plan=
                    lambda **kwargs: {},
                market=
                    lambda **kwargs: {},
                contract=
                    lambda **kwargs: {},
                delegation=
                    lambda **kwargs: {},
                execution=
                    lambda **kwargs: (
                        SimpleNamespace(
                            review_ids=[],
                            execution_attempts=0,
                            failed_contract_ids=[],
                        )
                    ),
                qa=
                    lambda **kwargs: (
                        SimpleNamespace(
                            qa_attempts=0,
                            retry_execution_attempts=0,
                            qa_passed=0,
                            qa_failed=0,
                            completed_contract_ids=[],
                            failed_contract_ids=[],
                        )
                    ),
                integration=integration,
                active_contracts=
                    lambda **kwargs: [],
                emit=
                    lambda **kwargs: None,
            )
        )

        state = run_project_lifecycle(
            db=MagicMock(),
            project_id=project.id,
            handlers=handlers,
        )

        self.assertEqual(
            state["current_stage"],
            "awaiting_final_review",
        )

        self.assertEqual(
            state["next_action"],
            "run_final_review",
        )

        self.assertEqual(
            state["final_review_status"],
            "pending",
        )


if __name__ == "__main__":
    unittest.main()
