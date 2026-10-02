from __future__ import annotations

import unittest

from sqlalchemy import (
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import (
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401

from app.database.base import Base
from app.models.ecosystem import (
    AgentActivityEvent,
    AgentMessage,
)
from app.models.project import Project
from app.models.realtime import (
    RealtimeEvent,
)
from app.models.user import User
from app.services.activity_service import (
    record_activity,
)
from app.services.message_service import (
    record_message,
)
from app.services.realtime_service import (
    event_payload,
    latest_project_event_id,
    list_project_realtime_events,
)


class Phase11ARealtimeEventsTests(
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

        self.user = User(
            full_name="Realtime User",
            email=(
                "realtime-"
                f"{self._testMethodName}"
                "@example.test"
            ),
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.db.add(
            self.user
        )

        self.db.flush()

        self.project = Project(
            client_id=
                self.user.id,
            title="Realtime Project",
            description=(
                "Proyecto para probar "
                "el outbox durable."
            ),
            status="draft",
            currency="PEN",
            budget_limit_cents=
                10_000,
            quoted_amount_cents=
                10_000,
            payment_status="unpaid",
        )

        self.db.add(
            self.project
        )

        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_activity_creates_realtime_event(
        self,
    ):
        record_activity(
            db=self.db,
            project_id=
                self.project.id,
            event_type=
                "planning_started",
            title=
                "R00 inicio planificacion",
            description=
                "Analizando requisitos.",
            actor_type="r00",
        )

        self.db.flush()

        activity_count = int(
            self.db.scalar(
                select(
                    func.count(
                        AgentActivityEvent.id
                    )
                )
            )
            or 0
        )

        realtime = list(
            self.db.scalars(
                select(
                    RealtimeEvent
                )
                .where(
                    RealtimeEvent.project_id
                    == self.project.id
                )
            ).all()
        )

        self.assertEqual(
            activity_count,
            1,
        )

        self.assertEqual(
            len(realtime),
            1,
        )

        event = realtime[0]

        self.assertEqual(
            event.kind,
            "activity",
        )

        self.assertEqual(
            event.event_type,
            "planning_started",
        )

        self.assertEqual(
            event.actor_type,
            "r00",
        )

        payload = event_payload(
            event
        )

        self.assertEqual(
            payload["description"],
            "Analizando requisitos.",
        )

    def test_message_creates_realtime_event(
        self,
    ):
        message = record_message(
            db=self.db,
            project_id=
                self.project.id,
            content=(
                "Necesito apoyo "
                "especializado."
            ),
            sender_type="repliker",
            receiver_type="project",
            message_type=
                "coordination",
        )

        self.assertIsNotNone(
            message
        )

        self.db.flush()

        message_count = int(
            self.db.scalar(
                select(
                    func.count(
                        AgentMessage.id
                    )
                )
            )
            or 0
        )

        realtime = list(
            self.db.scalars(
                select(
                    RealtimeEvent
                )
                .where(
                    RealtimeEvent.project_id
                    == self.project.id
                )
            ).all()
        )

        self.assertEqual(
            message_count,
            1,
        )

        self.assertEqual(
            len(realtime),
            1,
        )

        event = realtime[0]

        self.assertEqual(
            event.kind,
            "message",
        )

        payload = event_payload(
            event
        )

        self.assertEqual(
            payload["content"],
            (
                "Necesito apoyo "
                "especializado."
            ),
        )

    def test_blank_message_emits_nothing(
        self,
    ):
        result = record_message(
            db=self.db,
            project_id=
                self.project.id,
            content="   ",
            sender_type="repliker",
            receiver_type="project",
        )

        self.assertIsNone(
            result
        )

        self.db.flush()

        count = int(
            self.db.scalar(
                select(
                    func.count(
                        RealtimeEvent.id
                    )
                )
            )
            or 0
        )

        self.assertEqual(
            count,
            0,
        )

    def test_cursor_is_monotonic(
        self,
    ):
        record_activity(
            db=self.db,
            project_id=
                self.project.id,
            event_type="first",
            title="Primero",
        )

        self.db.flush()

        first = (
            list_project_realtime_events(
                db=self.db,
                project_id=
                    self.project.id,
            )[0]
        )

        record_activity(
            db=self.db,
            project_id=
                self.project.id,
            event_type="second",
            title="Segundo",
        )

        self.db.flush()

        rows = (
            list_project_realtime_events(
                db=self.db,
                project_id=
                    self.project.id,
                after_id=
                    first.id,
            )
        )

        self.assertEqual(
            len(rows),
            1,
        )

        self.assertEqual(
            rows[0].event_type,
            "second",
        )

        self.assertGreater(
            rows[0].id,
            first.id,
        )

        self.assertEqual(
            latest_project_event_id(
                db=self.db,
                project_id=
                    self.project.id,
            ),
            rows[0].id,
        )

    def test_project_isolation(
        self,
    ):
        other = Project(
            client_id=
                self.user.id,
            title="Otro proyecto",
            description="Aislado",
            status="draft",
            currency="PEN",
            budget_limit_cents=
                5_000,
            quoted_amount_cents=
                5_000,
            payment_status="unpaid",
        )

        self.db.add(other)
        self.db.flush()

        record_activity(
            db=self.db,
            project_id=
                self.project.id,
            event_type="project_a",
            title="A",
        )

        record_activity(
            db=self.db,
            project_id=
                other.id,
            event_type="project_b",
            title="B",
        )

        self.db.flush()

        rows = (
            list_project_realtime_events(
                db=self.db,
                project_id=
                    self.project.id,
            )
        )

        self.assertEqual(
            len(rows),
            1,
        )

        self.assertEqual(
            rows[0].event_type,
            "project_a",
        )

    def test_outbox_rolls_back_with_business_event(
        self,
    ):
        record_activity(
            db=self.db,
            project_id=
                self.project.id,
            event_type=
                "rollback_probe",
            title=
                "Debe desaparecer",
        )

        self.db.flush()

        before = int(
            self.db.scalar(
                select(
                    func.count(
                        RealtimeEvent.id
                    )
                )
                .where(
                    RealtimeEvent.event_type
                    == "rollback_probe"
                )
            )
            or 0
        )

        self.assertEqual(
            before,
            1,
        )

        self.db.rollback()

        after_realtime = int(
            self.db.scalar(
                select(
                    func.count(
                        RealtimeEvent.id
                    )
                )
                .where(
                    RealtimeEvent.event_type
                    == "rollback_probe"
                )
            )
            or 0
        )

        after_activity = int(
            self.db.scalar(
                select(
                    func.count(
                        AgentActivityEvent.id
                    )
                )
                .where(
                    AgentActivityEvent.event_type
                    == "rollback_probe"
                )
            )
            or 0
        )

        self.assertEqual(
            after_realtime,
            0,
        )

        self.assertEqual(
            after_activity,
            0,
        )

    def test_realtime_table_registered(
        self,
    ):
        self.assertIn(
            "realtime_events",
            Base.metadata.tables,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
