from __future__ import annotations

import unittest

from pathlib import Path
from types import SimpleNamespace

from app.agentic.repliker_runtime import (
    MARKET_AGENT_SYSTEM_PROMPT,
)
from app.services.repliker_matching_service import (
    MINIMUM_MARKET_SKILL_COVERAGE,
    market_candidate_is_relevant,
    rank_task_candidates,
)


def skill(
    name: str,
    level: int,
):
    return SimpleNamespace(
        name=name,
        level=level,
    )


def requirement(
    name: str,
    level: int,
):
    return SimpleNamespace(
        skill_name=name,
        minimum_level=level,
    )


class Phase24MarketDelegationPolicyTests(
    unittest.TestCase
):
    def test_prompt_knows_real_delegation(
        self,
    ):
        prompt = (
            MARKET_AGENT_SYSTEM_PROMPT
            .casefold()
        )

        self.assertIn(
            "delegation_available=true",
            prompt,
        )

        self.assertIn(
            "minimum_lead_coverage",
            prompt,
        )

        self.assertIn(
            "especialistas",
            prompt,
        )

        self.assertIn(
            "brecha puntual delegable",
            prompt,
        )

        self.assertNotIn(
            (
                "la posibilidad futura de "
                "delegar no justifica aceptar"
            ),
            prompt,
        )

    def test_market_sends_delegation_policy(
        self,
    ):
        source = Path(
            "app/api/routes/market.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            '"delegation_available":',
            source,
        )

        self.assertIn(
            '"minimum_lead_coverage":',
            source,
        )

        self.assertIn(
            '"delegation_policy":',
            source,
        )

        self.assertIn(
            "MINIMUM_MARKET_SKILL_COVERAGE",
            source,
        )

    def test_bruno_remains_valid_lead_candidate(
        self,
    ):
        bruno = SimpleNamespace(
            id=8,
            name="Bruno",
            specialty=
                "Backend Developer",
            status="available",
            reputation_score=95,
            jobs_completed=0,
            is_active=True,
            is_published=True,
            skills=[
                skill(
                    "Python",
                    98,
                ),
                skill(
                    "FastAPI",
                    98,
                ),
                skill(
                    "REST API",
                    97,
                ),
            ],
        )

        task = SimpleNamespace(
            required_specialty=
                "Generalist",
            required_skills=[
                requirement(
                    "Python",
                    75,
                ),
                requirement(
                    "FastAPI",
                    75,
                ),
                requirement(
                    "PostgreSQL",
                    70,
                ),
            ],
        )

        candidate = (
            rank_task_candidates(
                task=task,
                replikers=[
                    bruno,
                ],
            )[0]
        )

        self.assertAlmostEqual(
            candidate.skill_coverage,
            66.67,
            places=2,
        )

        self.assertEqual(
            candidate.skills_met,
            2,
        )

        self.assertFalse(
            candidate.meets_all_skills
        )

        self.assertGreaterEqual(
            candidate.skill_coverage,
            MINIMUM_MARKET_SKILL_COVERAGE,
        )

        self.assertTrue(
            market_candidate_is_relevant(
                candidate
            )
        )


if __name__ == "__main__":
    unittest.main()
