from __future__ import annotations

import unittest

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)


class Phase24StaleMarketBidTests(
    unittest.TestCase
):
    def test_market_active_bid_requires_currently_eligible_repliker(
        self,
    ):
        source = (
            ROOT
            / "app"
            / "api"
            / "routes"
            / "market.py"
        ).read_text(
            encoding="utf-8"
        )

        expected_fragments = (
            ".join(",
            "Repliker.is_active",
            "Repliker.is_published",
            'Repliker.status',
            '"available"',
            "Repliker.owner_id",
            "project.client_id",
        )

        for fragment in expected_fragments:
            with self.subTest(
                fragment=fragment
            ):
                self.assertIn(
                    fragment,
                    source,
                )

    def test_market_does_not_use_unfiltered_pending_bid_guard(
        self,
    ):
        source = (
            ROOT
            / "app"
            / "api"
            / "routes"
            / "market.py"
        ).read_text(
            encoding="utf-8"
        )

        old_guard = '''        active_bid = db.scalar(
            select(TaskBid)
            .where(
                TaskBid.task_id
                == task.id,
                TaskBid.status.in_(
'''

        self.assertNotIn(
            old_guard,
            source,
        )


if __name__ == "__main__":
    unittest.main()
