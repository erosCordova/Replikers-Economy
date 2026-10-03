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
    func,
    select,
)
from sqlalchemy.orm import Session

from app.agentic.project_graph import (
    ProjectLifecycleHandlers,
    run_project_lifecycle,
)
from app.database.base import Base
from app.models.contract import (
    TaskContract,
)
from app.models.execution import (
    ExecutionArtifact,
    ExecutionWorkspace,
)
from app.models.project import Project
from app.models.project_specialist import (
    ProjectFinalCorrectionRun,
    ProjectFinalReview,
    ProjectSpecialistOffer,
    ProjectSpecialistRequirement,
)
from app.models.qa import (
    QACriterionResult,
    QAReview,
)
from app.models.repliker import Repliker
from app.models.task import (
    Task,
    TaskAcceptanceCriterion,
    TaskBid,
)
from app.models.user import User
from app.schemas.final_review import (
    FinalReviewDecisionAI,
)
from app.services.final_review_correction_service import (
    run_final_review_corrections,
)
from app.services.final_review_service import (
    run_project_final_review,
)
from app.services.qa_service import (
    get_latest_qa_review,
)


LIFECYCLE_MODULE = (
    "app.services."
    "project_lifecycle_service"
)


class Phase13FinalCorrectionsTests(
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
            email="cliente@correccion.test",
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.owner = User(
            full_name="Ecosistema",
            email="owner@correccion.test",
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

        self.worker = Repliker(
            owner_id=self.owner.id,
            name="Bruno",
            specialty="Backend Developer",
            description=(
                "Desarrollo de servidor."
            ),
            status="available",
            reputation_score=90,
            base_price_credits=100,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=8,
            is_active=True,
        )

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

        self.db.add_all(
            [
                self.worker,
                self.vera,
            ]
        )

        self.db.flush()

        self.project = Project(
            client_id=self.client.id,
            title="Proyecto",
            description="Proyecto de prueba.",
            status="corrections_requested",
            currency="PEN",
            budget_limit_cents=10000,
            payment_status="funded",
        )

        self.db.add(
            self.project
        )

        self.db.flush()

        self.task = Task(
            project_id=self.project.id,
            title="Servidor",
            description=(
                "Implementar el servidor."
            ),
            status="completed",
            complexity=60,
            max_budget_cents=2000,
            required_specialty=
                "Backend Developer",
        )

        self.db.add(
            self.task
        )

        self.db.flush()

        self.criterion = (
            TaskAcceptanceCriterion(
                task_id=self.task.id,
                description=(
                    "El servidor debe "
                    "responder correctamente."
                ),
                status="passed",
                evidence="QA inicial aprobada.",
                is_mandatory=True,
            )
        )

        self.db.add(
            self.criterion
        )

        self.bid = TaskBid(
            task_id=self.task.id,
            repliker_id=self.worker.id,
            amount_cents=1000,
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
            repliker_id=self.worker.id,
            status="completed",
            currency="PEN",
            amount_cents=1000,
            reserved_cents=1000,
            skill_score=90,
            reputation_score=90,
            confidence_score=95,
            price_score=90,
            time_score=90,
            risk_score=90,
            selection_score=92,
            selected_by="r00",
            selection_policy_version=
                "r00-selection-v1",
            selection_summary="Seleccionado.",
        )

        self.db.add(
            self.contract
        )

        self.db.flush()

        self.workspace = ExecutionWorkspace(
            contract_id=self.contract.id,
            project_id=self.project.id,
            task_id=self.task.id,
            repliker_id=self.worker.id,
            status="ready",
            storage_driver="local",
            root_ref=(
                "tests/final-correction"
            ),
        )

        self.db.add(
            self.workspace
        )

        self.db.flush()

        self.artifact = ExecutionArtifact(
            workspace_id=self.workspace.id,
            relative_path="resultado.txt",
            media_type="text/plain",
            size_bytes=10,
            sha256="a" * 64,
        )

        self.db.add(
            self.artifact
        )

        previous_qa = QAReview(
            contract_id=self.contract.id,
            task_id=self.task.id,
            workspace_id=self.workspace.id,
            execution_repliker_id=
                self.worker.id,
            reviewer_repliker_id=None,
            attempt_number=1,
            status="passed",
            score=100,
            reviewer_type="langchain_qa",
            summary="QA inicial aprobada.",
            completed_at=datetime.now(
                timezone.utc
            ),
        )

        self.db.add(
            previous_qa
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
                message="Acepto.",
                reasoning="Disponible.",
                responded_at=datetime.now(
                    timezone.utc
                ),
            )
        )

        self.final_review = (
            ProjectFinalReview(
                project_id=self.project.id,
                requirement_id=
                    self.requirement.id,
                reviewer_repliker_id=
                    self.vera.id,
                attempt_number=1,
                status=
                    "corrections_requested",
                score=75,
                summary=(
                    "Se requiere una "
                    "corrección."
                ),
                corrections_json=json.dumps(
                    [
                        {
                            "task_id":
                                self.task.id,
                            "instruction": (
                                "Corrige la "
                                "validación final."
                            ),
                            "severity":
                                "high",
                        }
                    ]
                ),
                reasoning="Pendiente.",
                completed_at=datetime.now(
                    timezone.utc
                ),
            )
        )

        self.db.add(
            self.final_review
        )

        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def passing_qa(
        self,
        *,
        db,
        contract_id,
    ):
        review = (
            get_latest_qa_review(
                db=db,
                contract_id=contract_id,
            )
        )

        review.status = "passed"
        review.score = 100
        review.reviewer_type = (
            "langchain_qa"
        )
        review.summary = (
            "Corrección aprobada."
        )
        review.completed_at = (
            datetime.now(
                timezone.utc
            )
        )

        rows = list(
            db.scalars(
                select(
                    QACriterionResult
                )
                .where(
                    QACriterionResult.review_id
                    == review.id
                )
            ).all()
        )

        for row in rows:
            row.status = "passed"
            row.score = 100
            row.reason = (
                "Criterio corregido."
            )
            row.evidence_summary = (
                "Evidencia suficiente."
            )

        db.flush()

        return review

    def correction_executor(
        self,
        *,
        db,
        contract_id,
        instruction,
    ):
        self.transaction_states.append(
            db.in_transaction()
        )

        self.instructions.append(
            instruction
        )

        artifact = db.get(
            ExecutionArtifact,
            self.artifact.id,
        )

        artifact.sha256 = (
            "b" * 64
        )

        db.commit()

        return {
            "contract_id":
                contract_id,
            "status":
                "completed",
            "artifact_count":
                1,
            "artifacts": [],
        }

    def test_correction_returns_to_same_repliker(
        self,
    ):
        self.transaction_states = []
        self.instructions = []

        result = (
            run_final_review_corrections(
                db=self.db,
                project_id=self.project.id,
                executor=
                    self.correction_executor,
                qa_evaluator=
                    self.passing_qa,
            )
        )

        self.assertTrue(
            result[
                "ready_for_final_review"
            ]
        )

        self.assertEqual(
            self.transaction_states,
            [False],
        )

        self.assertIn(
            "Corrige la validación final.",
            self.instructions[0],
        )

        run = self.db.scalar(
            select(
                ProjectFinalCorrectionRun
            )
        )

        self.assertEqual(
            run.repliker_id,
            self.worker.id,
        )

        self.assertEqual(
            run.contract_id,
            self.contract.id,
        )

        self.assertEqual(
            run.status,
            "completed",
        )

        self.assertEqual(
            self.contract.status,
            "completed",
        )

        self.assertEqual(
            self.project.status,
            "awaiting_final_review",
        )

    def test_correction_does_not_create_new_contract(
        self,
    ):
        self.transaction_states = []
        self.instructions = []

        before = int(
            self.db.scalar(
                select(
                    func.count(
                        TaskContract.id
                    )
                )
            )
            or 0
        )

        run_final_review_corrections(
            db=self.db,
            project_id=self.project.id,
            executor=
                self.correction_executor,
            qa_evaluator=
                self.passing_qa,
        )

        after = int(
            self.db.scalar(
                select(
                    func.count(
                        TaskContract.id
                    )
                )
            )
            or 0
        )

        self.assertEqual(
            before,
            1,
        )

        self.assertEqual(
            after,
            1,
        )

    def test_completed_correction_is_not_executed_twice(
        self,
    ):
        self.transaction_states = []
        self.instructions = []

        run_final_review_corrections(
            db=self.db,
            project_id=self.project.id,
            executor=
                self.correction_executor,
            qa_evaluator=
                self.passing_qa,
        )

        first_calls = len(
            self.instructions
        )

        run_final_review_corrections(
            db=self.db,
            project_id=self.project.id,
            executor=
                self.correction_executor,
            qa_evaluator=
                self.passing_qa,
        )

        self.assertEqual(
            len(
                self.instructions
            ),
            first_calls,
        )

    def test_vera_can_review_again_after_correction(
        self,
    ):
        self.transaction_states = []
        self.instructions = []

        run_final_review_corrections(
            db=self.db,
            project_id=self.project.id,
            executor=
                self.correction_executor,
            qa_evaluator=
                self.passing_qa,
        )

        def evaluator(**kwargs):
            _ = kwargs

            return FinalReviewDecisionAI(
                decision="approve",
                score=100,
                summary=(
                    "La corrección quedó "
                    "aprobada."
                ),
                corrections=[],
                reasoning=(
                    "Entrega correcta."
                ),
            )

        with patch(
            f"{LIFECYCLE_MODULE}."
            "finalize_project_economy"
        ):
            result = (
                run_project_final_review(
                    db=self.db,
                    project_id=self.project.id,
                    evaluator=evaluator,
                )
            )

        self.assertEqual(
            result["status"],
            "approved",
        )

        self.assertEqual(
            result[
                "attempt_number"
            ],
            2,
        )

        self.assertEqual(
            self.project.status,
            "completed",
        )

    def test_graph_executes_corrections_before_vera(
        self,
    ):
        project = SimpleNamespace(
            id=77,
            status="corrections_requested",
            payment_status="funded",
        )

        calls: list[str] = []

        def corrections(**kwargs):
            _ = kwargs

            calls.append(
                "correcciones"
            )

            project.status = (
                "awaiting_final_review"
            )

            return {
                "ready_for_final_review":
                    True,
                "summary":
                    "Correcciones verificadas.",
            }

        def final_review(**kwargs):
            _ = kwargs

            calls.append(
                "vera"
            )

            project.status = "completed"

            return {
                "review_id": 2,
                "reviewer_id": 15,
                "attempt_number": 2,
                "status": "approved",
                "score": 100,
                "summary":
                    "Proyecto aprobado.",
                "corrections": [],
                "completed": True,
                "project_status":
                    "completed",
            }

        handlers = (
            ProjectLifecycleHandlers(
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
                integration=
                    lambda **kwargs: {},
                active_contracts=
                    lambda **kwargs: [],
                emit=
                    lambda **kwargs: None,
                final_review=
                    final_review,
                corrections=
                    corrections,
            )
        )

        state = run_project_lifecycle(
            db=MagicMock(),
            project_id=project.id,
            handlers=handlers,
        )

        self.assertEqual(
            calls,
            [
                "correcciones",
                "vera",
            ],
        )

        self.assertEqual(
            state["current_stage"],
            "completed",
        )


if __name__ == "__main__":
    unittest.main()
