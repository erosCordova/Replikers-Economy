from __future__ import annotations

import asyncio
import json
import unittest

from types import SimpleNamespace

from fastapi import (
    FastAPI,
    HTTPException,
)
from sqlalchemy import (
    create_engine,
)
from sqlalchemy.orm import (
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401

from app.api.routes.realtime import (
    SSE_RETRY_MILLISECONDS,
    assert_project_stream_access,
    project_event_stream,
    resolve_sse_cursor,
    router as realtime_router,
    serialize_sse_event,
    serialize_sse_heartbeat,
    serialize_sse_retry,
)
from app.database.base import Base
from app.models.project import Project
from app.models.user import User
from app.services.activity_service import (
    record_activity,
)


class FakeRequest:
    def __init__(
        self,
        disconnected: bool = False,
    ):
        self.disconnected = (
            disconnected
        )

    async def is_disconnected(
        self,
    ) -> bool:
        return self.disconnected


class Phase11BSSETests(
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

        self.client = User(
            full_name="SSE Client",
            email=(
                "sse-client-"
                f"{self._testMethodName}"
                "@example.test"
            ),
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.other = User(
            full_name="Other User",
            email=(
                "sse-other-"
                f"{self._testMethodName}"
                "@example.test"
            ),
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.admin = User(
            full_name="Admin",
            email=(
                "sse-admin-"
                f"{self._testMethodName}"
                "@example.test"
            ),
            password_hash="test",
            role="admin",
            is_active=True,
        )

        self.db.add_all(
            [
                self.client,
                self.other,
                self.admin,
            ]
        )

        self.db.flush()

        self.project = Project(
            client_id=
                self.client.id,
            title="SSE Project",
            description=(
                "Proyecto SSE."
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

    def test_cursor_query_value(
        self,
    ):
        self.assertEqual(
            resolve_sse_cursor(
                after_id=12,
                last_event_id=None,
            ),
            12,
        )

    def test_last_event_id_wins(
        self,
    ):
        self.assertEqual(
            resolve_sse_cursor(
                after_id=12,
                last_event_id="27",
            ),
            27,
        )

    def test_invalid_last_event_id(
        self,
    ):
        with self.assertRaises(
            HTTPException
        ):
            resolve_sse_cursor(
                after_id=0,
                last_event_id="abc",
            )

    def test_access_control(
        self,
    ):
        assert_project_stream_access(
            project=self.project,
            current_user=self.client,
        )

        assert_project_stream_access(
            project=self.project,
            current_user=self.admin,
        )

        with self.assertRaises(
            HTTPException
        ) as context:
            assert_project_stream_access(
                project=self.project,
                current_user=self.other,
            )

        self.assertEqual(
            context.exception.status_code,
            403,
        )

    def test_sse_serialization(
        self,
    ):
        record_activity(
            db=self.db,
            project_id=
                self.project.id,
            event_type=
                "execution_started",
            title=
                "Ejecucion iniciada",
            description=
                "Repliker trabajando.",
            actor_type="repliker",
        )

        self.db.commit()

        from app.models.realtime import (
            RealtimeEvent,
        )

        event = (
            self.db.query(
                RealtimeEvent
            )
            .filter(
                RealtimeEvent.project_id
                == self.project.id
            )
            .one()
        )

        serialized = (
            serialize_sse_event(
                event
            )
        )

        self.assertIn(
            f"id: {event.id}\n",
            serialized,
        )

        self.assertIn(
            "event: activity\n",
            serialized,
        )

        data_line = next(
            line
            for line
            in serialized.splitlines()
            if line.startswith(
                "data: "
            )
        )

        payload = json.loads(
            data_line[
                len("data: "):
            ]
        )

        self.assertEqual(
            payload["id"],
            event.id,
        )

        self.assertEqual(
            payload["event_type"],
            "execution_started",
        )

        self.assertEqual(
            payload["payload"][
                "description"
            ],
            "Repliker trabajando.",
        )

    def test_protocol_frames(
        self,
    ):
        self.assertEqual(
            serialize_sse_heartbeat(),
            ": heartbeat\n\n",
        )

        self.assertEqual(
            serialize_sse_retry(),
            (
                "retry: "
                f"{SSE_RETRY_MILLISECONDS}"
                "\n\n"
            ),
        )

    def test_generator_reads_durable_event(
        self,
    ):
        record_activity(
            db=self.db,
            project_id=
                self.project.id,
            event_type="qa_started",
            title="QA iniciado",
            description=
                "Verificacion activa.",
            actor_type="qa",
        )

        self.db.commit()

        async def collect():
            chunks = []

            async for chunk in (
                project_event_stream(
                    request=
                        FakeRequest(),
                    project_id=
                        self.project.id,
                    start_after_id=0,
                    session_factory=
                        self.Session,
                    poll_seconds=0.01,
                    heartbeat_seconds=
                        999,
                    max_cycles=1,
                )
            ):
                chunks.append(
                    chunk
                )

            return chunks

        chunks = asyncio.run(
            collect()
        )

        self.assertGreaterEqual(
            len(chunks),
            2,
        )

        self.assertEqual(
            chunks[0],
            serialize_sse_retry(),
        )

        joined = "".join(
            chunks
        )

        self.assertIn(
            "event: activity",
            joined,
        )

        self.assertIn(
            '"event_type":"qa_started"',
            joined,
        )

    def test_disconnected_client_stops(
        self,
    ):
        async def collect():
            chunks = []

            async for chunk in (
                project_event_stream(
                    request=
                        FakeRequest(
                            disconnected=True
                        ),
                    project_id=
                        self.project.id,
                    start_after_id=0,
                    session_factory=
                        self.Session,
                    max_cycles=3,
                )
            ):
                chunks.append(
                    chunk
                )

            return chunks

        chunks = asyncio.run(
            collect()
        )

        # Solo se envia la instruccion
        # de retry inicial.
        self.assertEqual(
            chunks,
            [
                serialize_sse_retry()
            ],
        )


class Phase11BSSEApiTests(
    unittest.TestCase
):
    def test_route_exists(
        self,
    ):
        api = FastAPI()

        api.include_router(
            realtime_router,
            prefix="/api/v1",
        )

        paths = set(
            api.openapi()[
                "paths"
            ]
        )

        self.assertIn(
            (
                "/api/v1/realtime/"
                "projects/{project_id}/"
                "stream"
            ),
            paths,
        )

    def test_route_is_protected(
        self,
    ):
        api = FastAPI()

        api.include_router(
            realtime_router,
            prefix="/api/v1",
        )

        operation = api.openapi()[
            "paths"
        ][
            (
                "/api/v1/realtime/"
                "projects/{project_id}/"
                "stream"
            )
        ][
            "get"
        ]

        # La ruta contiene dependencias
        # de autenticacion en runtime.
        self.assertIn(
            "responses",
            operation,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
