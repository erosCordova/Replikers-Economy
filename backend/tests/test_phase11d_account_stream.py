from __future__ import annotations

import unittest

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401

from app.api.routes.realtime import (
    router as realtime_router,
)
from app.database.base import Base
from app.models.project import Project
from app.models.user import User
from app.services.activity_service import (
    record_activity,
)
from app.services.realtime_service import (
    list_account_realtime_events,
)


class Phase11DAccountStreamTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={
                "check_same_thread":
                    False,
            },
            poolclass=StaticPool,
        )

        cls.Session = sessionmaker(
            bind=cls.engine,
            autocommit=False,
            autoflush=False,
        )

        Base.metadata.create_all(
            bind=cls.engine
        )

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(
            bind=cls.engine
        )

        cls.engine.dispose()

    def setUp(self):
        self.db = self.Session()

        self.user_a = User(
            full_name="User A",
            email=(
                "11d-a-"
                f"{self._testMethodName}"
                "@example.test"
            ),
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.user_b = User(
            full_name="User B",
            email=(
                "11d-b-"
                f"{self._testMethodName}"
                "@example.test"
            ),
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.db.add_all(
            [
                self.user_a,
                self.user_b,
            ]
        )

        self.db.flush()

        self.project_a = Project(
            client_id=
                self.user_a.id,
            title="Proyecto A",
            description="A",
            status="draft",
            currency="PEN",
            budget_limit_cents=
                1000,
            quoted_amount_cents=
                1000,
            payment_status="unpaid",
        )

        self.project_b = Project(
            client_id=
                self.user_b.id,
            title="Proyecto B",
            description="B",
            status="draft",
            currency="PEN",
            budget_limit_cents=
                1000,
            quoted_amount_cents=
                1000,
            payment_status="unpaid",
        )

        self.db.add_all(
            [
                self.project_a,
                self.project_b,
            ]
        )

        self.db.flush()

        record_activity(
            db=self.db,
            project_id=
                self.project_a.id,
            event_type="a_event",
            title="Evento A",
        )

        record_activity(
            db=self.db,
            project_id=
                self.project_b.id,
            event_type="b_event",
            title="Evento B",
        )

        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_user_only_sees_own_projects(
        self,
    ):
        rows = (
            list_account_realtime_events(
                db=self.db,
                user_id=
                    self.user_a.id,
                is_admin=False,
            )
        )

        self.assertEqual(
            [
                row.event_type
                for row in rows
            ],
            [
                "a_event"
            ],
        )

    def test_admin_can_see_all(
        self,
    ):
        rows = (
            list_account_realtime_events(
                db=self.db,
                user_id=
                    self.user_a.id,
                is_admin=True,
            )
        )

        event_types = {
            row.event_type
            for row in rows
        }

        self.assertEqual(
            event_types,
            {
                "a_event",
                "b_event",
            },
        )

    def test_cursor_reconnect(
        self,
    ):
        first = (
            list_account_realtime_events(
                db=self.db,
                user_id=
                    self.user_a.id,
                is_admin=False,
            )
        )[0]

        record_activity(
            db=self.db,
            project_id=
                self.project_a.id,
            event_type="a_second",
            title="Segundo A",
        )

        self.db.commit()

        rows = (
            list_account_realtime_events(
                db=self.db,
                user_id=
                    self.user_a.id,
                is_admin=False,
                after_id=
                    first.id,
            )
        )

        self.assertEqual(
            [
                row.event_type
                for row in rows
            ],
            [
                "a_second"
            ],
        )


class Phase11DRouteTests(
    unittest.TestCase
):
    def test_account_stream_route_exists(
        self,
    ):
        api = FastAPI()

        api.include_router(
            realtime_router,
            prefix="/api/v1",
        )

        self.assertIn(
            "/api/v1/realtime/mine/stream",
            api.openapi()[
                "paths"
            ],
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
