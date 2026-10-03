from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from sqlalchemy import (
    create_engine,
    text,
)

from app.database.migrations import (
    expected_database_heads,
)
from app.services.health_service import (
    check_readiness,
)


class Phase12CReadinessTests(
    unittest.TestCase
):
    def make_engine(
        self,
    ):
        temporary = (
            tempfile
            .TemporaryDirectory()
        )

        path = (
            Path(
                temporary.name
            )
            / "ready.db"
        )

        engine = create_engine(
            f"sqlite:///{path}"
        )

        self.addCleanup(
            engine.dispose
        )

        self.addCleanup(
            temporary.cleanup
        )

        return engine

    def test_unversioned_database_not_ready(
        self,
    ):
        engine = self.make_engine()

        result = check_readiness(
            engine
        )

        self.assertFalse(
            result.ready
        )

        self.assertEqual(
            result.database,
            "ok",
        )

        self.assertEqual(
            result.migrations,
            "outdated",
        )

    def test_database_at_head_ready(
        self,
    ):
        engine = self.make_engine()

        head = (
            expected_database_heads()[0]
        )

        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE alembic_version (
                        version_num VARCHAR(32)
                        NOT NULL PRIMARY KEY
                    )
                    """
                )
            )

            connection.execute(
                text(
                    """
                    INSERT INTO alembic_version
                        (version_num)
                    VALUES
                        (:revision)
                    """
                ),
                {
                    "revision":
                        head,
                },
            )

        result = check_readiness(
            engine
        )

        self.assertTrue(
            result.ready
        )

        self.assertEqual(
            result.database,
            "ok",
        )

        self.assertEqual(
            result.migrations,
            "current",
        )


class Phase12CProductionContractTests(
    unittest.TestCase
):
    def test_backend_env_example_complete(
        self,
    ):
        backend_root = (
            Path(__file__)
            .resolve()
            .parents[1]
        )

        content = (
            backend_root
            / ".env.example"
        ).read_text(
            encoding="utf-8"
        )

        required = [
            "ENVIRONMENT=",
            "DATABASE_URL=",
            "SECRET_KEY=",
            "FRONTEND_URL=",
            "REFRESH_COOKIE_SAMESITE=",
            "ECONOMY_MODE=",
            "REAL_PAYMENTS_ENABLED=",
            "GEMINI_API_KEY=",
        ]

        for item in required:
            self.assertIn(
                item,
                content,
            )

    def test_production_check_does_not_print_secrets(
        self,
    ):
        backend_root = (
            Path(__file__)
            .resolve()
            .parents[1]
        )

        source = (
            backend_root
            / "app"
            / "scripts"
            / "production_check.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            "settings.SECRET_KEY",
            source,
        )

        self.assertNotIn(
            "settings.DATABASE_URL",
            source,
        )

        self.assertNotIn(
            "settings.GEMINI_API_KEY",
            source,
        )

    def openapi_paths(
        self,
    ):
        from app.main import app

        schema = app.openapi()

        return schema.get(
            "paths",
            {},
        )

    def test_health_routes_registered(
        self,
    ):
        paths = (
            self.openapi_paths()
        )

        self.assertIn(
            "/api/v1/health/live",
            paths,
        )

        self.assertIn(
            "/api/v1/health/ready",
            paths,
        )

    def test_liveness_route_is_get(
        self,
    ):
        paths = (
            self.openapi_paths()
        )

        live = paths.get(
            "/api/v1/health/live",
            {},
        )

        self.assertIn(
            "get",
            live,
        )

    def test_readiness_route_is_get(
        self,
    ):
        paths = (
            self.openapi_paths()
        )

        ready = paths.get(
            "/api/v1/health/ready",
            {},
        )

        self.assertIn(
            "get",
            ready,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
