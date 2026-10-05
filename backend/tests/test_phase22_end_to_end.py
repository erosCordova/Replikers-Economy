from __future__ import annotations

import unittest

import app.models  # noqa: F401

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agentic.client_correction_runtime import (
    ClientCorrectionItem,
    ClientCorrectionPlan,
)
from app.database.base import Base
from app.models.project import Project
from app.models.project_specialist import (
    ProjectFinalReview,
)
from app.models.task import Task
from app.services.client_correction_cycle_service import (
    run_client_correction_cycle,
)
from app.services.client_correction_service import (
    prepare_client_correction_review,
)
from app.services.project_delivery_service import (
    submit_delivery_decision,
)
from app.services.project_version_service import (
    build_delivery_version_history,
)


class Phase22EndToEndTests(
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

        self.project = Project(
            client_id=1,
            title="Proyecto integral Fase 22",
            description=(
                "Proyecto utilizado para "
                "probar el ciclo completo."
            ),
            status="completed",
            currency="PEN",
            budget_limit_cents=100000,
            quoted_amount_cents=80000,
            payment_status="settled",
        )

        self.db.add(
            self.project
        )

        self.db.flush()

        self.task = Task(
            project_id=
                self.project.id,

            title=
                "Panel principal",

            description=(
                "Implementar el panel "
                "principal."
            ),

            required_specialty=
                "Frontend Developer",

            status="completed",

            complexity=50,

            max_budget_cents=30000,
        )

        self.db.add(
            self.task
        )

        self.db.flush()

        self.initial_review = (
            ProjectFinalReview(
                project_id=
                    self.project.id,

                requirement_id=100,

                reviewer_repliker_id=200,

                attempt_number=1,

                status="approved",

                score=94,

                summary=(
                    "Primera versión "
                    "aprobada por Vera."
                ),

                corrections_json="[]",

                reasoning=(
                    "Entrega técnicamente "
                    "aprobada."
                ),
            )
        )

        self.db.add(
            self.initial_review
        )

        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def planner(
        self,
        **kwargs,
    ):
        _ = kwargs

        return ClientCorrectionPlan(
            summary=(
                "Corregir el panel "
                "principal."
            ),

            corrections=[
                ClientCorrectionItem(
                    task_id=
                        self.task.id,

                    instruction=(
                        "Actualizar el panel "
                        "principal según "
                        "la observación "
                        "del cliente."
                    ),

                    severity="medium",
                )
            ],
        )

    def test_complete_client_correction_flow(
        self,
    ):
        decision = (
            submit_delivery_decision(
                db=self.db,
                project=self.project,
                decision=(
                    "corrections_requested"
                ),
                comment=(
                    "Quiero ajustar "
                    "el panel principal."
                ),
                review_attempt=1,
            )
        )

        self.assertEqual(
            decision["decision"],
            "corrections_requested",
        )

        prepared = (
            prepare_client_correction_review(
                db=self.db,
                project=self.project,
                client_request=(
                    "Quiero ajustar "
                    "el panel principal."
                ),
                source_review_attempt=1,
                planner=self.planner,
            )
        )

        self.db.commit()

        self.assertTrue(
            prepared["created"]
        )

        self.assertEqual(
            prepared["attempt_number"],
            2,
        )

        self.assertEqual(
            self.project.status,
            "corrections_requested",
        )

        def lifecycle_runner(
            *,
            db,
            project_id,
        ):
            project = db.get(
                Project,
                project_id,
            )

            new_review = (
                ProjectFinalReview(
                    project_id=
                        project.id,

                    requirement_id=
                        self.initial_review
                        .requirement_id,

                    reviewer_repliker_id=
                        self.initial_review
                        .reviewer_repliker_id,

                    attempt_number=3,

                    status="approved",

                    score=98,

                    summary=(
                        "Nueva versión "
                        "aprobada por Vera."
                    ),

                    corrections_json="[]",

                    reasoning=(
                        "Correcciones "
                        "verificadas."
                    ),
                )
            )

            db.add(
                new_review
            )

            project.status = (
                "completed"
            )

            db.commit()

            return {
                "current_stage":
                    "completed",

                "next_action":
                    "none",

                "final_review_status":
                    "approved",

                "final_review_id":
                    new_review.id,
            }

        cycle = (
            run_client_correction_cycle(
                db=self.db,
                project_id=
                    self.project.id,
                runner=
                    lifecycle_runner,
            )
        )

        self.assertTrue(
            cycle["completed"]
        )

        self.assertEqual(
            cycle["status"],
            "completed",
        )

        history = (
            build_delivery_version_history(
                db=self.db,
                project_id=
                    self.project.id,
            )
        )

        self.assertEqual(
            history["versions_total"],
            2,
        )

        self.assertEqual(
            history["current_version"],
            "v1.1",
        )

        first = history["items"][0]
        current = history["items"][1]

        self.assertEqual(
            first["version"],
            "v1.0",
        )

        self.assertEqual(
            first["review_attempt"],
            1,
        )

        self.assertEqual(
            first["client_decision"],
            "corrections_requested",
        )

        self.assertEqual(
            current["version"],
            "v1.1",
        )

        self.assertEqual(
            current["review_attempt"],
            3,
        )

        self.assertEqual(
            current["client_decision"],
            "pending",
        )

        self.assertTrue(
            current["is_current"]
        )


if __name__ == "__main__":
    unittest.main()
