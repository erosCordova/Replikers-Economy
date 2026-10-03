from __future__ import annotations

from datetime import (
    timedelta,
)
import unittest

from fastapi import Response
from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import (
    sessionmaker,
)
from sqlalchemy.pool import (
    StaticPool,
)

import app.models  # noqa: F401

from app.auth.cookies import (
    set_refresh_cookie,
)
from app.auth.security import (
    hash_password,
)
from app.database.base import Base
from app.models.auth_session import (
    AuthSession,
)
from app.models.user import User
from app.services.auth_session_service import (
    RefreshSessionError,
    RefreshTokenReuseError,
    create_refresh_session,
    hash_refresh_token,
    rotate_refresh_session,
    utc_now,
)


class Phase12BRefreshSessionTests(
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

        Session = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )

        self.db = Session()

        self.user = User(
            full_name=
                "Refresh Test",
            email=
                "refresh@example.com",
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

    def tearDown(
        self,
    ):
        self.db.close()

        Base.metadata.drop_all(
            bind=self.engine
        )

        self.engine.dispose()

    def test_raw_token_is_not_stored(
        self,
    ):
        token, session = (
            create_refresh_session(
                self.db,
                user_id=
                    self.user.id,
            )
        )

        self.db.commit()

        self.assertNotEqual(
            token,
            session.token_hash,
        )

        self.assertEqual(
            session.token_hash,
            hash_refresh_token(
                token
            ),
        )

        self.assertEqual(
            len(
                session.token_hash
            ),
            64,
        )

    def test_rotation_revokes_previous(
        self,
    ):
        token, first = (
            create_refresh_session(
                self.db,
                user_id=
                    self.user.id,
            )
        )

        self.db.commit()

        (
            user,
            new_token,
            second,
        ) = rotate_refresh_session(
            self.db,
            raw_token=token,
        )

        self.db.expire_all()

        old = self.db.get(
            AuthSession,
            first.id,
        )

        self.assertEqual(
            user.id,
            self.user.id,
        )

        self.assertNotEqual(
            token,
            new_token,
        )

        self.assertEqual(
            old.replaced_by_id,
            second.id,
        )

        self.assertIsNotNone(
            old.revoked_at
        )

        self.assertEqual(
            old.family_id,
            second.family_id,
        )

    def test_reuse_revokes_family(
        self,
    ):
        token, first = (
            create_refresh_session(
                self.db,
                user_id=
                    self.user.id,
            )
        )

        self.db.commit()

        _, _, second = (
            rotate_refresh_session(
                self.db,
                raw_token=token,
            )
        )

        with self.assertRaises(
            RefreshTokenReuseError
        ):
            rotate_refresh_session(
                self.db,
                raw_token=token,
            )

        self.db.expire_all()

        refreshed_second = (
            self.db.get(
                AuthSession,
                second.id,
            )
        )

        self.assertIsNotNone(
            refreshed_second.revoked_at
        )

        self.assertEqual(
            refreshed_second.family_id,
            first.family_id,
        )

    def test_expired_token_rejected(
        self,
    ):
        token, session = (
            create_refresh_session(
                self.db,
                user_id=
                    self.user.id,
            )
        )

        session.expires_at = (
            utc_now()
            - timedelta(
                seconds=1
            )
        )

        self.db.commit()

        with self.assertRaises(
            RefreshSessionError
        ):
            rotate_refresh_session(
                self.db,
                raw_token=token,
            )

        self.db.expire_all()

        refreshed = self.db.get(
            AuthSession,
            session.id,
        )

        self.assertIsNotNone(
            refreshed.revoked_at
        )

    def test_token_hash_is_unique(
        self,
    ):
        first_token, _ = (
            create_refresh_session(
                self.db,
                user_id=
                    self.user.id,
            )
        )

        second_token, _ = (
            create_refresh_session(
                self.db,
                user_id=
                    self.user.id,
            )
        )

        self.assertNotEqual(
            first_token,
            second_token,
        )

    def test_cookie_is_http_only(
        self,
    ):
        response = Response()

        set_refresh_cookie(
            response,
            "secret-refresh-token",
        )

        header = (
            response.headers[
                "set-cookie"
            ]
        )

        self.assertIn(
            "HttpOnly",
            header,
        )

        self.assertIn(
            "Path=/api/v1/auth",
            header,
        )

        self.assertIn(
            "SameSite=lax",
            header,
        )

    def test_auth_session_model_registered(
        self,
    ):
        names = (
            Base.metadata.tables
        )

        self.assertIn(
            "auth_sessions",
            names,
        )

    def test_family_query(
        self,
    ):
        _, created = (
            create_refresh_session(
                self.db,
                user_id=
                    self.user.id,
            )
        )

        self.db.commit()

        found = self.db.scalar(
            select(
                AuthSession
            )
            .where(
                AuthSession.family_id
                == created.family_id
            )
        )

        self.assertEqual(
            found.id,
            created.id,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )


class Phase12BRefreshIntegrationTests(
    unittest.TestCase
):
    def test_auth_routes_include_refresh_and_logout(
        self,
    ):
        from app.api.routes.auth import (
            router,
        )

        paths = {
            route.path
            for route
            in router.routes
        }

        self.assertIn(
            "/auth/refresh",
            paths,
        )

        self.assertIn(
            "/auth/logout",
            paths,
        )

        self.assertIn(
            "/auth/logout-all",
            paths,
        )

    def test_main_allows_credentialed_cors(
        self,
    ):
        from pathlib import Path

        backend_root = (
            Path(__file__)
            .resolve()
            .parents[1]
        )

        source = (
            backend_root
            / "app"
            / "main.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "allow_credentials=True",
            source,
        )

        self.assertNotIn(
            'allow_origins=["*"]',
            source,
        )

    def test_auth_routes_validate_origin(
        self,
    ):
        from pathlib import Path

        backend_root = (
            Path(__file__)
            .resolve()
            .parents[1]
        )

        source = (
            backend_root
            / "app"
            / "api"
            / "routes"
            / "auth.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertGreaterEqual(
            source.count(
                "validate_cookie_origin("
            ),
            5,
        )
