from __future__ import annotations

import unittest

import app.models  # noqa: F401

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models.project import Project
from app.services.client_correction_cycle_service import (
    run_client_correction_cycle,
)


class Phase22CorrectionCycleTests(
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
            title="Proyecto Fase 22",
            description=(
                "Proyecto para probar "
                "el ciclo de correcciones."
            ),
            status=(
                "corrections_requested"
            ),
            currency="PEN",
            payment_status="settled",
        )

        self.db.add(
            self.project
        )

        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_cycle_can_finish_project(
        self,
    ):
        def runner(
            *,
            db,
            project_id,
        ):
            project = db.get(
                Project,
                project_id,
            )

            project.status = "completed"

            db.commit()

            return {
                "current_stage":
                    "completed",

                "next_action":
                    "none",

                "final_review_status":
                    "approved",

                "final_review_id":
                    5,
            }

        result = (
            run_client_correction_cycle(
                db=self.db,
                project_id=
                    self.project.id,
                runner=runner,
            )
        )

        self.assertTrue(
            result["completed"]
        )

        self.assertEqual(
            result["status"],
            "completed",
        )

        self.assertEqual(
            result["cycles_count"],
            1,
        )

    def test_cycle_retries_when_vera_requests_more_changes(
        self,
    ):
        counter = {
            "value": 0
        }

        def runner(
            *,
            db,
            project_id,
        ):
            counter["value"] += 1

            project = db.get(
                Project,
                project_id,
            )

            if counter["value"] == 1:
                project.status = (
                    "corrections_requested"
                )

                final_status = (
                    "corrections_requested"
                )

            else:
                project.status = (
                    "completed"
                )

                final_status = (
                    "approved"
                )

            db.commit()

            return {
                "current_stage":
                    (
                        "corrections_requested"
                        if counter["value"]
                        == 1
                        else "completed"
                    ),

                "next_action":
                    (
                        "apply_corrections"
                        if counter["value"]
                        == 1
                        else "none"
                    ),

                "final_review_status":
                    final_status,

                "final_review_id":
                    counter["value"],
            }

        result = (
            run_client_correction_cycle(
                db=self.db,
                project_id=
                    self.project.id,
                runner=runner,
                max_cycles=3,
            )
        )

        self.assertTrue(
            result["completed"]
        )

        self.assertEqual(
            result["cycles_count"],
            2,
        )

        self.assertEqual(
            counter["value"],
            2,
        )

    def test_cycle_has_a_safety_limit(
        self,
    ):
        def runner(
            *,
            db,
            project_id,
        ):
            project = db.get(
                Project,
                project_id,
            )

            project.status = (
                "corrections_requested"
            )

            db.commit()

            return {
                "current_stage":
                    "corrections_requested",

                "next_action":
                    "apply_corrections",

                "final_review_status":
                    "corrections_requested",

                "final_review_id":
                    1,
            }

        result = (
            run_client_correction_cycle(
                db=self.db,
                project_id=
                    self.project.id,
                runner=runner,
                max_cycles=2,
            )
        )

        self.assertFalse(
            result["completed"]
        )

        self.assertEqual(
            result["status"],
            "needs_attention",
        )

        self.assertEqual(
            result["cycles_count"],
            2,
        )

    def test_cycle_failure_is_controlled(
        self,
    ):
        def runner(
            **kwargs,
        ):
            _ = kwargs

            raise RuntimeError(
                "Fallo simulado."
            )

        result = (
            run_client_correction_cycle(
                db=self.db,
                project_id=
                    self.project.id,
                runner=runner,
            )
        )

        self.assertFalse(
            result["completed"]
        )

        self.assertEqual(
            result["status"],
            "failed",
        )

        self.assertIn(
            "Fallo simulado",
            result["error"],
        )


if __name__ == "__main__":
    unittest.main()
