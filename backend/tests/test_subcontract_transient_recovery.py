from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from app.services.subcontract_execution_service import (
    _recover_transient_failed_artifacts,
)


def _result(values):
    result = MagicMock()
    result.all.return_value = values
    return result


class SubcontractTransientRecoveryTests(
    unittest.TestCase
):

    def test_recovers_only_transient_failed_work(
        self,
    ):
        source = Path(
            "app/services/"
            "subcontract_execution_service.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "is_transient_provider_error",
            source,
        )

        self.assertIn(
            '"workspace_write_text"',
            source,
        )

        self.assertIn(
            "carryover_artifacts",
            source,
        )

    def test_merges_previous_and_current_artifacts(
        self,
    ):
        source = Path(
            "app/services/"
            "subcontract_execution_service.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "artifact_map = {",
            source,
        )

        self.assertIn(
            "*carryover_artifacts",
            source,
        )

        self.assertIn(
            "*artifacts",
            source,
        )

    def test_recovery_is_scoped_to_repliker(
        self,
    ):
        db = MagicMock()

        failed_log = SimpleNamespace(
            id=30,
            error_summary=(
                "503 Service Unavailable"
            ),
        )

        db.scalars.side_effect = [
            _result(
                [failed_log]
            ),
            _result(
                []
            ),
        ]

        db.scalar.return_value = 20

        result = (
            _recover_transient_failed_artifacts(
                db=db,
                workspace_id=1,
                repliker_id=9,
            )
        )

        self.assertEqual(
            result,
            [],
        )

        statements = [
            db.scalars
            .call_args_list[0]
            .args[0],

            db.scalar
            .call_args_list[0]
            .args[0],

            db.scalars
            .call_args_list[1]
            .args[0],
        ]

        for statement in statements:
            sql = str(statement)

            self.assertIn(
                "tool_execution_logs.repliker_id",
                sql,
            )

            params = (
                statement
                .compile()
                .params
            )

            self.assertIn(
                9,
                params.values(),
            )

    def test_scans_past_newer_writeless_failure(
        self,
    ):
        db = MagicMock()

        newest_failure = SimpleNamespace(
            id=40,
            error_summary=(
                "503 Service Unavailable"
            ),
        )

        older_failure = SimpleNamespace(
            id=30,
            error_summary=(
                "429 Too Many Requests"
            ),
        )

        artifact = SimpleNamespace(
            id=7,
            relative_path=(
                "database/schema.sql"
            ),
            media_type="text/plain",
            size_bytes=321,
            sha256="abc123",
        )

        db.scalars.side_effect = [
            # Fallos delegados.
            _result(
                [
                    newest_failure,
                    older_failure,
                ]
            ),

            # El intento nuevo no escribio.
            _result(
                []
            ),

            # El intento anterior si escribio.
            _result(
                [
                    "database/schema.sql"
                ]
            ),

            # Artifact actual.
            _result(
                [
                    artifact
                ]
            ),
        ]

        db.scalar.side_effect = [
            35,
            25,
        ]

        recovered = (
            _recover_transient_failed_artifacts(
                db=db,
                workspace_id=1,
                repliker_id=9,
            )
        )

        self.assertEqual(
            len(recovered),
            1,
        )

        self.assertEqual(
            recovered[0][
                "relative_path"
            ],
            "database/schema.sql",
        )

        self.assertEqual(
            recovered[0][
                "sha256"
            ],
            "abc123",
        )


if __name__ == "__main__":
    unittest.main()
