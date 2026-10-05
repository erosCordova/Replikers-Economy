from __future__ import annotations

import unittest

from types import SimpleNamespace

from app.agentic.tool_catalog import (
    MarketToolContext,
    _skill_coverage,
)
from app.services.contract_service import (
    _skill_score,
)
from app.services.delegation_service import (
    _skill_level,
)
from app.services.repliker_matching_service import (
    market_candidate_is_relevant,
    rank_task_candidates,
)


def skill(name, level):
    return SimpleNamespace(
        name=name,
        level=level,
    )


def requirement(name, level):
    return SimpleNamespace(
        skill_name=name,
        minimum_level=level,
    )


def make_repliker(
    repliker_id,
    name,
    specialty,
    skills,
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


class Phase24SkillAlignmentTests(
    unittest.TestCase
):
    def frontend_task(self):
        return SimpleNamespace(
            required_specialty=
                "Generalist",
            required_skills=[
                requirement(
                    "Frontend Development",
                    75,
                ),
                requirement(
                    "JavaScript",
                    70,
                ),
                requirement(
                    "HTML/CSS",
                    70,
                ),
            ],
        )

    def backend_task(self):
        return SimpleNamespace(
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

    def test_nova_frontend_is_consistent(
        self,
    ):
        nova = make_repliker(
            7,
            "Nova",
            "Frontend Developer",
            [
                skill("React", 98),
                skill("TypeScript", 97),
                skill("JavaScript", 97),
                skill("HTML", 98),
                skill("CSS", 97),
            ],
        )

        task = self.frontend_task()

        candidate = (
            rank_task_candidates(
                task=task,
                replikers=[nova],
            )[0]
        )

        self.assertEqual(
            candidate.skill_coverage,
            100.0,
        )

        self.assertEqual(
            candidate.skills_met,
            3,
        )

        self.assertTrue(
            candidate.meets_all_skills
        )

        self.assertTrue(
            market_candidate_is_relevant(
                candidate
            )
        )

        self.assertEqual(
            _skill_score(
                task=task,
                repliker=nova,
            ),
            100,
        )

        self.assertEqual(
            _skill_level(
                repliker=nova,
                skill_name=
                    "Frontend Development",
            ),
            97,
        )

        self.assertEqual(
            _skill_level(
                repliker=nova,
                skill_name="HTML/CSS",
            ),
            97,
        )

        context = MarketToolContext(
            repliker_data={
                "skills": [
                    {
                        "name": s.name,
                        "level": s.level,
                    }
                    for s in nova.skills
                ]
            },
            task_data={
                "required_skills": [
                    {
                        "skill_name":
                            r.skill_name,
                        "minimum_level":
                            r.minimum_level,
                    }
                    for r
                    in task.required_skills
                ]
            },
            project_data={},
            allowed_tool_names=(),
        )

        result = _skill_coverage(
            context
        )

        self.assertEqual(
            result["coverage_percent"],
            100,
        )

        self.assertEqual(
            result["requirements_met"],
            3,
        )

    def test_bruno_can_lead_backend(
        self,
    ):
        bruno = make_repliker(
            8,
            "Bruno",
            "Backend Developer",
            [
                skill("Python", 98),
                skill("FastAPI", 98),
                skill("REST API", 97),
            ],
        )

        candidate = (
            rank_task_candidates(
                task=self.backend_task(),
                replikers=[bruno],
            )[0]
        )

        self.assertEqual(
            candidate.skills_met,
            2,
        )

        self.assertAlmostEqual(
            candidate.skill_coverage,
            66.67,
            places=2,
        )

        self.assertTrue(
            market_candidate_is_relevant(
                candidate
            )
        )

    def test_dalia_is_specialist_not_lead(
        self,
    ):
        dalia = make_repliker(
            9,
            "Dalia",
            "Database Engineer",
            [
                skill("PostgreSQL", 98),
                skill("SQL", 98),
            ],
        )

        candidate = (
            rank_task_candidates(
                task=self.backend_task(),
                replikers=[dalia],
            )[0]
        )

        self.assertEqual(
            candidate.skills_met,
            1,
        )

        self.assertAlmostEqual(
            candidate.skill_coverage,
            33.33,
            places=2,
        )

        self.assertFalse(
            market_candidate_is_relevant(
                candidate
            )
        )

    def test_zero_coverage_is_filtered(
        self,
    ):
        luna = make_repliker(
            6,
            "Luna",
            "UI Designer",
            [
                skill("UI Design", 98),
                skill("Design Systems", 95),
            ],
        )

        candidate = (
            rank_task_candidates(
                task=self.backend_task(),
                replikers=[luna],
            )[0]
        )

        self.assertEqual(
            candidate.skill_coverage,
            0.0,
        )

        self.assertFalse(
            market_candidate_is_relevant(
                candidate
            )
        )


if __name__ == "__main__":
    unittest.main()
