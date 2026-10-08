from pathlib import Path
import unittest
from unittest.mock import MagicMock

from app.agentic.execution_graph import (
    run_execution_graph,
)
from app.services.execution_agent_service import (
    _delegated_integration_verified,
)


class DelegatedIntegrationCompletionTests(
    unittest.TestCase
):

    def test_verified_integration_can_finish_without_new_write(
        self,
    ):
        def executor(state):
            return {
                "contract_id":
                    state["contract_id"],
                "status":
                    "completed",
                "artifact_count":
                    0,
                "artifacts":
                    [],
                "integration_verified":
                    True,
                "trace":
                    [],
            }

        result = run_execution_graph(
            contract_id=1,
            instruction="",
            executor=executor,
        )

        self.assertEqual(
            result["status"],
            "completed",
        )

        self.assertTrue(
            result[
                "integration_verified"
            ]
        )

    def test_normal_execution_still_needs_artifact(
        self,
    ):
        def executor(state):
            return {
                "contract_id":
                    state["contract_id"],
                "status":
                    "completed",
                "artifact_count":
                    0,
                "artifacts":
                    [],
                "integration_verified":
                    False,
                "trace":
                    [],
            }

        result = run_execution_graph(
            contract_id=1,
            instruction="",
            executor=executor,
        )

        self.assertEqual(
            result["status"],
            "needs_artifact",
        )

    def test_integration_uses_exact_principal_attempt(
        self,
    ):
        source = Path(
            "app/services/"
            "execution_agent_service.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "principal_run_log = "
            "log_tool_execution(",
            source,
        )

        self.assertIn(
            "principal_running_log_id = int(",
            source,
        )

        self.assertIn(
            "principal_running_log_id="
            "\n                    "
            "principal_running_log_id,",
            source,
        )

    def test_exact_attempt_bounds_principal_reads(
        self,
    ):
        db = MagicMock()

        db.scalar.side_effect = [
            # Subcontrato completado.
            1,

            # Delegacion completada antes
            # del intento principal actual.
            50,

            # El log exacto #70 existe.
            70,

            # Existe otro intento principal
            # posterior en #90.
            90,

            # Lectura del intento #70.
            80,
        ]

        verified = (
            _delegated_integration_verified(
                db=db,
                contract_id=5,
                workspace_id=1,
                baseline_artifact_count=4,
                principal_running_log_id=70,
                principal_repliker_id=8,
            )
        )

        self.assertTrue(
            verified
        )

        principal_query = (
            db.scalar
            .call_args_list[2]
            .args[0]
        )

        next_attempt_query = (
            db.scalar
            .call_args_list[3]
            .args[0]
        )

        read_query = (
            db.scalar
            .call_args_list[4]
            .args[0]
        )

        principal_sql = str(
            principal_query
        )

        self.assertIn(
            "tool_execution_logs.id",
            principal_sql,
        )

        self.assertIn(
            "tool_execution_logs.repliker_id",
            principal_sql,
        )

        principal_params = (
            principal_query
            .compile()
            .params
        )

        self.assertIn(
            70,
            principal_params.values(),
        )

        self.assertIn(
            8,
            principal_params.values(),
        )

        next_params = (
            next_attempt_query
            .compile()
            .params
        )

        self.assertIn(
            70,
            next_params.values(),
        )

        self.assertIn(
            8,
            next_params.values(),
        )

        read_params = (
            read_query
            .compile()
            .params
        )

        self.assertIn(
            70,
            read_params.values(),
        )

        self.assertIn(
            90,
            read_params.values(),
        )

        self.assertIn(
            8,
            read_params.values(),
        )

    def test_wrong_principal_attempt_is_rejected(
        self,
    ):
        db = MagicMock()

        db.scalar.side_effect = [
            # Subcontrato completado.
            1,

            # Delegacion completada.
            50,

            # El ID exacto recibido no
            # corresponde al principal.
            None,
        ]

        verified = (
            _delegated_integration_verified(
                db=db,
                contract_id=5,
                workspace_id=1,
                baseline_artifact_count=4,
                principal_running_log_id=70,
                principal_repliker_id=8,
            )
        )

        self.assertFalse(
            verified
        )

        self.assertEqual(
            db.scalar.call_count,
            3,
        )


if __name__ == "__main__":
    unittest.main()
