from pathlib import Path
import unittest


class Phase24SubcontractExecutionTests(
    unittest.TestCase
):

    def test_subcontract_execution_service_exists(
        self,
    ):
        source = Path(
            "app/services/"
            "subcontract_execution_service.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "def run_subcontract_execution(",
            source,
        )

        self.assertIn(
            "build_execution_workspace_tools",
            source,
        )

        self.assertIn(
            "execution_system_prompt",
            source,
        )

        self.assertIn(
            'subcontract.status = "completed"',
            source,
        )

        self.assertIn(
            'delegated_task.status = "completed"',
            source,
        )

    def test_lifecycle_runs_subcontracts_first(
        self,
    ):
        source = Path(
            "app/services/"
            "project_lifecycle_service.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "run_subcontract_execution(",
            source,
        )

        self.assertIn(
            "ACTIVE_SUBCONTRACT_STATUSES",
            source,
        )

        self.assertIn(
            "delegated_executed",
            source,
        )


if __name__ == "__main__":
    unittest.main()
