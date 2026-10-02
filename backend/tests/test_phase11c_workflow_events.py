from __future__ import annotations

import unittest

from types import SimpleNamespace

from app.agentic.project_graph import (
    DEFAULT_HANDLERS,
    ProjectLifecycleHandlers,
    run_project_lifecycle,
)
from app.services.project_lifecycle_service import (
    ExecutionStageResult,
    QAStageResult,
)
from app.services.realtime_service import (
    record_workflow_event,
)


class FakeDB:
    pass


class Phase11CWorkflowEventsTests(
    unittest.TestCase
):
    def build_runtime(
        self,
        *,
        events: list[dict],
        execution_failure: bool = False,
    ):
        project = SimpleNamespace(
            id=77,
            status="draft",
            payment_status="unpaid",
        )

        def get_project(
            *,
            db,
            project_id,
        ):
            _ = db

            self.assertEqual(
                project_id,
                project.id,
            )

            return project

        def is_funded(
            *,
            db,
            project,
        ):
            _ = db

            return (
                project.payment_status
                == "escrowed"
            )

        def plan(
            *,
            db,
            project_id,
        ):
            _ = (
                db,
                project_id,
            )

            project.status = "planned"

            return {
                "tasks_created": 1,
            }

        def market(
            *,
            db,
            project_id,
        ):
            _ = (
                db,
                project_id,
            )

            project.status = (
                "market_open"
            )

            project.payment_status = (
                "escrowed"
            )

            return {
                "new_decisions": 2,
                "bid_count": 1,
            }

        def contract(
            *,
            db,
            project_id,
        ):
            _ = (
                db,
                project_id,
            )

            project.status = (
                "contracted"
            )

            return {
                "contracts_created": 1,
                "contract_ids": [101],
            }

        def active_contracts(
            *,
            db,
            project_id,
        ):
            _ = (
                db,
                project_id,
            )

            return [
                101
            ]

        def delegation(
            *,
            db,
            contract_ids,
        ):
            _ = (
                db,
                contract_ids,
            )

            return {
                "processed": 1,
                "delegated": 1,
            }

        def execution(
            *,
            db,
            contract_ids,
        ):
            _ = (
                db,
                contract_ids,
            )

            if execution_failure:
                raise RuntimeError(
                    "execution probe"
                )

            return ExecutionStageResult(
                review_ids=[
                    201
                ],
                execution_attempts=1,
                failed_contract_ids=[],
            )

        def qa(
            *,
            db,
            contract_ids,
        ):
            _ = (
                db,
                contract_ids,
            )

            return QAStageResult(
                qa_attempts=2,
                retry_execution_attempts=1,
                qa_passed=1,
                qa_failed=0,
                completed_contract_ids=[
                    101
                ],
                failed_contract_ids=[],
            )

        def integration(
            *,
            db,
            project_id,
        ):
            _ = (
                db,
                project_id,
            )

            project.status = "completed"
            project.payment_status = (
                "settled"
            )

            return {
                "completed": True,
                "total_tasks": 1,
                "completed_tasks": 1,
                "project_status":
                    "completed",
            }

        def emit(
            **kwargs,
        ):
            events.append(
                dict(kwargs)
            )

            # None evita que FakeDB necesite
            # implementar commit().
            return None

        handlers = (
            ProjectLifecycleHandlers(
                get_project=
                    get_project,
                is_funded=
                    is_funded,
                plan=plan,
                market=market,
                contract=contract,
                delegation=
                    delegation,
                execution=
                    execution,
                qa=qa,
                integration=
                    integration,
                active_contracts=
                    active_contracts,
                emit=emit,
            )
        )

        return (
            project,
            handlers,
        )

    def test_full_workflow_emits_stage_events(
        self,
    ):
        events: list[dict] = []

        project, handlers = (
            self.build_runtime(
                events=events,
            )
        )

        state = run_project_lifecycle(
            db=FakeDB(),
            project_id=
                project.id,
            handlers=handlers,
        )

        self.assertEqual(
            state[
                "current_stage"
            ],
            "completed",
        )

        started = [
            event["stage"]
            for event in events
            if (
                event["status"]
                == "started"
            )
        ]

        self.assertEqual(
            started,
            [
                "inspect",
                "planning",
                "market",
                "funding",
                "contracting",
                "delegation",
                "execution",
                "qa",
                "integration",
            ],
        )

        completed = [
            event["stage"]
            for event in events
            if (
                event["status"]
                == "completed"
                and event["kind"]
                == "workflow"
                and event["stage"]
                != "retry"
            )
        ]

        self.assertEqual(
            completed,
            started,
        )

    def test_retry_event_emitted(
        self,
    ):
        events: list[dict] = []

        project, handlers = (
            self.build_runtime(
                events=events,
            )
        )

        run_project_lifecycle(
            db=FakeDB(),
            project_id=
                project.id,
            handlers=handlers,
        )

        retry_events = [
            event
            for event in events
            if (
                event["stage"]
                == "retry"
                and event["status"]
                == "completed"
            )
        ]

        self.assertEqual(
            len(retry_events),
            1,
        )

        self.assertEqual(
            retry_events[0][
                "payload"
            ][
                "retry_attempts"
            ],
            1,
        )

    def test_economy_settled_event(
        self,
    ):
        events: list[dict] = []

        project, handlers = (
            self.build_runtime(
                events=events,
            )
        )

        run_project_lifecycle(
            db=FakeDB(),
            project_id=
                project.id,
            handlers=handlers,
        )

        economy_events = [
            event
            for event in events
            if (
                event["kind"]
                == "economy"
                and event["stage"]
                == "economy"
                and event["status"]
                == "settled"
            )
        ]

        self.assertEqual(
            len(economy_events),
            1,
        )

        self.assertEqual(
            economy_events[0][
                "payload"
            ][
                "payment_status"
            ],
            "settled",
        )

    def test_failure_event_emitted(
        self,
    ):
        events: list[dict] = []

        project, handlers = (
            self.build_runtime(
                events=events,
                execution_failure=True,
            )
        )

        with self.assertRaises(
            RuntimeError
        ):
            run_project_lifecycle(
                db=FakeDB(),
                project_id=
                    project.id,
                handlers=handlers,
            )

        failures = [
            event
            for event in events
            if (
                event["stage"]
                == "execution"
                and event["status"]
                == "failed"
            )
        ]

        self.assertEqual(
            len(failures),
            1,
        )

        self.assertIn(
            "execution probe",
            failures[0][
                "payload"
            ][
                "error"
            ],
        )

    def test_default_runtime_uses_realtime_emitter(
        self,
    ):
        self.assertIs(
            DEFAULT_HANDLERS.emit,
            record_workflow_event,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
