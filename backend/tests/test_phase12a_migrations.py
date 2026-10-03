from __future__ import annotations

import tempfile
import unittest

from pathlib import Path

from alembic import command
from sqlalchemy import (
    create_engine,
    inspect,
    text,
)

from app.core.config import settings
from app.database.migrations import (
    DatabaseMigrationError,
    assert_database_migrations_current,
    build_alembic_config,
    database_revision_status,
    expected_database_heads,
)


BASELINE_REVISION = (
    "7940ce23d545"
)

CURRENT_REVISION = (
    "f3a713a2b002"
)


class Phase12AMigrationTests(
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
            / "migration-test.db"
        )

        engine = create_engine(
            f"sqlite:///{path}"
        )

        # unittest ejecuta los cleanups en orden LIFO.
        # Registramos primero el directorio temporal
        # para que engine.dispose() ocurra antes
        # de intentar eliminar el archivo SQLite.
        self.addCleanup(
            temporary.cleanup
        )

        self.addCleanup(
            engine.dispose
        )

        return engine

    def run_upgrade(
        self,
        database_url: str,
        revision: str,
    ) -> None:
        original_url = (
            settings.DATABASE_URL
        )

        try:
            settings.DATABASE_URL = (
                database_url
            )

            config = (
                build_alembic_config()
            )

            command.upgrade(
                config,
                revision,
            )

        finally:
            settings.DATABASE_URL = (
                original_url
            )

    def test_expected_head_exists(
        self,
    ):
        heads = (
            expected_database_heads()
        )

        self.assertEqual(
            len(heads),
            1,
        )

        self.assertEqual(
            heads[0],
            CURRENT_REVISION,
        )

    def test_unversioned_database_rejected(
        self,
    ):
        engine = (
            self.make_engine()
        )

        status = (
            database_revision_status(
                engine
            )
        )

        self.assertFalse(
            status.is_current
        )

        self.assertEqual(
            status.current_heads,
            (),
        )

        with self.assertRaises(
            DatabaseMigrationError
        ):
            assert_database_migrations_current(
                engine
            )

    def test_database_at_head_accepted(
        self,
    ):
        engine = (
            self.make_engine()
        )

        expected = (
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
                        expected,
                },
            )

        status = (
            assert_database_migrations_current(
                engine
            )
        )

        self.assertTrue(
            status.is_current
        )

        self.assertEqual(
            status.current_heads,
            status.expected_heads,
        )

    def test_runtime_does_not_create_schema(
        self,
    ):
        backend_root = (
            Path(__file__)
            .resolve()
            .parents[1]
        )

        main_source = (
            backend_root
            / "app"
            / "main.py"
        ).read_text(
            encoding="utf-8"
        )

        admin_source = (
            backend_root
            / "app"
            / "scripts"
            / "create_admin.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            "create_all",
            main_source,
        )

        self.assertNotIn(
            "create_all",
            admin_source,
        )

    def test_tests_may_keep_isolated_create_all(
        self,
    ):
        backend_root = (
            Path(__file__)
            .resolve()
            .parents[1]
        )

        source = (
            backend_root
            / "tests"
            / "test_phase11a_realtime_events.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "create_all",
            source,
        )

    def test_clean_database_upgrades_to_head(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            path = (
                Path(tmp)
                / "clean.db"
            )

            database_url = (
                f"sqlite:///{path}"
            )

            self.run_upgrade(
                database_url,
                "head",
            )

            engine = create_engine(
                database_url
            )

            try:
                inspector = inspect(
                    engine
                )

                self.assertIn(
                    "realtime_events",
                    inspector.get_table_names(),
                )

                status = (
                    assert_database_migrations_current(
                        engine
                    )
                )

                self.assertTrue(
                    status.is_current
                )

            finally:
                engine.dispose()

    def test_legacy_database_missing_realtime_is_repaired(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            path = (
                Path(tmp)
                / "legacy.db"
            )

            database_url = (
                f"sqlite:///{path}"
            )

            self.run_upgrade(
                database_url,
                BASELINE_REVISION,
            )

            engine = create_engine(
                database_url
            )

            try:
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            "DROP TABLE "
                            "realtime_events"
                        )
                    )

                inspector = inspect(
                    engine
                )

                self.assertNotIn(
                    "realtime_events",
                    inspector.get_table_names(),
                )

            finally:
                engine.dispose()

            self.run_upgrade(
                database_url,
                "head",
            )

            engine = create_engine(
                database_url
            )

            try:
                inspector = inspect(
                    engine
                )

                self.assertIn(
                    "realtime_events",
                    inspector.get_table_names(),
                )

                index_names = {
                    item["name"]
                    for item
                    in inspector.get_indexes(
                        "realtime_events"
                    )
                }

                expected_indexes = {
                    "ix_realtime_events_event_type",
                    "ix_realtime_events_id",
                    "ix_realtime_events_kind",
                    "ix_realtime_events_project_id",
                    "ix_realtime_events_repliker_id",
                    "ix_realtime_events_task_id",
                    "ix_realtime_project_cursor",
                    "ix_realtime_repliker_cursor",
                }

                self.assertTrue(
                    expected_indexes
                    .issubset(
                        index_names
                    )
                )

                status = (
                    assert_database_migrations_current(
                        engine
                    )
                )

                self.assertTrue(
                    status.is_current
                )

            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
