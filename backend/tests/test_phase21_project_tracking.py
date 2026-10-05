from __future__ import annotations

import unittest
from types import SimpleNamespace

import app.models  # noqa: F401

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes.projects import (
    _get_accessible_project,
    router,
)
from app.database.base import Base
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.schemas.project import (
    ProjectTrackingPublic,
)
from app.services.project_delivery_service import (
    DeliveryDecisionError,
    latest_delivery_decision,
    parse_delivery_message,
    submit_delivery_decision,
)
from app.services.project_tracking_service import (
    _progress_percent,
    build_project_tracking,
)


class Phase21ProjectTrackingTests(
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

        self.client = User(
            full_name="Cliente Fase 21",
            email="cliente21@test.local",
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.other_user = User(
            full_name="Otro Cliente",
            email="otro21@test.local",
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.admin = User(
            full_name="Administrador",
            email="admin21@test.local",
            password_hash="test",
            role="admin",
            is_active=True,
        )

        self.db.add_all(
            [
                self.client,
                self.other_user,
                self.admin,
            ]
        )

        self.db.flush()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def make_project(
        self,
        *,
        status: str = "draft",
    ) -> Project:
        project = Project(
            client_id=self.client.id,
            title="Clínica SaludVida",
            description=(
                "Sistema de gestión "
                "para una clínica."
            ),
            status=status,
            currency="PEN",
            budget_limit_cents=100000,
            quoted_amount_cents=80000,
            payment_status="unpaid",
        )

        self.db.add(project)
        self.db.flush()

        return project

    def make_task(
        self,
        *,
        project: Project,
        title: str,
        status: str = "planned",
    ) -> Task:
        task = Task(
            project_id=project.id,
            title=title,
            description=(
                f"Implementar {title}."
            ),
            required_specialty=(
                "Backend Developer"
            ),
            status=status,
            complexity=50,
            max_budget_cents=20000,
        )

        self.db.add(task)
        self.db.flush()

        return task

    def test_tracking_route_is_registered(
        self,
    ):
        paths = {
            route.path
            for route in router.routes
        }

        self.assertIn(
            "/projects/{project_id}/tracking",
            paths,
        )

        self.assertIn(
            "/projects/{project_id}/delivery-decision",
            paths,
        )

    def test_initial_tracking_uses_real_data(
        self,
    ):
        project = self.make_project(
            status="draft"
        )

        self.make_task(
            project=project,
            title="API de pacientes",
        )

        self.make_task(
            project=project,
            title="Panel clínico",
        )

        self.db.commit()

        tracking = build_project_tracking(
            db=self.db,
            project=project,
        )

        validated = (
            ProjectTrackingPublic
            .model_validate(
                tracking
            )
        )

        self.assertEqual(
            validated.project_id,
            project.id,
        )

        self.assertEqual(
            validated.stage,
            "planning",
        )

        self.assertEqual(
            validated.progress_percent,
            20,
        )

        self.assertEqual(
            validated.tasks.total,
            2,
        )

        self.assertEqual(
            validated.tasks.completed,
            0,
        )

        self.assertEqual(
            validated.tasks.active,
            0,
        )

        self.assertEqual(
            validated.tasks.pending,
            2,
        )

        self.assertEqual(
            validated.team.total,
            0,
        )

        self.assertEqual(
            validated.budget.currency,
            "PEN",
        )

        self.assertEqual(
            validated.budget
            .budget_limit_cents,
            100000,
        )

        self.assertEqual(
            validated.budget
            .quoted_amount_cents,
            80000,
        )

        self.assertIsNone(
            validated.final_review
        )

    def test_completed_project_without_vera_is_not_100(
        self,
    ):
        project = self.make_project(
            status="completed"
        )

        self.make_task(
            project=project,
            title="API terminada",
            status="completed",
        )

        self.db.commit()

        tracking = build_project_tracking(
            db=self.db,
            project=project,
        )

        self.assertLess(
            tracking[
                "progress_percent"
            ],
            100,
        )

        self.assertEqual(
            tracking["stage"],
            "completed",
        )

        self.assertEqual(
            tracking[
                "tasks"
            ][
                "completed"
            ],
            1,
        )

    def test_full_verified_progress_reaches_100(
        self,
    ):
        progress, parts = _progress_percent(
            project=SimpleNamespace(
                status="completed",
            ),
            tasks=[
                SimpleNamespace(
                    id=1,
                    status="completed",
                )
            ],
            contracts=[
                SimpleNamespace(
                    task_id=1,
                    status="completed",
                )
            ],
            latest_qa={
                1: SimpleNamespace(
                    task_id=1,
                    status="passed",
                )
            },
            final_review=SimpleNamespace(
                status="approved",
            ),
        )

        self.assertEqual(
            progress,
            100,
        )

        self.assertTrue(
            all(
                value == 1.0
                for value
                in parts.values()
            )
        )



    def test_delivery_decision_parser(
        self,
    ):
        from types import SimpleNamespace

        parsed = parse_delivery_message(
            SimpleNamespace(
                content=(
                    "DECISIÓN DE ENTREGA — "
                    "Versión v4 — "
                    "Correcciones solicitadas. "
                    "Solicitud: Ajustar el inicio."
                )
            )
        )

        self.assertEqual(
            parsed["decision"],
            "corrections_requested",
        )

        self.assertEqual(
            parsed["review_attempt"],
            4,
        )

        self.assertEqual(
            parsed["comment"],
            "Ajustar el inicio.",
        )



    def test_client_acceptance_is_persisted(
        self,
    ):
        project = self.make_project(
            status="completed"
        )

        self.db.commit()

        result = (
            submit_delivery_decision(
                db=self.db,
                project=project,
                decision="accepted",
                comment="Entrega conforme.",
                review_attempt=2,
            )
        )

        self.db.commit()

        self.assertEqual(
            result["decision"],
            "accepted",
        )

        self.assertEqual(
            project.status,
            "completed",
        )

        message = (
            latest_delivery_decision(
                db=self.db,
                project_id=project.id,
            )
        )

        parsed = (
            parse_delivery_message(
                message
            )
        )

        self.assertEqual(
            parsed["decision"],
            "accepted",
        )

        self.assertEqual(
            parsed["review_attempt"],
            2,
        )

        self.assertEqual(
            parsed["comment"],
            "Entrega conforme.",
        )


    def test_client_correction_request_is_persisted(
        self,
    ):
        project = self.make_project(
            status="completed"
        )

        self.db.commit()

        result = (
            submit_delivery_decision(
                db=self.db,
                project=project,
                decision=(
                    "corrections_requested"
                ),
                comment=(
                    "Ajustar la pantalla "
                    "principal."
                ),
                review_attempt=3,
            )
        )

        self.db.commit()

        self.assertEqual(
            result["decision"],
            "corrections_requested",
        )

        self.assertEqual(
            project.status,
            "client_corrections_requested",
        )

        message = (
            latest_delivery_decision(
                db=self.db,
                project_id=project.id,
            )
        )

        parsed = (
            parse_delivery_message(
                message
            )
        )

        self.assertEqual(
            parsed["decision"],
            "corrections_requested",
        )

        self.assertEqual(
            parsed["review_attempt"],
            3,
        )

        with self.assertRaises(
            DeliveryDecisionError
        ):
            submit_delivery_decision(
                db=self.db,
                project=project,
                decision=(
                    "corrections_requested"
                ),
                comment=(
                    "Repetir la misma "
                    "solicitud."
                ),
                review_attempt=3,
            )



    def test_project_access_is_protected(
        self,
    ):
        project = self.make_project()

        self.db.commit()

        owner_result = (
            _get_accessible_project(
                project_id=project.id,
                db=self.db,
                current_user=self.client,
            )
        )

        self.assertEqual(
            owner_result.id,
            project.id,
        )

        admin_result = (
            _get_accessible_project(
                project_id=project.id,
                db=self.db,
                current_user=self.admin,
            )
        )

        self.assertEqual(
            admin_result.id,
            project.id,
        )

        with self.assertRaises(
            HTTPException
        ) as context:
            _get_accessible_project(
                project_id=project.id,
                db=self.db,
                current_user=
                    self.other_user,
            )

        self.assertEqual(
            context.exception.status_code,
            403,
        )


if __name__ == "__main__":
    unittest.main()
