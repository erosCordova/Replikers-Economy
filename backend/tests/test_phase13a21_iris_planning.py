import unittest

from app.models.task import Task
from app.orchestration.coordinator import (
    SYSTEM_INSTRUCTION,
    normalize_budgets,
    normalize_specialists,
)
from app.schemas.coordinator import (
    AIProjectPlan,
)


class Phase13A21IrisPlanningTests(
    unittest.TestCase
):
    def _plan(self):
        return AIProjectPlan.model_validate(
            {
                "summary":
                    "Plan de prueba.",
                "strategy":
                    "Cubrir el proyecto.",
                "required_specialists": [
                    {
                        "specialty":
                            "Frontend Developer",
                        "reason":
                            "Construir interfaz.",
                        "mandatory":
                            True,
                        "final_gate":
                            False,
                    }
                ],
                "market_gaps": [],
                "tasks": [
                    {
                        "title":
                            "Construir frontend",
                        "description":
                            "Crear interfaz web.",
                        "required_specialty":
                            "Frontend Developer",
                        "complexity":
                            60,
                        "max_budget_cents":
                            5000,
                        "required_skills": [
                            {
                                "skill_name":
                                    "React",
                                "minimum_level":
                                    80,
                            }
                        ],
                        "acceptance_criteria": [
                            "La interfaz funciona."
                        ],
                    }
                ],
            }
        )

    def test_task_has_required_specialty(
        self,
    ):
        self.assertIn(
            "required_specialty",
            Task.__table__.columns,
        )

    def test_iris_is_planner(
        self,
    ):
        self.assertIn(
            "Eres Iris",
            SYSTEM_INSTRUCTION,
        )

        self.assertIn(
            "Product / Requirements",
            SYSTEM_INSTRUCTION,
        )

    def test_concrete_selection_is_forbidden(
        self,
    ):
        self.assertIn(
            "No selecciones Replikers concretos",
            SYSTEM_INSTRUCTION,
        )

    def test_required_specialty_is_preserved(
        self,
    ):
        plan = self._plan()

        self.assertEqual(
            plan.tasks[0].required_specialty,
            "Frontend Developer",
        )

    def test_final_reviewer_is_added(
        self,
    ):
        plan = normalize_specialists(
            self._plan()
        )

        reviewer = next(
            item
            for item
            in plan.required_specialists
            if item.specialty
            == "Final Reviewer"
        )

        self.assertTrue(
            reviewer.mandatory
        )

        self.assertTrue(
            reviewer.final_gate
        )

    def test_task_specialty_is_added_to_registry(
        self,
    ):
        plan = self._plan()
        plan.required_specialists = []

        result = normalize_specialists(
            plan
        )

        specialties = {
            item.specialty
            for item
            in result.required_specialists
        }

        self.assertIn(
            "Frontend Developer",
            specialties,
        )

    def test_budget_limit_is_respected(
        self,
    ):
        plan = self._plan()

        normalized = normalize_budgets(
            plan,
            3000,
        )

        total = sum(
            task.max_budget_cents
            for task
            in normalized.tasks
        )

        self.assertLessEqual(
            total,
            3000,
        )


if __name__ == "__main__":
    unittest.main()
