from __future__ import annotations

from datetime import (
    timedelta,
)
import unittest

from fastapi import (
    HTTPException,
    Request,
)
from sqlalchemy import (
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import (
    sessionmaker,
)
from sqlalchemy.pool import (
    StaticPool,
)

import app.models  # noqa: F401

from app.api.routes.auth import (
    enforce_limit,
)
from app.auth.security import (
    hash_password,
)
from app.core.config import settings
from app.database.base import Base
from app.models.auth_rate_limit import (
    AuthRateLimit,
)
from app.models.auth_session import (
    AuthSession,
)
from app.models.user import User
from app.services.auth_abuse_service import (
    AuthRateLimitExceeded,
    build_identity,
    clear_auth_rate_limit,
    consume_auth_rate_limit,
    hash_identity,
)
from app.services.auth_session_service import (
    create_refresh_session,
    enforce_user_session_policy,
    rotate_refresh_session,
    utc_now,
)


class DatabaseTestCase(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.engine = (
            create_engine(
                "sqlite://",
                connect_args={
                    "check_same_thread":
                        False,
                },
                poolclass=
                    StaticPool,
            )
        )

        Base.metadata.create_all(
            bind=self.engine
        )

        self.Session = (
            sessionmaker(
                bind=self.engine,
                autoflush=False,
                expire_on_commit=False,
            )
        )

    def tearDown(
        self,
    ):
        Base.metadata.drop_all(
            bind=self.engine
        )

        self.engine.dispose()


class Phase12BRateLimitTests(
    DatabaseTestCase
):
    def request(
        self,
        ip: str = "203.0.113.20",
    ) -> Request:
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/auth/login",
                "headers": [],
                "client": (
                    ip,
                    50000,
                ),
                "server": (
                    "testserver",
                    80,
                ),
                "scheme": "http",
                "query_string": b"",
            }
        )

    def test_subject_identity_is_global(
        self,
    ):
        first = build_identity(
            self.request(
                "203.0.113.1"
            ),
            extra=
                " User@Example.COM ",
            include_ip=False,
        )

        second = build_identity(
            self.request(
                "203.0.113.2"
            ),
            extra=
                "user@example.com",
            include_ip=False,
        )

        self.assertEqual(
            first,
            "user@example.com",
        )

        self.assertEqual(
            first,
            second,
        )

    def test_ip_identity_is_separate(
        self,
    ):
        first = build_identity(
            self.request(
                "203.0.113.1"
            )
        )

        second = build_identity(
            self.request(
                "203.0.113.2"
            )
        )

        self.assertNotEqual(
            first,
            second,
        )

    def test_identity_hash_hides_subject(
        self,
    ):
        identity = (
            "user@example.com"
        )

        value = hash_identity(
            action=
                "login_identity",
            identity=identity,
        )

        self.assertEqual(
            len(value),
            64,
        )

        self.assertNotIn(
            identity,
            value,
        )

        self.assertEqual(
            value,
            hash_identity(
                action=
                    "login_identity",
                identity=identity,
            ),
        )

    def test_rate_limit_blocks(
        self,
    ):
        factory = self.Session

        for _ in range(2):
            consume_auth_rate_limit(
                action="test_login",
                identity="subject",
                max_requests=2,
                window_seconds=60,
                block_seconds=120,
                session_factory=factory,
            )

        with self.assertRaises(
            AuthRateLimitExceeded
        ) as context:
            consume_auth_rate_limit(
                action="test_login",
                identity="subject",
                max_requests=2,
                window_seconds=60,
                block_seconds=120,
                session_factory=factory,
            )

        self.assertGreaterEqual(
            context.exception
            .retry_after_seconds,
            1,
        )

        db = factory()

        try:
            row = db.scalar(
                select(
                    AuthRateLimit
                )
                .where(
                    AuthRateLimit.action
                    == "test_login"
                )
            )

            self.assertIsNotNone(
                row
            )

            self.assertEqual(
                row.attempts,
                3,
            )

            self.assertIsNotNone(
                row.blocked_until
            )

        finally:
            db.close()

    def test_clear_rate_limit(
        self,
    ):
        factory = self.Session

        consume_auth_rate_limit(
            action="login_identity",
            identity=
                "user@example.com",
            max_requests=10,
            window_seconds=60,
            block_seconds=60,
            session_factory=factory,
        )

        clear_auth_rate_limit(
            action="login_identity",
            identity=
                "user@example.com",
            session_factory=factory,
        )

        db = factory()

        try:
            count = db.scalar(
                select(
                    func.count()
                )
                .select_from(
                    AuthRateLimit
                )
            )

            self.assertEqual(
                count,
                0,
            )

        finally:
            db.close()

    def test_http_429_has_retry_after(
        self,
    ):
        from unittest.mock import patch

        with patch(
            "app.api.routes.auth."
            "consume_auth_rate_limit",
            side_effect=
                AuthRateLimitExceeded(
                    90
                ),
        ):
            with self.assertRaises(
                HTTPException
            ) as context:
                enforce_limit(
                    self.request(),
                    action=
                        "login_ip",
                    max_requests=1,
                    window_seconds=60,
                    block_seconds=90,
                )

        self.assertEqual(
            context.exception
            .status_code,
            429,
        )

        self.assertEqual(
            context.exception
            .headers[
                "Retry-After"
            ],
            "90",
        )


class Phase12BSessionPolicyTests(
    DatabaseTestCase
):
    def setUp(
        self,
    ):
        super().setUp()

        self.db = self.Session()

        self.user = User(
            full_name=
                "Session Policy Test",
            email=
                "session-policy@example.com",
            password_hash=
                hash_password(
                    "correct horse battery staple"
                ),
            role="user",
            is_active=True,
        )

        self.db.add(
            self.user
        )

        self.db.commit()
        self.db.refresh(
            self.user
        )

        self.old_max = (
            settings
            .MAX_ACTIVE_SESSIONS_PER_USER
        )

        self.old_history = (
            settings
            .AUTH_SESSION_HISTORY_DAYS
        )

    def tearDown(
        self,
    ):
        settings.MAX_ACTIVE_SESSIONS_PER_USER = (
            self.old_max
        )

        settings.AUTH_SESSION_HISTORY_DAYS = (
            self.old_history
        )

        self.db.close()

        super().tearDown()

    def test_session_cap_revokes_oldest(
        self,
    ):
        settings.MAX_ACTIVE_SESSIONS_PER_USER = (
            2
        )

        _, first = (
            create_refresh_session(
                self.db,
                user_id=
                    self.user.id,
            )
        )

        self.db.commit()

        _, second = (
            create_refresh_session(
                self.db,
                user_id=
                    self.user.id,
            )
        )

        self.db.commit()

        _, third = (
            create_refresh_session(
                self.db,
                user_id=
                    self.user.id,
            )
        )

        self.db.commit()
        self.db.expire_all()

        first_db = self.db.get(
            AuthSession,
            first.id,
        )

        second_db = self.db.get(
            AuthSession,
            second.id,
        )

        third_db = self.db.get(
            AuthSession,
            third.id,
        )

        self.assertIsNotNone(
            first_db.revoked_at
        )

        self.assertIsNone(
            second_db.revoked_at
        )

        self.assertIsNone(
            third_db.revoked_at
        )

    def test_rotation_at_cap_preserves_other_sessions(
        self,
    ):
        settings.MAX_ACTIVE_SESSIONS_PER_USER = (
            3
        )

        first_token, first = (
            create_refresh_session(
                self.db,
                user_id=
                    self.user.id,
            )
        )

        self.db.commit()

        second_token, second = (
            create_refresh_session(
                self.db,
                user_id=
                    self.user.id,
            )
        )

        self.db.commit()

        _, third = (
            create_refresh_session(
                self.db,
                user_id=
                    self.user.id,
            )
        )

        self.db.commit()

        _ = first_token

        _, _, replacement = (
            rotate_refresh_session(
                self.db,
                raw_token=
                    second_token,
            )
        )

        self.db.expire_all()

        first_db = self.db.get(
            AuthSession,
            first.id,
        )

        second_db = self.db.get(
            AuthSession,
            second.id,
        )

        third_db = self.db.get(
            AuthSession,
            third.id,
        )

        replacement_db = self.db.get(
            AuthSession,
            replacement.id,
        )

        self.assertIsNone(
            first_db.revoked_at
        )

        self.assertIsNotNone(
            second_db.revoked_at
        )

        self.assertIsNone(
            third_db.revoked_at
        )

        self.assertIsNone(
            replacement_db.revoked_at
        )

        active = list(
            self.db.scalars(
                select(
                    AuthSession
                )
                .where(
                    AuthSession.user_id
                    == self.user.id,
                    AuthSession.revoked_at
                    .is_(None),
                )
            )
        )

        self.assertEqual(
            len(active),
            3,
        )

    def test_recent_revocation_history_is_retained(
        self,
    ):
        settings.AUTH_SESSION_HISTORY_DAYS = (
            30
        )

        _, session = (
            create_refresh_session(
                self.db,
                user_id=
                    self.user.id,
            )
        )

        self.db.commit()

        session.created_at = (
            utc_now()
            - timedelta(
                days=60
            )
        )

        session.revoked_at = (
            utc_now()
            - timedelta(
                days=1
            )
        )

        self.db.commit()

        enforce_user_session_policy(
            self.db,
            user_id=
                self.user.id,
        )

        self.db.commit()
        self.db.expire_all()

        retained = self.db.get(
            AuthSession,
            session.id,
        )

        self.assertIsNotNone(
            retained
        )

    def test_old_revocation_history_is_removed(
        self,
    ):
        settings.AUTH_SESSION_HISTORY_DAYS = (
            30
        )

        _, session = (
            create_refresh_session(
                self.db,
                user_id=
                    self.user.id,
            )
        )

        self.db.commit()

        session.revoked_at = (
            utc_now()
            - timedelta(
                days=31
            )
        )

        self.db.commit()

        session_id = session.id

        enforce_user_session_policy(
            self.db,
            user_id=
                self.user.id,
        )

        self.db.commit()
        self.db.expire_all()

        self.assertIsNone(
            self.db.get(
                AuthSession,
                session_id,
            )
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
