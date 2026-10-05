from __future__ import annotations

import unittest

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.api.routes.projects import (
    create_project,
)
from app.models.project import Project
from app.schemas.project import ProjectCreate
from app.services.economy_service import (
    EconomyError,
    project_has_sufficient_custody,
    required_project_funding_cents,
    simulate_project_funding,
    sync_project_payment_status,
)


class FakeProjectDatabase:
    def __init__(self):
        self.project = None
        self.commits = 0
        self.flushes = 0

    def add(self, item):
        if isinstance(
            item,
            Project,
        ):
            self.project = item

    def flush(self):
        self.flushes += 1

        if (
            self.project is not None
            and self.project.id is None
        ):
            self.project.id = 101

    def commit(self):
        self.commits += 1

    def scalar(self, statement):
        del statement

        return self.project


class Phase24AdminFreeProjectsTests(
    unittest.TestCase
):
    def _payload(self):
        return ProjectCreate(
            title="Proyecto de prueba",
            description=(
                "Proyecto suficientemente "
                "descrito para las pruebas."
            ),
            currency="PEN",
            budget_limit_cents=50000,
            requirements=[],
        )

    def test_admin_project_is_created_free(
        self,
    ):
        db = FakeProjectDatabase()

        project = create_project(
            payload=self._payload(),
            db=db,
            current_user=
                SimpleNamespace(
                    id=7,
                    role="admin",
                ),
        )

        self.assertTrue(
            project.is_admin_free
        )

        self.assertEqual(
            project.payment_status,
            "admin_free",
        )

        self.assertEqual(
            project.budget_limit_cents,
            50000,
        )

    def test_normal_user_project_is_not_free(
        self,
    ):
        db = FakeProjectDatabase()

        project = create_project(
            payload=self._payload(),
            db=db,
            current_user=
                SimpleNamespace(
                    id=8,
                    role="user",
                ),
        )

        self.assertFalse(
            project.is_admin_free
        )

        self.assertEqual(
            project.payment_status,
            "unpaid",
        )

    def test_admin_free_requires_zero_funding(
        self,
    ):
        project = SimpleNamespace(
            is_admin_free=True,
            quoted_amount_cents=45000,
            budget_limit_cents=50000,
        )

        self.assertEqual(
            required_project_funding_cents(
                project
            ),
            0,
        )

    def test_admin_free_is_considered_funded(
        self,
    ):
        project = SimpleNamespace(
            id=11,
            is_admin_free=True,
        )

        db = MagicMock()

        self.assertTrue(
            project_has_sufficient_custody(
                db=db,
                project=project,
            )
        )

    def test_admin_free_payment_status_is_stable(
        self,
    ):
        project = SimpleNamespace(
            id=11,
            is_admin_free=True,
            payment_status="unpaid",
        )

        db = MagicMock()

        status = (
            sync_project_payment_status(
                db=db,
                project=project,
            )
        )

        self.assertEqual(
            status,
            "admin_free",
        )

        self.assertEqual(
            project.payment_status,
            "admin_free",
        )

        db.flush.assert_called_once()

    def test_admin_free_rejects_simulated_funding(
        self,
    ):
        project = SimpleNamespace(
            id=11,
            is_admin_free=True,
        )

        db = MagicMock()
        db.scalar.return_value = project

        with self.assertRaises(
            EconomyError
        ) as context:
            simulate_project_funding(
                db=db,
                project_id=11,
                idempotency_key=
                    "admin-free-test",
                initiated_by_user_id=1,
            )

        self.assertIn(
            "no requieren",
            str(
                context.exception
            ),
        )


if __name__ == "__main__":
    unittest.main()
