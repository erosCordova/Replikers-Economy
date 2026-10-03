from __future__ import annotations

import unittest

from types import SimpleNamespace
from unittest.mock import (
    MagicMock,
    patch,
)

from app.services.project_lifecycle_service import (
    run_contracting_stage,
    run_market_stage,
)


MODULE = (
    "app.services."
    "project_lifecycle_service"
)


class Phase13A29MarketLifecycleTests(
    unittest.TestCase
):
    def test_market_recruits_even_without_open_tasks(
        self,
    ):
        db = MagicMock()

        project = SimpleNamespace(
            id=31,
        )

        specialist_result = {
            "requirements_processed": 1,
            "candidates_considered": 1,
            "offers_sent": 1,
            "accepted": 1,
            "rejected": 0,
            "errors": [],
        }

        with (
            patch(
                f"{MODULE}.get_project",
                return_value=project,
            ),
            patch(
                f"{MODULE}."
                "_eligible_market_task_count",
                return_value=0,
            ),
            patch(
                f"{MODULE}."
                "_run_specialist_recruitment_stage",
                return_value=
                    specialist_result,
            ) as recruitment,
        ):
            result = run_market_stage(
                db=db,
                project_id=project.id,
            )

        recruitment.assert_called_once_with(
            db=db,
            project_id=project.id,
        )

        self.assertFalse(
            result["skipped"]
        )

        self.assertEqual(
            result[
                "tasks_processed"
            ],
            0,
        )

        self.assertEqual(
            result[
                "specialist_offers"
            ],
            1,
        )

        self.assertEqual(
            result[
                "specialist_accepted"
            ],
            1,
        )

    def test_market_skips_when_nothing_to_process(
        self,
    ):
        db = MagicMock()

        project = SimpleNamespace(
            id=32,
        )

        specialist_result = {
            "requirements_processed": 0,
            "candidates_considered": 0,
            "offers_sent": 0,
            "accepted": 0,
            "rejected": 0,
            "errors": [],
        }

        with (
            patch(
                f"{MODULE}.get_project",
                return_value=project,
            ),
            patch(
                f"{MODULE}."
                "_eligible_market_task_count",
                return_value=0,
            ),
            patch(
                f"{MODULE}."
                "_run_specialist_recruitment_stage",
                return_value=
                    specialist_result,
            ),
        ):
            result = run_market_stage(
                db=db,
                project_id=project.id,
            )

        self.assertTrue(
            result["skipped"]
        )

    def test_contracting_retries_specialist_recruitment(
        self,
    ):
        db = MagicMock()

        db.scalar.return_value = 0

        project = SimpleNamespace(
            id=41,
            status="partially_contracted",
        )

        coverage = SimpleNamespace(
            ready=True,
            mandatory_total=1,
            mandatory_covered=1,
            missing_specialties=(),
        )

        with (
            patch(
                f"{MODULE}.get_project",
                return_value=project,
            ),
            patch(
                f"{MODULE}.project_is_funded",
                return_value=True,
            ),
            patch(
                f"{MODULE}."
                "_run_specialist_recruitment_stage",
                return_value={
                    "requirements_processed": 1,
                    "candidates_considered": 1,
                    "offers_sent": 1,
                    "accepted": 1,
                    "rejected": 0,
                    "errors": [],
                },
            ) as recruitment,
            patch(
                f"{MODULE}.active_contract_ids",
                return_value=[101],
            ),
            patch(
                f"{MODULE}."
                "enforce_project_specialist_gate",
                return_value=coverage,
            ),
        ):
            result = run_contracting_stage(
                db=db,
                project_id=project.id,
            )

        recruitment.assert_called_once_with(
            db=db,
            project_id=project.id,
        )

        self.assertTrue(
            result[
                "specialist_coverage_ready"
            ]
        )

        self.assertEqual(
            result[
                "covered_specialists"
            ],
            1,
        )


if __name__ == "__main__":
    unittest.main()
