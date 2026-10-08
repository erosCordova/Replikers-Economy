from pathlib import Path
from types import SimpleNamespace
import inspect
import unittest
from unittest.mock import (
    MagicMock,
    patch,
)

from app.agentic.execution_tools import (
    build_execution_workspace_tools,
)
from app.execution.tool_gateway import (
    ToolGateway,
)
from app.services.workspace_service import (
    log_tool_execution,
)


class DelegatedLogAttributionTests(
    unittest.TestCase
):

    def test_log_can_override_workspace_owner(
        self,
    ):
        db = MagicMock()

        workspace = SimpleNamespace(
            id=1,
            contract_id=5,
            repliker_id=8,
        )

        log_tool_execution(
            db=db,
            workspace=workspace,
            actor_repliker_id=9,
            tool_name="workspace_read_text",
            status="success",
        )

        row = (
            db.add.call_args
            .args[0]
        )

        self.assertEqual(
            9,
            row.repliker_id,
        )

        self.assertEqual(
            5,
            row.contract_id,
        )

        self.assertEqual(
            1,
            row.workspace_id,
        )

    def test_default_keeps_workspace_owner(
        self,
    ):
        db = MagicMock()

        workspace = SimpleNamespace(
            id=1,
            contract_id=5,
            repliker_id=8,
        )

        log_tool_execution(
            db=db,
            workspace=workspace,
            tool_name="workspace_read_text",
            status="success",
        )

        row = (
            db.add.call_args
            .args[0]
        )

        self.assertEqual(
            8,
            row.repliker_id,
        )

    def test_gateway_propagates_actor(
        self,
    ):
        db = MagicMock()

        workspace = SimpleNamespace(
            id=1,
            contract_id=5,
            repliker_id=8,
        )

        gateway = ToolGateway(
            db=db,
            workspace=workspace,
            actor_repliker_id=9,
        )

        with (
            patch(
                "app.execution.tool_gateway."
                "list_workspace_files",
                return_value=[],
            ),
            patch(
                "app.execution.tool_gateway."
                "log_tool_execution",
            ) as mocked_log,
        ):
            result = gateway.list_files()

        self.assertEqual(
            [],
            result,
        )

        self.assertEqual(
            9,
            mocked_log.call_args
            .kwargs["actor_repliker_id"],
        )

    def test_tool_builder_accepts_actor(
        self,
    ):
        signature = inspect.signature(
            build_execution_workspace_tools
        )

        self.assertIn(
            "actor_repliker_id",
            signature.parameters,
        )

    def test_subcontract_uses_real_actor(
        self,
    ):
        source = Path(
            "app/services/"
            "subcontract_execution_service.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "actor_repliker_id=",
            source,
        )

        self.assertIn(
            "repliker.id",
            source,
        )

        self.assertGreaterEqual(
            source.count(
                "actor_repliker_id="
            ),
            4,
        )


if __name__ == "__main__":
    unittest.main()
