from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from app.services.subcontract_execution_service import (
    _release_subcontractor_if_idle,
)


class SubcontractorReleaseTests(
    unittest.TestCase
):

    def test_idle_subcontractor_becomes_available(
        self,
    ):
        db = MagicMock()

        repliker = SimpleNamespace(
            status="subcontracted",
        )

        db.get.return_value = repliker
        db.scalar.side_effect = [
            None,
            None,
        ]

        _release_subcontractor_if_idle(
            db=db,
            repliker_id=9,
        )

        self.assertEqual(
            "available",
            repliker.status,
        )

        db.flush.assert_called_once()

    def test_active_subcontract_keeps_busy_status(
        self,
    ):
        db = MagicMock()

        repliker = SimpleNamespace(
            status="subcontracted",
        )

        db.get.return_value = repliker
        db.scalar.return_value = 99

        _release_subcontractor_if_idle(
            db=db,
            repliker_id=9,
        )

        self.assertEqual(
            "subcontracted",
            repliker.status,
        )

        db.flush.assert_not_called()

    def test_active_principal_contract_keeps_busy_status(
        self,
    ):
        db = MagicMock()

        repliker = SimpleNamespace(
            status="subcontracted",
        )

        db.get.return_value = repliker
        db.scalar.side_effect = [
            None,
            88,
        ]

        _release_subcontractor_if_idle(
            db=db,
            repliker_id=9,
        )

        self.assertEqual(
            "subcontracted",
            repliker.status,
        )

        db.flush.assert_not_called()


if __name__ == "__main__":
    unittest.main()
