from __future__ import annotations

import unittest

from types import SimpleNamespace

from app.services.repliker_matching_service import (
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


def required_skill(
    name: str,
    minimum: int,
):
    return SimpleNamespace(
        skill_name=name,
        minimum_level=minimum,
    )


def repliker(
    *,
    repliker_id: int,
    name: str,
    specialty: str,
    skills: list,
):
    return SimpleNamespace(
        id=repliker_id,
        name=name,
        specialty=specialty,
        status="available",
        reputation_score=95,
        jobs_completed=0,
        is_active=True,
        is_published=True,
        skills=skills,
    )


class Phase24MarketMatchingTests(
    unittest.TestCase
):
    def _frontend_task(self):
        return SimpleNamespace(
            required_specialty="Generalist",
            required_skills=[
                required_skill(
                    "Frontend Development",
                    75,
                ),
                required_skill(
                    "JavaScript",
                    70,
                ),
                required_skill(
                    "HTML/CSS",
                    70,
                ),
            ],
        )

    def test_frontend_composite_skills_match(
        self,
    ):
        nova = repliker(
            repliker_id=7,
            name="Nova",
            specialty="Frontend Developer",
            skills=[
                skill("React", 98),
                skill("TypeScript", 97),
                skill("JavaScript", 97),
                skill("HTML", 98),
                skill("CSS", 97),
            ],
        )

        candidates = (
            rank_task_candidates(
                task=self._frontend_task(),
                replikers=[nova],
            )
        )

        self.assertEqual(
            len(candidates),
            1,
        )

        candidate = candidates[0]

        self.assertEqual(
            candidate.skills_met,
            3,
        )

        self.assertEqual(
            candidate.skills_total,
            3,
        )

        self.assertTrue(
            candidate.meets_all_skills
        )

        self.assertEqual(
            candidate.skill_coverage,
            100.0,
        )

    def test_html_css_requires_both(
        self,
    ):
        incomplete = repliker(
            repliker_id=20,
            name="Solo HTML",
            specialty="Frontend Developer",
            skills=[
                skill("JavaScript", 95),
                skill("HTML", 95),
            ],
        )

        candidates = (
            rank_task_candidates(
                task=self._frontend_task(),
                replikers=[incomplete],
            )
        )

        candidate = candidates[0]

        self.assertFalse(
            candidate.meets_all_skills
        )

        self.assertLess(
            candidate.skills_met,
            3,
        )

    def test_backend_profile_does_not_fake_frontend(
        self,
    ):
        backend = repliker(
            repliker_id=1,
            name="Backend",
            specialty="Backend Development",
            skills=[
                skill("Python", 98),
                skill("FastAPI", 98),
                skill("PostgreSQL", 95),
            ],
        )

        candidates = (
            rank_task_candidates(
                task=self._frontend_task(),
                replikers=[backend],
            )
        )

        candidate = candidates[0]

        self.assertEqual(
            candidate.skills_met,
            0,
        )

        self.assertFalse(
            candidate.meets_all_skills
        )


if __name__ == "__main__":
    unittest.main()
