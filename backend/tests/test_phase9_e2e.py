from __future__ import annotations

import hashlib
import shutil
import unittest

from types import SimpleNamespace

from app.agentic.project_graph import (
    ProjectLifecycleHandlers,
    build_project_lifecycle_graph,
    run_project_lifecycle,
)
from app.main import app
from app.database.session import engine
from app.services.workspace_service import (
    read_workspace_file_bytes,
    workspace_root,
)


class FakeDB:
    pass


class Phase9LifecycleTests(
    unittest.TestCase
):
    def make_handlers(
        self,
        *,
        project,
        execution_fails=False,
        qa_fails=False,
    ):
        def get_project(
            *,
            db,
            project_id,
        ):
            self.assertEqual(
                project_id,
                project.id,
            )

            return project

        def plan(
            *,
            db,
            project_id,
        ):
            project.status = "planned"

            return {
                "tasks_created": 2,
            }

        def market(
            *,
            db,
            project_id,
        ):
            project.status = (
                "market_open"
            )

            return {
                "new_decisions": 4,
                "bid_count": 3,
            }

        def contract(
            *,
            db,
            project_id,
        ):
            project.status = (
                "contracted"
            )

            return {
                "contracts_created": 2,
                "contract_ids": [
                    101,
                    102,
                ],
            }

        def active_contracts(
            *,
            db,
            project_id,
        ):
            return [
                101,
                102,
            ]

        def delegation(
            *,
            db,
            contract_ids,
        ):
            self.assertEqual(
                contract_ids,
                [
                    101,
                    102,
                ],
            )

            return {
                "processed": 2,
                "delegated": 1,
            }

        def execution(
            *,
            db,
            contract_ids,
        ):
            return SimpleNamespace(
                review_ids=(
                    []
                    if execution_fails
                    else [
                        201,
                        202,
                    ]
                ),
                execution_attempts=2,
                failed_contract_ids=(
                    [101]
                    if execution_fails
                    else []
                ),
            )

        def qa(
            *,
            db,
            contract_ids,
        ):
            return SimpleNamespace(
                qa_attempts=2,
                retry_execution_attempts=1,
                qa_passed=(
                    1
                    if qa_fails
                    else 2
                ),
                qa_failed=(
                    1
                    if qa_fails
                    else 0
                ),
                completed_contract_ids=(
                    [101]
                    if qa_fails
                    else [
                        101,
                        102,
                    ]
                ),
                failed_contract_ids=(
                    [102]
                    if qa_fails
                    else []
                ),
            )

        def integration(
            *,
            db,
            project_id,
        ):
            project.status = (
                "completed"
            )

            return {
                "completed": True,
                "total_tasks": 2,
                "completed_tasks": 2,
                "project_status":
                    "completed",
            }

        return ProjectLifecycleHandlers(
            get_project=get_project,
            plan=plan,
            market=market,
            contract=contract,
            delegation=delegation,
            execution=execution,
            qa=qa,
            integration=integration,
            active_contracts=
                active_contracts,
        )

    def test_full_lifecycle(
        self,
    ):
        project = SimpleNamespace(
            id=9001,
            status="draft",
            payment_status="funded",
        )

        handlers = self.make_handlers(
            project=project
        )

        state = run_project_lifecycle(
            db=FakeDB(),
            project_id=project.id,
            handlers=handlers,
        )

        self.assertEqual(
            state["current_stage"],
            "completed",
        )

        self.assertEqual(
            state["project_status"],
            "completed",
        )

        self.assertEqual(
            state["contracts_created"],
            2,
        )

        self.assertEqual(
            state["contracts_completed"],
            2,
        )

        self.assertEqual(
            state[
                "delegations_processed"
            ],
            2,
        )

        self.assertEqual(
            state["execution_attempts"],
            3,
        )

        self.assertEqual(
            state["qa_attempts"],
            2,
        )

        self.assertEqual(
            state["qa_passed"],
            2,
        )

        self.assertEqual(
            state["qa_failed"],
            0,
        )

        self.assertEqual(
            state[
                "failed_contract_ids"
            ],
            [],
        )

    def test_waits_for_funding(
        self,
    ):
        project = SimpleNamespace(
            id=9002,
            status="planned",
            payment_status="unpaid",
        )

        handlers = self.make_handlers(
            project=project
        )

        state = run_project_lifecycle(
            db=FakeDB(),
            project_id=project.id,
            handlers=handlers,
        )

        self.assertEqual(
            state["current_stage"],
            "awaiting_funding",
        )

        self.assertEqual(
            state["next_action"],
            "await_funding",
        )

        self.assertTrue(
            state["blocked_reason"]
        )

    def test_resume_contracted_project(
        self,
    ):
        project = SimpleNamespace(
            id=9003,
            status="contracted",
            payment_status="funded",
        )

        handlers = self.make_handlers(
            project=project
        )

        state = run_project_lifecycle(
            db=FakeDB(),
            project_id=project.id,
            handlers=handlers,
        )

        self.assertEqual(
            state["current_stage"],
            "completed",
        )

        self.assertEqual(
            state[
                "delegations_processed"
            ],
            2,
        )

        self.assertEqual(
            state["qa_passed"],
            2,
        )

    def test_execution_failure_stops(
        self,
    ):
        project = SimpleNamespace(
            id=9004,
            status="contracted",
            payment_status="funded",
        )

        handlers = self.make_handlers(
            project=project,
            execution_fails=True,
        )

        state = run_project_lifecycle(
            db=FakeDB(),
            project_id=project.id,
            handlers=handlers,
        )

        self.assertEqual(
            state["current_stage"],
            "failed",
        )

        self.assertEqual(
            state[
                "failed_contract_ids"
            ],
            [101],
        )

        self.assertEqual(
            state["next_action"],
            "inspect_failure",
        )

    def test_qa_failure_stops(
        self,
    ):
        project = SimpleNamespace(
            id=9005,
            status="contracted",
            payment_status="funded",
        )

        handlers = self.make_handlers(
            project=project,
            qa_fails=True,
        )

        state = run_project_lifecycle(
            db=FakeDB(),
            project_id=project.id,
            handlers=handlers,
        )

        self.assertEqual(
            state["current_stage"],
            "failed",
        )

        self.assertEqual(
            state["qa_failed"],
            1,
        )

        self.assertEqual(
            state[
                "failed_contract_ids"
            ],
            [102],
        )

    def test_graph_contains_required_nodes(
        self,
    ):
        project = SimpleNamespace(
            id=9006,
            status="draft",
            payment_status="funded",
        )

        graph = (
            build_project_lifecycle_graph(
                db=FakeDB(),
                handlers=
                    self.make_handlers(
                        project=project
                    ),
            )
        )

        nodes = set(
            graph.get_graph().nodes
        )

        required = {
            "inspect",
            "planning",
            "market",
            "funding",
            "contracting",
            "delegation",
            "execution",
            "qa",
            "integration",
            "awaiting_funding",
            "already_completed",
            "failed",
        }

        self.assertTrue(
            required.issubset(
                nodes
            )
        )


class Phase9IntegrityTests(
    unittest.TestCase
):
    def test_real_sha256_changes(
        self,
    ):
        workspace = SimpleNamespace(
            root_ref=(
                "phase9-permanent-test"
            ),
            max_file_bytes=
                2_000_000,
        )

        root = workspace_root(
            workspace
        )

        try:
            target = (
                root
                / "artifact.txt"
            )

            original = (
                b"immutable evidence"
            )

            target.write_bytes(
                original
            )

            payload = (
                read_workspace_file_bytes(
                    workspace=workspace,
                    relative_path=
                        "artifact.txt",
                )
            )

            snapshot_sha = (
                hashlib.sha256(
                    payload
                )
                .hexdigest()
            )

            target.write_bytes(
                b"modified evidence"
            )

            modified = (
                read_workspace_file_bytes(
                    workspace=workspace,
                    relative_path=
                        "artifact.txt",
                )
            )

            actual_sha = (
                hashlib.sha256(
                    modified
                )
                .hexdigest()
            )

            self.assertNotEqual(
                snapshot_sha,
                actual_sha,
            )

        finally:
            shutil.rmtree(
                root,
                ignore_errors=True,
            )


class Phase9APITests(
    unittest.TestCase
):
    def test_required_routes_exist(
        self,
    ):
        paths = set(
            app.openapi()[
                "paths"
            ]
        )

        required = {
            (
                "/api/v1/agentic/"
                "projects/{project_id}/run"
            ),
            (
                "/api/v1/qa/contracts/"
                "{contract_id}/prepare"
            ),
        }

        self.assertTrue(
            required.issubset(
                paths
            )
        )


def tearDownModule():
    """
    Cierra explicitamente el pool SQLAlchemy
    utilizado al importar FastAPI durante
    las pruebas.
    """

    engine.dispose()


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
