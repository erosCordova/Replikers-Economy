from __future__ import annotations

import json
import unittest

import app.models  # noqa: F401

from sqlalchemy import (
    create_engine,
)
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
from app.services.client_correction_service import (
    ClientCorrectionPreparationError,
    prepare_client_correction_review,
)


class Phase22ClientCorrectionsTests(
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
            title="Clínica SaludVida",
            description=(
                "Sistema de gestión "
                "para una clínica."
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
                "Construir el panel "
                "principal del sistema."
            ),

            status=
                "completed",

            required_specialty=
                "Frontend Developer",

            complexity=50,

            max_budget_cents=30000,
        )

        self.db.add(
            self.task
        )

        self.db.flush()

        self.source_review = (
            ProjectFinalReview(
                project_id=
                    self.project.id,

                requirement_id=999,

                reviewer_repliker_id=999,

                attempt_number=1,

                status="approved",

                score=96,

                summary=(
                    "Entrega aprobada."
                ),

                corrections_json="[]",

                reasoning=(
                    "Revisión aprobada."
                ),
            )
        )

        self.db.add(
            self.source_review
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
                "Actualizar el panel."
            ),
            corrections=[
                ClientCorrectionItem(
                    task_id=
                        self.task.id,

                    instruction=(
                        "Ajustar el panel "
                        "principal según "
                        "la solicitud "
                        "del cliente."
                    ),

                    severity="medium",
                )
            ],
        )

    def test_client_request_creates_bridge(
        self,
    ):
        result = (
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
            result["created"]
        )

        self.assertEqual(
            self.project.status,
            "corrections_requested",
        )

        bridge = self.db.get(
            ProjectFinalReview,
            result["review_id"],
        )

        self.assertIsNotNone(
            bridge
        )

        self.assertEqual(
            bridge.status,
            "corrections_requested",
        )

        self.assertEqual(
            bridge.attempt_number,
            2,
        )

        corrections = json.loads(
            bridge.corrections_json
        )

        self.assertEqual(
            len(corrections),
            1,
        )

        self.assertEqual(
            corrections[0][
                "task_id"
            ],
            self.task.id,
        )

    def test_same_request_bridge_is_not_duplicated(
        self,
    ):
        first = (
            prepare_client_correction_review(
                db=self.db,
                project=self.project,
                client_request=(
                    "Cambiar el panel."
                ),
                source_review_attempt=1,
                planner=self.planner,
            )
        )

        self.db.commit()

        second = (
            prepare_client_correction_review(
                db=self.db,
                project=self.project,
                client_request=(
                    "Cambiar el panel."
                ),
                source_review_attempt=1,
                planner=self.planner,
            )
        )

        self.assertFalse(
            second["created"]
        )

        self.assertEqual(
            first["review_id"],
            second["review_id"],
        )

    def test_invalid_task_from_planner_is_rejected(
        self,
    ):
        def invalid_planner(
            **kwargs,
        ):
            _ = kwargs

            return ClientCorrectionPlan(
                summary=(
                    "Plan inválido."
                ),
                corrections=[
                    ClientCorrectionItem(
                        task_id=999999,
                        instruction=(
                            "Modificar una "
                            "tarea inexistente."
                        ),
                        severity="high",
                    )
                ],
            )

        with self.assertRaises(
            ClientCorrectionPreparationError
        ):
            prepare_client_correction_review(
                db=self.db,
                project=self.project,
                client_request=(
                    "Necesito un cambio."
                ),
                source_review_attempt=1,
                planner=invalid_planner,
            )


if __name__ == "__main__":
    unittest.main()
