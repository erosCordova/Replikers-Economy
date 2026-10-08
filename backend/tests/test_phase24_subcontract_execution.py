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

        self.assertIn(
            "subcontract_execution_agent_run",
            source,
        )

        self.assertIn(
            "principal_log_id",
            source,
        )

        self.assertIn(
            "subcontract_log_id",
            source,
        )


if __name__ == "__main__":
    unittest.main()



class Phase24SandboxUnavailableTests(
    unittest.TestCase
):
    def test_docker_unavailable_does_not_abort_agent(
        self,
    ):
        tools_source = Path(
            "app/agentic/execution_tools.py"
        ).read_text(
            encoding="utf-8"
        )

        runtime_source = Path(
            "app/agentic/execution_runtime.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "except SandboxError as exc:",
            tools_source,
        )

        self.assertIn(
            '"sandbox_available":',
            tools_source,
        )

        self.assertIn(
            "False,",
            tools_source,
        )

        self.assertIn(
            "sandbox_available=false",
            runtime_source,
        )

        self.assertIn(
            "No intentes evadir",
            runtime_source,
        )
