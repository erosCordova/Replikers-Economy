from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from app.services.delegation_service import (
    _same_owner_blocks_delegation,
)


class Phase24SystemDelegationTests(
    unittest.TestCase
):

    def repliker(
        self,
        *,
        owner_id: int,
        system: bool,
    ):
        return SimpleNamespace(
            owner_id=owner_id,
            is_system=system,
        )

    def test_system_replikers_same_owner_can_collaborate(
        self,
    ):
        bruno = self.repliker(
            owner_id=21,
            system=True,
        )

        dalia = self.repliker(
            owner_id=21,
            system=True,
        )

        self.assertFalse(
            _same_owner_blocks_delegation(
                delegator=bruno,
                candidate=dalia,
            )
        )

    def test_user_replikers_same_owner_remain_blocked(
        self,
    ):
        one = self.repliker(
            owner_id=10,
            system=False,
        )

        two = self.repliker(
            owner_id=10,
            system=False,
        )

        self.assertTrue(
            _same_owner_blocks_delegation(
                delegator=one,
                candidate=two,
            )
        )

    def test_different_owners_are_not_blocked(
        self,
    ):
        one = self.repliker(
            owner_id=10,
            system=False,
        )

        two = self.repliker(
            owner_id=11,
            system=False,
        )

        self.assertFalse(
            _same_owner_blocks_delegation(
                delegator=one,
                candidate=two,
            )
        )

    def test_rejected_request_is_retriable_in_source(
        self,
    ):
        source = Path(
            "app/services/"
            "delegation_service.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'existing.status\n'
            '            != "rejected"',
            source,
        )

        self.assertIn(
            "retry_existing = True",
            source,
        )

        self.assertIn(
            'delegated_task.status = "open"',
            source,
        )

        self.assertIn(
            '"delegation_reopened"',
            source,
        )


if __name__ == "__main__":
    unittest.main()
